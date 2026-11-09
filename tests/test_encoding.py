from __future__ import annotations

import re
import sys
import threading
import time

import pytest
from PIL import Image

from framepick.encoding import (
    Cancelled,
    EncodingError,
    export_gif,
    export_snapshot,
    gif_commands,
    run_ffmpeg,
)
from framepick.media import probe
from framepick.model import Clip, ExportSettings


@pytest.mark.integration
def test_selected_late_range_gif_and_snapshot_content(video, tools, tmp_path):
    info = probe(video, tools)
    assert info.duration_ms == 60_000
    assert (info.width, info.height) == (160, 90)
    clip = Clip(42_350, 5000)
    output = export_gif(tools, video, clip, ExportSettings(128, 5), tmp_path, threading.Event())
    with Image.open(output) as image:
        assert image.n_frames == 25
        assert image.size == (128, 72)
        duration = 0
        for index in range(image.n_frames):
            image.seek(index)
            duration += image.info["duration"]
            red, green, blue = image.convert("RGB").getpixel((60, 35))
            assert blue > 220 and red < 30 and green < 30
        assert duration == 5000
    snapshot = export_snapshot(tools, video, 43_000, tmp_path, threading.Event())
    with Image.open(snapshot) as image:
        assert image.size == (160, 90)
        assert image.convert("RGB").getpixel((80, 45))[2] > 220
    # Re-exporting the same moment must not overwrite previous user output.
    second = export_gif(tools, video, clip, ExportSettings(128, 5), tmp_path, threading.Event())
    assert second != output
    assert output.is_file() and second.is_file()
    assert not list(tmp_path.glob(".framepick-*"))


@pytest.mark.integration
def test_subsecond_seek_keeps_scene_transition_at_the_right_time(video, tools, tmp_path):
    output = export_gif(
        tools, video, Clip(19350, 2000), ExportSettings(128, 10), tmp_path, threading.Event()
    )
    with Image.open(output) as image:
        assert image.n_frames == 20
        colors = []
        for index in range(image.n_frames):
            image.seek(index)
            red, green, _blue = image.convert("RGB").getpixel((60, 35))
            colors.append("red" if red > green else "green")
        # The original scene transition is 650 ms after the requested start.
        assert 6 <= colors.index("green") <= 7
        assert colors[0] == "red" and colors[-1] == "green"


@pytest.mark.integration
def test_three_hour_video_only_feeds_selected_range_to_palette(long_video, tools, tmp_path):
    assert probe(long_video, tools).duration_ms == 10_800_000
    # Near the beginning intentionally: an output-only trim would process the
    # remaining THREE HOURS, which is the exact Torchio regression being guarded.
    clip = Clip(17_000, 5000)
    palette, _ = gif_commands(
        tools,
        long_video,
        clip,
        ExportSettings(128, 5),
        tmp_path / "palette.png",
        tmp_path / "result.gif",
    )
    palette[palette.index("-loglevel") + 1] = "info"
    filter_index = palette.index("-vf") + 1
    palette[filter_index] = "showinfo," + palette[filter_index]
    lines = []
    started = time.monotonic()
    run_ffmpeg(
        palette, clip.duration_ms, threading.Event(), lambda _value: None, lines.append, timeout=30
    )
    frames = [
        line for line in lines if "Parsed_showinfo" in line and re.search(r"\bn:\s*\d+", line)
    ]
    assert 1 <= len(frames) <= 6, "Source decoding leaked past the five-second input cap"
    output = export_gif(
        tools,
        long_video,
        Clip(9_500_000, 5000),
        ExportSettings(128, 5),
        tmp_path,
        threading.Event(),
    )
    with Image.open(output) as image:
        assert image.n_frames == 25
    print(
        f"3h source: palette input frames={len(frames)}, total test time={time.monotonic() - started:.3f}s"
    )


def test_both_pipes_are_drained_and_errors_are_bounded():
    command = [
        sys.executable,
        "-c",
        "import sys; sys.stderr.write('warning\\n'*20000); sys.stderr.flush(); "
        "print('out_time_us=1000000', flush=True)",
    ]
    values = []
    run_ffmpeg(command, 1000, threading.Event(), values.append, timeout=10)
    assert values[-1] == 1
    command = [sys.executable, "-c", "import sys; sys.stderr.write('x'*200000); sys.exit(1)"]
    with pytest.raises(EncodingError) as error:
        run_ffmpeg(command, 1000, threading.Event(), lambda _value: None, timeout=10)
    assert len(str(error.value)) <= 2000


def test_cancel_actually_terminates_child():
    event = threading.Event()
    timer = threading.Timer(0.3, event.set)
    timer.start()
    started = time.monotonic()
    try:
        with pytest.raises(Cancelled):
            run_ffmpeg(
                [sys.executable, "-c", "import time; time.sleep(60)"],
                1000,
                event,
                lambda _value: None,
            )
    finally:
        timer.cancel()
    assert time.monotonic() - started < 5


@pytest.mark.integration
def test_cancel_does_not_leave_partial_files(video, tools, tmp_path):
    event = threading.Event()

    def progress(_stage, value):
        if value >= 0.3:
            event.set()

    with pytest.raises(Cancelled):
        export_gif(tools, video, Clip(0, 5000), ExportSettings(), tmp_path, event, progress)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.integration
def test_no_video_frames_fails_cleanly(video, tools, tmp_path):
    with pytest.raises(EncodingError):
        export_gif(tools, video, Clip(100000, 5000), ExportSettings(), tmp_path, threading.Event())
    assert list(tmp_path.iterdir()) == []
