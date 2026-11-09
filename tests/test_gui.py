from __future__ import annotations

import time

import pytest
from PySide6.QtCore import QPointF, QSettings, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest

from framepick.model import Clip
from framepick.timeline import Timeline


def wait_for(predicate, timeout=15):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return
        QTest.qWait(20)
    raise AssertionError("Qt condition timed out")


@pytest.mark.gui
def test_timeline_window_drag_preserves_duration(qapp):
    timeline = Timeline()
    timeline.resize(800, 100)
    timeline.set_state(10_800_000, 100_000, 100_000, 5000, [Clip(50000, 5000)])
    result = []
    timeline.windowMoved.connect(result.append)
    start = QPointF(timeline._x(102_000), 40)
    timeline.mousePressEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            start,
            start,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    end = QPointF(timeline._x(107_000), 40)
    timeline.mouseMoveEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseMove,
            end,
            end,
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    assert abs(result[-1] - 105_000) <= 2
    assert timeline.selection_duration == 5000


@pytest.mark.gui
@pytest.mark.integration
def test_native_player_collect_export_and_screenshot(qapp, video, tmp_path, monkeypatch):
    from framepick.window import MainWindow

    # Isolate all application preferences, auto-recovery and generated files.
    monkeypatch.setattr(
        "framepick.window.QSettings",
        lambda *_: QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat),
    )
    monkeypatch.setattr(
        MainWindow, "recovery_path", staticmethod(lambda: tmp_path / "recovery.json")
    )
    window = MainWindow(
        preferences=QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat),
        recovery_file=tmp_path / "recovery.json",
    )
    errors = []
    window._error = errors.append
    window.show()
    try:
        window.output_input.setText(str(tmp_path / "exports"))
        window.load_video(video)
        wait_for(lambda: window.media is not None and window.probe_worker is None)
        wait_for(lambda: window.player.duration() > 0)
        window.seek(42350)
        window.player.play()
        wait_for(lambda: window.video.videoSink().videoFrame().isValid())
        window.player.pause()
        window.move_window(42350)
        window.add_clip()
        window.move_window(2000)
        window.add_clip()
        assert len(window.project.clips) == 2
        assert all(clip.duration_ms == 5000 for clip in window.project.clips)
        window.fps_spin.setValue(5)
        window.size_spin.setValue(128)
        window.export_all()
        wait_for(lambda: window.export_worker is None, timeout=30)
        assert len(list((tmp_path / "exports").glob("*.gif"))) == 2
        window.take_snapshot()
        wait_for(lambda: window.snapshot_worker is None)
        assert len(list((tmp_path / "exports").glob("*.png"))) == 1
        assert not errors
        assert all(status == "已导出" for status in window.clip_status.values())
    finally:
        if window.export_worker:
            window.export_worker.cancel_event.set()
            window.export_worker.wait(6000)
            qapp.processEvents()
        if window.snapshot_worker:
            window.snapshot_worker.cancel_event.set()
            window.snapshot_worker.wait(6000)
            qapp.processEvents()
        window.dirty = False
        window.close()
        qapp.processEvents()
