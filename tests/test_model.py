import json

import pytest

from framepick.model import Clip, ExportSettings, Project, fit_window, parse_timecode, timecode


@pytest.mark.parametrize(
    "anchor,duration,total,mode,expected",
    [
        (10000, 5000, 10800000, "after", (10000, 5000)),
        (10000, 5000, 10800000, "before", (5000, 5000)),
        (10000, 5000, 10800000, "center", (7500, 5000)),
        (0, 5000, 10800000, "before", (0, 5000)),
        (10799999, 5000, 10800000, "after", (10795000, 5000)),
        (2000, 5000, 3000, "after", (0, 3000)),
    ],
)
def test_fixed_window_preserves_duration_at_boundaries(anchor, duration, total, mode, expected):
    assert fit_window(anchor, duration, total, mode) == expected


def test_portable_project_roundtrip_and_atomic_replace(tmp_path):
    source = tmp_path / "素材" / "a video.mp4"
    project = Project(source, [Clip(3_601_234, 5000)], settings=ExportSettings(480, 12))
    destination = tmp_path / "highlight.framepick.json"
    project.save(destination)
    assert json.loads(destination.read_text(encoding="utf-8"))["source"] == str(
        source.relative_to(tmp_path)
    )
    assert Project.load(destination) == project
    project.clips.append(Clip(10, 800))
    project.save(destination)
    assert Project.load(destination).clips == project.clips
    assert not list(tmp_path.glob(".framepick-project-*"))


@pytest.mark.parametrize("value", ["nan", "inf", "-1", "01:70", "1:00:60", "0:0:0:0", "oops"])
def test_invalid_times(value):
    with pytest.raises(ValueError):
        parse_timecode(value)


def test_three_hour_times_and_custom_duration():
    assert parse_timecode("02:59:59.125") == 10_799_125
    assert timecode(10_799_125) == "02:59:59.125"
    assert parse_timecode("125.5") == 125500
    assert Clip(120000, 7250).end_ms == 127250


@pytest.mark.parametrize(
    "start,duration", [(-1, 5000), (0, 0), (0, 50), (0, 3_600_001), (0.0, 5000)]
)
def test_invalid_clip_ranges(start, duration):
    with pytest.raises(ValueError):
        Clip(start, duration)


def test_untrusted_project_ids_and_settings(tmp_path):
    path = tmp_path / "bad.json"
    base = {
        "schema_version": 1,
        "source": "video.mp4",
        "clips": [{"start_ms": 0, "duration_ms": 5000, "id": "../../unsafe"}],
    }
    path.write_text(json.dumps(base), encoding="utf-8")
    with pytest.raises(ValueError):
        Project.load(path)
    base["clips"] = []
    base["settings"] = {"fps": 1000000}
    path.write_text(json.dumps(base), encoding="utf-8")
    with pytest.raises(ValueError):
        Project.load(path)
