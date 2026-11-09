"""Discover local tools and read container metadata without frame scans."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from framepick.i18n import tr


def hidden_process_options() -> dict:
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}


@dataclass(frozen=True)
class Tools:
    ffmpeg: Path
    ffprobe: Path
    ffmpeg_origin: str = ""
    ffprobe_origin: str = ""

    @classmethod
    def discover(cls, directory: str | Path | None = None, *, prefer_bundled: bool = True) -> Tools:
        suffix = ".exe" if sys.platform == "win32" else ""
        roots: list[tuple[Path, str]] = []
        bundled: list[tuple[Path, str]] = []
        if getattr(sys, "frozen", False):
            bundled.extend(
                [
                    (Path(sys._MEIPASS) / "bin", tr("内置工具")),
                    (Path(sys.executable).parent / "bin", tr("程序旁的工具")),
                ]
            )
        else:
            bundled.append(
                (Path(__file__).resolve().parents[2] / "vendor" / "bin", tr("开发目录随附工具"))
            )
        custom = [(Path(directory).expanduser(), tr("自定义目录"))] if directory else []
        roots = bundled + custom if prefer_bundled else custom + bundled

        def find(name: str) -> tuple[Path, str]:
            override = os.environ.get(f"FRAMEPICK_{name.upper()}")
            if override:
                path = Path(override).expanduser().resolve()
                if not path.is_file():
                    raise FileNotFoundError(tr("工具不存在：{p0}", p0=path))
                return path, tr("环境变量指定")
            for root, origin in roots:
                candidate = root / f"{name}{suffix}"
                if candidate.is_file():
                    return candidate.resolve(), origin
            found = shutil.which(name)
            if found:
                return Path(found).resolve(), tr("系统 PATH")
            raise FileNotFoundError(
                tr("未找到 FFmpeg / ffprobe。请在工具设置中选择它们所在的目录。")
            )

        ffmpeg, origin = find("ffmpeg")
        ffprobe, probe_origin = find("ffprobe")
        return cls(ffmpeg, ffprobe, origin, probe_origin)


@dataclass(frozen=True)
class MediaInfo:
    path: Path
    duration_ms: int
    width: int
    height: int
    fps: float


def probe(path: Path, tools: Tools) -> MediaInfo:
    path = path.resolve(strict=True)
    command = [
        str(tools.ffprobe),
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "format=duration:stream=width,height,avg_frame_rate,duration",
        "-of",
        "json",
        str(path),
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
        **hidden_process_options(),
    )
    if result.returncode:
        raise ValueError(result.stderr[-3000:] or tr("无法读取视频元数据。"))
    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    if not streams:
        raise ValueError(tr("文件没有可用的视频轨道。"))
    video = streams[0]
    duration = data.get("format", {}).get("duration") or video.get("duration")
    try:
        duration_ms = round(float(duration) * 1000)
        fps = float(Fraction(video.get("avg_frame_rate", "0/1")))
    except (ValueError, TypeError, OverflowError, ZeroDivisionError) as exc:
        raise ValueError(tr("无法确定视频时长或帧率。")) from exc
    if duration_ms <= 0:
        raise ValueError(tr("视频时长无效；暂不支持直播流。"))
    return MediaInfo(path, duration_ms, int(video["width"]), int(video["height"]), fps or 25.0)
