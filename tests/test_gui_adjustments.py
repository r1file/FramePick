from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QMimeData, QPoint, QPointF, QRect, QSettings, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from test_gui import wait_for

from framepick.timeline import Timeline
from framepick.window import MainWindow


@pytest.fixture
def window(qapp, tmp_path):
    instance = MainWindow(
        preferences=QSettings(str(tmp_path / "preferences.ini"), QSettings.Format.IniFormat),
        recovery_file=tmp_path / "recovery.json",
    )
    instance._error = lambda message: pytest.fail(message)
    instance.show()
    qapp.processEvents()
    yield instance
    if instance.probe_worker:
        instance.probe_worker.wait(31000)
        qapp.processEvents()
    instance.close()
    qapp.processEvents()


@pytest.mark.gui
@pytest.mark.parametrize("width,height", [(900, 600), (1024, 700), (1330, 920)])
def test_layout_does_not_clip_fields_or_overlap_panes(window, qapp, width, height):
    window.resize(width, height)
    qapp.processEvents()
    for scroll in (window.left_scroll, window.right_scroll):
        assert scroll.widget().width() <= scroll.viewport().width()
    assert not window.left_scroll.geometry().intersects(window.right_scroll.geometry())
    for widget in (window.size_spin, window.fps_spin, window.export_button, window.cancel_button):
        bounds = QRect(widget.mapTo(window.output_panel, QPoint(0, 0)), widget.size())
        assert window.output_panel.rect().contains(bounds)
    for spin in (window.size_spin, window.fps_spin, window.window_seconds):
        editor = spin.lineEdit()
        assert editor.width() >= 65, "Qt stylesheet collapsed the spin editor to one pixel"
        assert editor.height() >= editor.fontMetrics().height()
    previous = None
    for action in window.menuBar().actions():
        bounds = window.menuBar().actionGeometry(action)
        assert window.menuBar().rect().contains(bounds)
        if previous:
            assert not previous.intersects(bounds)
        previous = bounds


@pytest.mark.gui
@pytest.mark.parametrize("target", ["video", "list", "output"])
def test_file_drop_is_handled_over_child_widgets(window, qapp, tmp_path, target):
    received = []
    window.load_video = received.append
    path = tmp_path / "drop space 测试.mp4"
    path.touch()
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path))])
    widget = {
        "video": window.video,
        "list": window.clip_list.viewport(),
        "output": window.output_input,
    }[target]
    original = window.output_input.text()
    enter = QDragEnterEvent(
        QPointF(10, 10),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(widget, enter)
    assert enter.isAccepted()
    drop = QDropEvent(
        QPointF(10, 10),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(widget, drop)
    qapp.processEvents()
    assert received == [path]
    assert window.output_input.text() == original


@pytest.mark.gui
@pytest.mark.integration
@pytest.mark.parametrize("muted", [False, True])
def test_import_decodes_first_frame_then_pauses_without_user_play(window, video, muted):
    window.audio.setMuted(muted)
    window.load_video(video)
    wait_for(
        lambda: (
            window.media is not None
            and window.probe_worker is None
            and not window._poster_pending
            and window.video.videoSink().videoFrame().isValid()
        )
    )
    assert window.player.playbackState() == QMediaPlayer.PlaybackState.PausedState
    assert window.audio.isMuted() is muted
    assert window.player.position() <= 100
    assert window.selection_start == 0


@pytest.mark.gui
@pytest.mark.integration
def test_up_down_shortcuts_recall_collected_clips(window, qapp, video):
    window.load_video(video)
    wait_for(
        lambda: (
            window.media is not None and window.probe_worker is None and not window._poster_pending
        )
    )
    for position in (2000, 20000, 40000):
        window.move_window(position)
        window.add_clip()
    window.clip_list.setCurrentRow(0)
    window._activate_clip(window.clip_list.item(0))
    window.activateWindow()
    window.clip_list.setFocus()
    qapp.processEvents()
    QTest.keyClick(window.clip_list, Qt.Key.Key_Down)
    assert window.selection_start == 20000
    QTest.keyClick(window.clip_list, Qt.Key.Key_Up)
    assert window.selection_start == 2000
    QTest.keyClick(window.clip_list, Qt.Key.Key_Up)
    assert window.selection_start == 2000


@pytest.mark.gui
def test_vector_keycaps_time_fonts_and_hover_volume(window, qapp):
    assert window.add_button.keycap == "A"
    assert window.snapshot_button.symbol == "camera"
    assert window.position_label.font().fixedPitch()
    assert "Space" in window.play_button.toolTip()
    assert "M" in window.mute_button.toolTip()
    width = window.volume_control.width()
    QApplication.sendEvent(window.mute_button, QEvent(QEvent.Type.Enter))
    qapp.processEvents()
    assert window.volume_control.popup.isVisible()
    assert window.volume_control.width() == width
    window.volume_control.slider.setValue(72)
    assert abs(window.audio.volume() - 0.72) < 0.001
    window.toggle_mute()
    assert window.audio.isMuted()
    assert window.mute_button.symbol == "muted"


@pytest.mark.gui
@pytest.mark.parametrize("total,step", [(30000, 5000), (10154221, 1800000), (10800000, 1800000)])
def test_start_and_end_time_labels_fit_inside_axis(qapp, total, step):
    timeline = Timeline(overview=True)
    timeline.resize(538, 56)
    timeline.set_state(total, 0, 0, 5000, [])
    labels = timeline._axis_labels(step)
    assert {0, total}.issubset({value for value, _text, _rect in labels})
    for _value, _text, rect in labels:
        assert rect.left() >= 9
        assert rect.right() <= timeline.width() - 9
    for index, first in enumerate(labels):
        for second in labels[index + 1 :]:
            assert not first[2].intersects(second[2])
    if total % 1000:
        assert next(text for value, text, _rect in labels if value == total).endswith(".221")


@pytest.mark.gui
def test_input_focus_does_not_let_shortcuts_swallow_text_or_spin_keys(window, qapp):
    window.activateWindow()
    window.output_input.setFocus()
    qapp.processEvents()
    QTest.keyClicks(window.output_input, "Maps")
    assert window.output_input.text() == "Maps"
    window.size_spin.setFocus()
    qapp.processEvents()
    previous = window.size_spin.value()
    QTest.keyClick(window.size_spin, Qt.Key.Key_Up)
    assert window.size_spin.value() == previous + window.size_spin.singleStep()
