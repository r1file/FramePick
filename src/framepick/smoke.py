"""An opt-in end-to-end check for frozen desktop bundles, using isolated settings."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer
from PySide6.QtGui import QRawFont
from PySide6.QtWidgets import QApplication

from framepick import __version__
from framepick.i18n import current_language, tr
from framepick.media import Tools
from framepick.window import MainWindow


def run(video: Path, report: Path, screenshot: Path | None = None) -> int:
    report = report.resolve()
    report.parent.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    from framepick.theme import configure_application

    configure_application(app)
    app.setApplicationName("FramePickSelfTest")
    preferences = QSettings(str(report.parent / "self-test.ini"), QSettings.Format.IniFormat)
    preferences.setValue("language", os.environ.get("FRAMEPICK_TEST_LANGUAGE", "zh_CN"))
    window = MainWindow(
        preferences=preferences, recovery_file=report.parent / "self-test-project.json"
    )
    window.output_input.setText(str(report.parent / "self-test-output"))
    errors: list[str] = []
    window._error = errors.append
    window.player.errorOccurred.connect(lambda _code, text: errors.append(text))
    window.show()
    state = {"stage": "loading", "started": time.monotonic()}
    data = {"version": __version__, "ok": False, "errors": errors}
    data["language"] = current_language()
    data["first_launch_welcome"] = (
        window.video_stack.currentWidget() is not window.video and not window.clip_list.count()
    )
    if screenshot:
        window.grab().save(str(screenshot.with_name("welcome.png")))
    font = QRawFont.fromFont(app.font())
    data["font_family"] = app.font().family()
    data["ui_font_has_glyphs"] = all(
        font.supportsCharacter(ord(char))
        for char in {
            "en": "FramePick012345ÀΩЖ",
            "zh_CN": "FramePick012345片段截图",
            "ja": "FramePick012345動画スクリーンショット",
        }[current_language()]
    )
    if not data["ui_font_has_glyphs"]:
        errors.append("Packaged font is missing required interface glyphs")
    tools = Tools.discover()
    data["ffmpeg_origin"] = tools.ffmpeg_origin
    data["ffprobe_origin"] = tools.ffprobe_origin
    data["ffmpeg_path"] = str(tools.ffmpeg)
    window.load_video(video)
    timer = QTimer()
    timer.setInterval(80)

    def finish(ok: bool):
        timer.stop()
        data["ok"] = ok
        data["elapsed_seconds"] = round(time.monotonic() - state["started"], 3)
        data["stage"] = state["stage"]
        report.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        if window.export_worker:
            window.export_worker.cancel_event.set()
            window.export_worker.wait(6000)
        if window.snapshot_worker:
            window.snapshot_worker.cancel_event.set()
            window.snapshot_worker.wait(6000)
        app.processEvents()
        window.dirty = False
        window.close()
        app.exit(0 if ok else 1)

    def tick():
        try:
            if errors:
                finish(False)
                return
            if time.monotonic() - state["started"] > 90:
                errors.append("Self-test timed out")
                finish(False)
                return
            if (
                state["stage"] == "loading"
                and window.media
                and window.player.duration() > 0
                and not window._poster_pending
                and window.video.videoSink().videoFrame().isValid()
            ):
                data["first_frame_without_play_click"] = True
                data["source_duration_ms"] = window.media.duration_ms
                window.window_seconds.setValue(min(2, window.media.duration_ms / 4000))
                window.seek(window.media.duration_ms // 2)
                window.player.play()
                state["stage"] = "decoding"
            elif state["stage"] == "decoding" and window.video.videoSink().videoFrame().isValid():
                window.player.pause()
                frame = window.video.videoSink().videoFrame()
                data["decoded_frame_size"] = [frame.width(), frame.height()]
                window.add_clip()
                window.move_window(window.media.duration_ms // 4)
                window.add_clip()
                data["clips"] = [
                    {"start_ms": c.start_ms, "duration_ms": c.duration_ms}
                    for c in window.project.clips
                ]
                window.size_spin.setValue(320)
                window.fps_spin.setValue(10)
                window.export_all()
                state["stage"] = "exporting"
            elif state["stage"] == "exporting" and window.export_worker is None:
                outputs = list(window.output_directory().glob("*.gif"))
                data["gif_files"] = [path.name for path in outputs]
                if len(outputs) < 2 or any(
                    status != tr("已导出") for status in window.clip_status.values()
                ):
                    errors.append(f"GIF export did not complete: {window.clip_status}")
                    finish(False)
                    return
                window.take_snapshot()
                state["stage"] = "snapshot"
            elif state["stage"] == "snapshot" and window.snapshot_worker is None:
                outputs = list(window.output_directory().glob("*.png"))
                data["png_files"] = [path.name for path in outputs]
                if not outputs:
                    errors.append("Snapshot did not complete")
                    finish(False)
                    return
                state["stage"] = "thumbnails"
            elif state["stage"] == "thumbnails" and window.thumbnail_worker is None:
                data["clip_thumbnails"] = all(
                    not window.clip_list.item(i).icon().isNull()
                    for i in range(window.clip_list.count())
                )
                if not data["clip_thumbnails"]:
                    errors.append("Collected clip thumbnails are missing")
                    finish(False)
                    return
                if screenshot:
                    screenshot.parent.mkdir(parents=True, exist_ok=True)
                    window.grab().save(str(screenshot))
                state["stage"] = "complete"
                finish(True)
        except Exception as exc:
            errors.append(str(exc))
            finish(False)

    timer.timeout.connect(tick)
    timer.start()
    return app.exec()
