"""Qt adapters: all probing and file encoding runs off the GUI thread."""

from __future__ import annotations

import tempfile
import threading
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QThread, Signal

from framepick.encoding import Cancelled, export_gif, export_snapshot, run_ffmpeg
from framepick.i18n import tr
from framepick.media import Tools, probe
from framepick.model import Clip, ExportSettings


class ProbeWorker(QThread):
    ready = Signal(object)
    failed = Signal(str)

    def __init__(self, source: Path, tools: Tools, parent=None):
        super().__init__(parent)
        self.source, self.tools = source, tools

    def run(self):
        try:
            self.ready.emit(probe(self.source, self.tools))
        except Exception as exc:
            self.failed.emit(str(exc))


class ExportWorker(QThread):
    progress = Signal(str, str, float)
    succeeded = Signal(str, str)
    failed = Signal(str, str)
    summary = Signal(int, int, bool, str)

    def __init__(
        self,
        tools: Tools,
        source: Path,
        clips: list[Clip],
        settings: ExportSettings,
        directory: Path,
        parent=None,
    ):
        super().__init__(parent)
        self.tools, self.source, self.clips = tools, source, list(clips)
        self.settings, self.directory = settings, directory
        self.cancel_event = threading.Event()

    def run(self):
        succeeded, failed = 0, 0
        log_path = self.directory / (
            f"framepick-export-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:6]}.log"
        )
        lock = threading.Lock()
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            with log_path.open("w", encoding="utf-8") as stream:

                def log(text: str) -> None:
                    with lock:
                        stream.write(f"{datetime.now():%H:%M:%S} {text}\n")
                        stream.flush()

                for clip in self.clips:
                    if self.cancel_event.is_set():
                        break
                    try:
                        output = export_gif(
                            self.tools,
                            self.source,
                            clip,
                            self.settings,
                            self.directory,
                            self.cancel_event,
                            lambda stage, value, cid=clip.id: self.progress.emit(cid, stage, value),
                            log,
                        )
                        succeeded += 1
                        self.succeeded.emit(clip.id, str(output))
                        log(f"OK {output.name}")
                    except Cancelled:
                        self.failed.emit(clip.id, tr("已取消，可重试。"))
                        break
                    except Exception as exc:
                        failed += 1
                        self.failed.emit(clip.id, str(exc))
                        log(f"ERROR {clip.id}: {exc}")
        except Exception as exc:
            failed += 1
            self.failed.emit("", str(exc))
        self.summary.emit(succeeded, failed, self.cancel_event.is_set(), str(log_path))


class SnapshotWorker(QThread):
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(self, tools: Tools, source: Path, position_ms: int, directory: Path, parent=None):
        super().__init__(parent)
        self.tools, self.source = tools, source
        self.position_ms, self.directory = position_ms, directory
        self.cancel_event = threading.Event()

    def run(self):
        try:
            output = export_snapshot(
                self.tools, self.source, self.position_ms, self.directory, self.cancel_event
            )
            self.succeeded.emit(str(output))
        except Exception as exc:
            self.failed.emit(str(exc))


class ThumbnailWorker(QThread):
    """One input-side seek and one small frame; never scans a whole video."""

    ready = Signal(str, int, object)
    failed = Signal(str, int, str)

    def __init__(self, tools: Tools, source: Path, clip_id: str, start_ms: int, parent=None):
        super().__init__(parent)
        self.tools, self.source = tools, source
        self.clip_id, self.start_ms = clip_id, start_ms
        self.cancel_event = threading.Event()

    def run(self):
        from PySide6.QtGui import QImage

        try:
            with tempfile.TemporaryDirectory(prefix="framepick-thumb-") as folder:
                output = Path(folder) / "frame.png"
                command = [
                    str(self.tools.ffmpeg),
                    "-hide_banner",
                    "-nostdin",
                    "-v",
                    "error",
                    "-y",
                    "-threads",
                    "2",
                    "-ss",
                    f"{self.start_ms / 1000:.3f}",
                    "-t",
                    "1",
                    "-i",
                    str(self.source),
                    "-map",
                    "0:v:0",
                    "-an",
                    "-sn",
                    "-dn",
                    "-vf",
                    "scale=320:180:force_original_aspect_ratio=decrease",
                    "-frames:v",
                    "1",
                    "-threads",
                    "1",
                    str(output),
                ]
                run_ffmpeg(command, 1000, self.cancel_event, lambda _: None, timeout=25)
                image = QImage(str(output))
                if image.isNull():
                    raise ValueError("No frame at this position")
                self.ready.emit(self.clip_id, self.start_ms, image)
        except Cancelled:
            pass
        except Exception as exc:
            self.failed.emit(self.clip_id, self.start_ms, str(exc))
