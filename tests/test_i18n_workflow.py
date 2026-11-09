from __future__ import annotations

import ast
import string
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, QRect, QSettings, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QRawFont
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QStyle, QStyleOptionComboBox
from test_gui import wait_for

from framepick.i18n import CATALOGS, set_language, tr
from framepick.model import Clip, Project
from framepick.timeline import Timeline
from framepick.window import MainWindow


@pytest.fixture
def window(qapp, tmp_path):
    preferences = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    preferences.setValue("language", "zh_CN")
    instance = MainWindow(preferences=preferences, recovery_file=tmp_path / "recovery.json")
    instance.show()
    qapp.processEvents()
    yield instance
    instance.dirty = False
    instance.close()
    qapp.processEvents()
    set_language("zh_CN")


def test_every_application_string_has_complete_matching_placeholders():
    keys = set()
    for file in Path("src/framepick").glob("*.py"):
        tree = ast.parse(file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "tr"
            ):
                if isinstance(node.args[0], ast.Constant):
                    keys.add(node.args[0].value)
    formatter = string.Formatter()
    for code, catalog in CATALOGS.items():
        assert keys <= catalog.keys(), (code, keys - catalog.keys())
        for source, translated in catalog.items():

            def placeholders(text):
                return sorted(
                    (name, spec, conversion)
                    for _, name, spec, conversion in formatter.parse(text)
                    if name is not None
                )

            assert placeholders(source) == placeholders(translated), source
            assert translated.strip(), source


@pytest.mark.gui
@pytest.mark.parametrize("code", ["en", "zh_CN", "ja"])
@pytest.mark.parametrize("size", [(900, 600), (1024, 700), (1330, 920)])
def test_localized_oobe_and_speed_fit(window, qapp, code, size):
    window.change_language(code)
    window.resize(*size)
    qapp.processEvents()
    assert window.video_stack.currentWidget() is not window.video
    assert window.open_button.text() == tr("打开视频")
    assert window.empty_clip_hint.isVisible()
    assert window.preferences.value("language") == code
    option = QStyleOptionComboBox()
    window.speed.initStyleOption(option)
    edit = window.speed.style().subControlRect(
        QStyle.ComplexControl.CC_ComboBox,
        option,
        QStyle.SubControl.SC_ComboBoxEditField,
        window.speed,
    )
    assert (
        edit.width()
        >= max(
            window.speed.fontMetrics().horizontalAdvance(window.speed.itemText(i))
            for i in range(window.speed.count())
        )
        + 6
    )
    assert edit.right() < window.speed.width()
    for control in (
        window.play_button,
        window.speed,
        window.volume_control,
        window.selection_panel,
        window.output_panel,
    ):
        assert control.width() >= control.minimumSizeHint().width() or control is window.speed
    for pane in (window.left_scroll, window.right_scroll):
        assert pane.widget().width() <= pane.viewport().width()
        assert pane.horizontalScrollBar().maximum() == 0
    font = QRawFont.fromFont(qapp.font())
    sample = {
        "en": "FramePick ÀΩЖ012345",
        "zh_CN": "精彩片段截图打开视频",
        "ja": "動画スクリーンショット再生一時停止",
    }[code]
    assert all(font.supportsCharacter(ord(char)) for char in sample)


@pytest.mark.gui
@pytest.mark.integration
def test_restored_unvisited_clips_get_correct_visible_thumbnails(window, video, qapp):
    clips = [Clip(2000, 5000), Clip(25000, 5000), Clip(45000, 5000)]
    window.load_video(video, Project(video, clips=clips))
    wait_for(
        lambda: (
            window.clip_list.count() == 3
            and all(not window.clip_list.item(i).icon().isNull() for i in range(3))
        )
    )
    assert window.player.position() < 500
    assert window.video_stack.currentWidget() is window.video
    assert not window.empty_clip_hint.isVisible()
    for i, channel in enumerate(("red", "green", "blue")):
        color = window.clip_list.item(i).icon().pixmap(88, 54).toImage().pixelColor(40, 25)
        assert getattr(color, channel)() >= 100
        # Verify the delegate actually paints the decoration (not merely the model).
        option = (
            window.clip_list.viewOptions() if hasattr(window.clip_list, "viewOptions") else None
        )
        from PySide6.QtWidgets import QStyleOptionViewItem

        option = option or QStyleOptionViewItem()
        option.rect = QRect(0, 0, 360, 82)
        option.widget = window.clip_list
        image = QImage(360, 82, QImage.Format.Format_ARGB32)
        image.fill(QColor("black"))

        class RecordingPainter(QPainter):
            def __init__(self, target):
                super().__init__(target)
                self.painted_text = []

            def drawText(self, *args):
                self.painted_text.append(args)
                return super().drawText(*args)

        painter = RecordingPainter(image)
        window.clip_list.itemDelegate().paint(painter, option, window.clip_list.model().index(i, 0))
        painter.end()
        painted_text = painter.painted_text
        assert getattr(image.pixelColor(40, 30), channel)() >= 100
        # The duration/status must be visibly painted below the header. Qt's
        # style option turns model newlines into U+2028, which once lost this row.
        assert len(painted_text) == 2
        assert painted_text[1][0].top() > painted_text[0][0].bottom()
        assert tr("待导出") in painted_text[1][-1]
    window.clip_list.setCurrentRow(1)
    before = window.player.position()
    window.change_language("ja")
    assert window.project.clips == clips
    assert window.clip_list.currentRow() == 1
    assert window.player.position() == before
    assert "秒" in window.clip_list.item(0).text()


@pytest.mark.gui
def test_detail_drag_holds_edge_scrolls_both_directions_and_stops(qapp):
    axis = Timeline()
    axis.resize(600, 82)
    axis.set_state(3_600_000, 120000, 120000, 5000, [])
    axis.show()
    qapp.processEvents()
    moves = []
    axis.windowMoved.connect(moves.append)
    QTest.mousePress(axis, Qt.MouseButton.LeftButton, pos=QPoint(round(axis._x(122000)), 40))
    QTest.mouseMove(axis, QPoint(axis.width() - 3, 40))
    old = axis._view
    wait_for(lambda: axis._view[0] > old[0] + 5000)
    assert moves and 0 <= moves[-1] <= axis.total_ms - axis.selection_duration
    QTest.mouseMove(axis, QPoint(2, 40))
    old = axis._view
    wait_for(lambda: axis._view[0] < old[0] - 5000)
    QTest.mouseRelease(axis, Qt.MouseButton.LeftButton, pos=QPoint(2, 40))
    assert not axis._scroll_timer.isActive()
    stopped = axis._view
    QTest.qWait(100)
    assert axis._view == stopped
    axis.hide()


@pytest.mark.gui
def test_standard_qt_dialog_button_translations(qapp):
    from PySide6.QtCore import QCoreApplication

    try:
        for code in ("zh_CN", "ja"):
            set_language(code)
            assert QCoreApplication.translate("QPlatformTheme", "Cancel") != "Cancel"
    finally:
        set_language("zh_CN")
