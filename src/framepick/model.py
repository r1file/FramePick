"""Time-domain and project models. No Qt or decoder dependencies."""

from __future__ import annotations

import json
import math
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from uuid import uuid4

from framepick.i18n import tr


def timecode(milliseconds: int, *, precision: bool = True) -> str:
    value = max(0, round(milliseconds))
    seconds, millis = divmod(value, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    text = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{text}.{millis:03d}" if precision else text


def parse_timecode(text: str) -> int:
    parts = text.strip().split(":")
    if not 1 <= len(parts) <= 3:
        raise ValueError(tr("请输入秒数、分:秒或时:分:秒。"))
    try:
        values = [float(part) for part in parts]
    except ValueError as exc:
        raise ValueError(tr("时间格式无效。")) from exc
    if any(not math.isfinite(value) or value < 0 for value in values):
        raise ValueError(tr("时间必须是非负数。"))
    if len(values) > 1 and (values[-1] >= 60 or (len(values) == 3 and values[-2] >= 60)):
        raise ValueError(tr("分、秒须小于 60。"))
    return round(sum(value * 60**index for index, value in enumerate(reversed(values))) * 1000)


def fit_window(
    anchor_ms: int, duration_ms: int, total_ms: int, mode: str = "after"
) -> tuple[int, int]:
    if total_ms <= 0 or duration_ms <= 0:
        raise ValueError(tr("视频和选取窗口的时长必须大于 0。"))
    length = min(duration_ms, total_ms)
    offset = {"after": 0, "before": length, "center": length // 2}.get(mode)
    if offset is None:
        raise ValueError(f"Unknown window mode: {mode}")
    start = max(0, min(anchor_ms - offset, total_ms - length))
    return start, length


@dataclass(frozen=True)
class Clip:
    start_ms: int
    duration_ms: int
    id: str = field(default_factory=lambda: uuid4().hex[:12])

    def __post_init__(self) -> None:
        if type(self.start_ms) is not int or type(self.duration_ms) is not int:
            raise ValueError(tr("片段时间必须为整数毫秒。"))
        if self.start_ms < 0 or not 100 <= self.duration_ms <= 3_600_000:
            raise ValueError(tr("片段起点须非负，时长须在 0.1 秒至 1 小时之间。"))
        if not self.id or len(self.id) > 64 or not self.id.isalnum():
            raise ValueError("Invalid clip identifier")

    @property
    def end_ms(self) -> int:
        return self.start_ms + self.duration_ms


@dataclass(frozen=True)
class ExportSettings:
    max_size: int = 640
    fps: int = 15

    def __post_init__(self) -> None:
        if type(self.max_size) is not int or not 64 <= self.max_size <= 1920:
            raise ValueError(tr("GIF 长边须在 64–1920 像素之间。"))
        if type(self.fps) is not int or not 1 <= self.fps <= 50:
            raise ValueError(tr("GIF 帧率须在 1–50 FPS 之间。"))


@dataclass
class Project:
    source: Path
    clips: list[Clip] = field(default_factory=list)
    window_ms: int = 5000
    mode: str = "after"
    settings: ExportSettings = field(default_factory=ExportSettings)

    def save(self, destination: Path) -> None:
        destination = destination.resolve()
        try:
            source = os.path.relpath(self.source.resolve(), destination.parent)
        except ValueError:  # Different Windows drives.
            source = str(self.source.resolve())
        data = {
            "schema_version": 1,
            "source": source,
            "window_ms": self.window_ms,
            "mode": self.mode,
            "settings": asdict(self.settings),
            "clips": [asdict(clip) for clip in self.clips],
        }
        destination.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(dir=destination.parent, prefix=".framepick-project-")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
        finally:
            Path(temporary).unlink(missing_ok=True)

    @classmethod
    def load(cls, path: Path) -> Project:
        if path.stat().st_size > 5_000_000:
            raise ValueError(tr("工程文件过大。"))
        with path.open(encoding="utf-8") as stream:
            data = json.load(stream)
        if not isinstance(data, dict) or data.get("schema_version") != 1:
            raise ValueError(tr("不支持此工程版本。"))
        source = Path(data["source"])
        if not source.is_absolute():
            source = path.resolve().parent / source
        window = data.get("window_ms", 5000)
        if type(window) is not int or not 100 <= window <= 3_600_000:
            raise ValueError(tr("工程中的窗口时长无效。"))
        mode = data.get("mode", "after")
        if mode not in ("after", "before", "center"):
            raise ValueError(tr("工程中的选取模式无效。"))
        clips = [Clip(**item) for item in data.get("clips", [])]
        if len({clip.id for clip in clips}) != len(clips):
            raise ValueError(tr("工程包含重复片段 ID。"))
        return cls(
            source.resolve(), clips, window, mode, ExportSettings(**data.get("settings", {}))
        )
