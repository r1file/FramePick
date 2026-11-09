"""Bounded-range FFmpeg jobs; deliberately independent from the GUI.

Every source input has an input-side seek AND duration. Each palette and encode
pass also trims before its filters. No full-video frames or split/palette queues.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import tempfile
import threading
import time
from collections import deque
from collections.abc import Callable
from pathlib import Path

from framepick.i18n import tr
from framepick.media import Tools, hidden_process_options
from framepick.model import Clip, ExportSettings, timecode

Progress = Callable[[str, float], None]


class Cancelled(Exception):
    """A cancelled job never publishes a partial image."""


class EncodingError(RuntimeError):
    pass


def source_args(source: Path, clip: Clip) -> list[str]:
    # -t BEFORE -i is essential: an output-side -t alone does not bound palettegen.
    return [
        "-threads",
        "2",
        "-ss",
        f"{clip.start_ms / 1000:.3f}",
        "-t",
        f"{clip.duration_ms / 1000:.3f}",
        "-i",
        str(source.resolve()),
    ]


def base_filter(clip: Clip, settings: ExportSettings) -> str:
    size = settings.max_size
    return (
        f"trim=duration={clip.duration_ms / 1000:.3f},setpts=PTS-STARTPTS,"
        f"fps={settings.fps},"
        f"scale=w='min({size},iw)':h='min({size},ih)':"
        "force_original_aspect_ratio=decrease:flags=lanczos"
    )


def gif_commands(
    tools: Tools,
    source: Path,
    clip: Clip,
    settings: ExportSettings,
    palette: Path,
    output: Path,
) -> tuple[list[str], list[str]]:
    common = [
        str(tools.ffmpeg),
        "-hide_banner",
        "-nostdin",
        "-loglevel",
        "warning",
        "-progress",
        "pipe:1",
        "-nostats",
        "-y",
    ]
    filtering = base_filter(clip, settings)
    palette_command = [
        *common,
        "-filter_threads",
        "2",
        *source_args(source, clip),
        "-map",
        "0:v:0",
        "-an",
        "-sn",
        "-dn",
        "-vf",
        f"{filtering},palettegen=stats_mode=full",
        "-frames:v",
        "1",
        "-threads",
        "2",
        "-update",
        "1",
        str(palette),
    ]
    gif_command = [
        *common,
        "-filter_complex_threads",
        "2",
        *source_args(source, clip),
        "-i",
        str(palette),
        "-filter_complex",
        f"[0:v:0]{filtering}[v];[v][1:v:0]paletteuse=dither=sierra2_4a:diff_mode=rectangle[out]",
        "-map",
        "[out]",
        "-an",
        "-sn",
        "-dn",
        "-loop",
        "0",
        "-threads",
        "2",
        "-t",
        f"{clip.duration_ms / 1000:.3f}",
        "-f",
        "gif",
        str(output),
    ]
    return palette_command, gif_command


def _check_cancel(cancel: threading.Event) -> None:
    if cancel.is_set():
        raise Cancelled(tr("任务已取消"))


def run_ffmpeg(
    command: list[str],
    duration_ms: int,
    cancel: threading.Event,
    progress: Callable[[float], None],
    log: Callable[[str], None] = lambda _text: None,
    *,
    timeout: float = 1800,
) -> None:
    """Drain BOTH pipes continuously, bound stderr memory, terminate on cancel."""
    _check_cancel(cancel)
    log(json.dumps(command, ensure_ascii=False))
    events: queue.SimpleQueue[str] = queue.SimpleQueue()
    errors: deque[str] = deque(maxlen=80)
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        **hidden_process_options(),
    )

    def read_stdout() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            if line.startswith("out_time_us="):
                events.put(line)

    def read_stderr() -> None:
        assert process.stderr is not None
        for line in process.stderr:
            errors.append(line.rstrip()[:2000])
            log(line.rstrip()[:2000])

    readers = [
        threading.Thread(target=read_stdout, daemon=True),
        threading.Thread(target=read_stderr, daemon=True),
    ]
    for reader in readers:
        reader.start()
    started = time.monotonic()
    try:
        while process.poll() is None:
            _check_cancel(cancel)
            if time.monotonic() - started > timeout:
                raise EncodingError(tr("FFmpeg 超时；可重试该片段。详细信息见导出日志。"))
            while not events.empty():
                try:
                    micros = int(events.get_nowait().split("=", 1)[1])
                    progress(max(0.0, min(1.0, micros / (duration_ms * 1000))))
                except (ValueError, queue.Empty):
                    pass
            cancel.wait(0.05)
        for reader in readers:
            reader.join(timeout=2)
        _check_cancel(cancel)
        if process.returncode:
            raise EncodingError("\n".join(errors) or f"FFmpeg exited with {process.returncode}")
        progress(1.0)
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        for reader in readers:
            reader.join(timeout=2)
        if process.stdout:
            process.stdout.close()
        if process.stderr:
            process.stderr.close()


def _reserve_output(directory: Path, stem: str, suffix: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    # Names may include Unicode; subprocess uses an argument vector, never a shell.
    stem = "".join(c if c not in '<>:"/\\|?*' and ord(c) >= 32 else "_" for c in stem)
    stem = stem[:110].rstrip(". ") or "framepick"
    for number in range(1, 10000):
        name = f"{stem}{'' if number == 1 else f'_{number}'}{suffix}"
        candidate = directory / name
        try:
            with candidate.open("xb"):
                pass
            return candidate
        except FileExistsError:
            continue
    raise EncodingError(tr("输出文件重名过多，请选择其他文件夹。"))


def export_gif(
    tools: Tools,
    source: Path,
    clip: Clip,
    settings: ExportSettings,
    directory: Path,
    cancel: threading.Event,
    progress: Progress = lambda _stage, _value: None,
    log: Callable[[str], None] = lambda _text: None,
) -> Path:
    _check_cancel(cancel)
    stamp = timecode(clip.start_ms).replace(":", "-")
    output = _reserve_output(directory, f"{source.stem}_{stamp}_{clip.id[:6]}", ".gif")
    published = False
    try:
        with tempfile.TemporaryDirectory(dir=directory, prefix=".framepick-") as work:
            palette = Path(work) / "palette.png"
            temporary = Path(work) / "result.gif"
            commands = gif_commands(tools, source, clip, settings, palette, temporary)
            progress(tr("生成片段调色板"), 0.02)
            run_ffmpeg(
                commands[0],
                clip.duration_ms,
                cancel,
                lambda value: progress(tr("生成片段调色板"), 0.02 + value * 0.28),
                log,
            )
            if not palette.is_file() or not palette.stat().st_size:
                raise EncodingError(tr("选中范围没有可解码的画面，未生成调色板。"))
            progress(tr("编码 GIF"), 0.30)
            run_ffmpeg(
                commands[1],
                clip.duration_ms,
                cancel,
                lambda value: progress(tr("编码 GIF"), 0.30 + value * 0.69),
                log,
            )
            if not temporary.is_file() or temporary.stat().st_size < 14:
                raise EncodingError(tr("未生成有效 GIF。"))
            _check_cancel(cancel)
            os.replace(temporary, output)
            published = True
            progress(tr("完成"), 1.0)
            return output
    finally:
        if not published:
            output.unlink(missing_ok=True)


def export_snapshot(
    tools: Tools,
    source: Path,
    position_ms: int,
    directory: Path,
    cancel: threading.Event,
    log: Callable[[str], None] = lambda _text: None,
) -> Path:
    _check_cancel(cancel)
    stamp = timecode(position_ms).replace(":", "-")
    output = _reserve_output(directory, f"{source.stem}_{stamp}", ".png")
    published = False
    try:
        with tempfile.TemporaryDirectory(dir=directory, prefix=".framepick-") as work:
            temporary = Path(work) / "snapshot.png"
            # Single-frame extraction, input-side seek and a one-second input cap.
            command = [
                str(tools.ffmpeg),
                "-hide_banner",
                "-nostdin",
                "-loglevel",
                "warning",
                "-y",
                "-filter_threads",
                "2",
                *source_args(source, Clip(position_ms, 1000)),
                "-map",
                "0:v:0",
                "-frames:v",
                "1",
                "-an",
                "-sn",
                "-dn",
                "-threads",
                "2",
                "-update",
                "1",
                str(temporary),
            ]
            run_ffmpeg(command, 1000, cancel, lambda _value: None, log, timeout=120)
            if not temporary.is_file() or not temporary.stat().st_size:
                raise EncodingError(tr("该位置没有可截取的画面。"))
            _check_cancel(cancel)
            os.replace(temporary, output)
            published = True
            return output
    finally:
        if not published:
            output.unlink(missing_ok=True)
