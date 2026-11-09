"""Small native vector controls; all drawing uses logical coordinates at any DPI."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QFontMetrics,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionButton,
    QStyleOptionComboBox,
    QStyleOptionSpinBox,
    QStyleOptionViewItem,
    QWidget,
)

from framepick.i18n import tr


class ComboBox(QComboBox):
    def paintEvent(self, event):
        super().paintEvent(event)
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        rect = self.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox, option, QStyle.SubControl.SC_ComboBoxArrow, self
        )
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#b2c1d5"), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        center = rect.center()
        painter.drawPolyline(
            [
                QPointF(center.x() - 4, center.y() - 2),
                QPointF(center.x(), center.y() + 2),
                QPointF(center.x() + 4, center.y() - 2),
            ]
        )


class SpinArrows:
    def paintEvent(self, event):
        super().paintEvent(event)
        option = QStyleOptionSpinBox()
        self.initStyleOption(option)
        painter = QPainter(self)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#b2c1d5" if self.isEnabled() else "#586577"))
        for control, direction in (
            (QStyle.SubControl.SC_SpinBoxUp, -1),
            (QStyle.SubControl.SC_SpinBoxDown, 1),
        ):
            rect = self.style().subControlRect(
                QStyle.ComplexControl.CC_SpinBox, option, control, self
            )
            center = rect.center()
            path = QPainterPath(QPointF(center.x() - 3, center.y() - direction))
            path.lineTo(center.x() + 3, center.y() - direction)
            path.lineTo(center.x(), center.y() + 2 * direction)
            path.closeSubpath()
            painter.drawPath(path)


class SpinBox(SpinArrows, QSpinBox):
    pass


class DoubleSpinBox(SpinArrows, QDoubleSpinBox):
    pass


def time_font(size: int = 10) -> QFont:
    family = (
        QApplication.instance().property("framepick.mono_family")
        if QApplication.instance()
        else None
    )
    font = QFont(family) if family else QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    font.setPointSize(size)
    font.setWeight(QFont.Weight.DemiBold)
    font.setFixedPitch(True)
    font.setStyleHint(QFont.StyleHint.Monospace)
    return font


def draw_symbol(painter: QPainter, name: str, rect: QRectF, color: QColor):
    painter.save()
    painter.translate(rect.topLeft())
    painter.scale(rect.width() / 24, rect.height() / 24)
    painter.setPen(
        QPen(color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    )
    painter.setBrush(Qt.BrushStyle.NoBrush)
    if name == "play":
        path = QPainterPath(QPointF(8, 5))
        path.lineTo(19, 12)
        path.lineTo(8, 19)
        path.closeSubpath()
        painter.fillPath(path, color)
    elif name == "pause":
        painter.fillRect(QRectF(6, 5, 4, 14), color)
        painter.fillRect(QRectF(14, 5, 4, 14), color)
    elif name in ("volume", "muted"):
        path = QPainterPath(QPointF(3, 9))
        for x, y in ((7, 9), (12, 5), (12, 19), (7, 15), (3, 15)):
            path.lineTo(x, y)
        path.closeSubpath()
        painter.drawPath(path)
        if name == "muted":
            painter.drawLine(QPointF(16, 9), QPointF(21, 15))
            painter.drawLine(QPointF(21, 9), QPointF(16, 15))
        else:
            painter.drawArc(QRectF(11, 7, 8, 10), -65 * 16, 130 * 16)
            painter.drawArc(QRectF(10, 3, 14, 18), -55 * 16, 110 * 16)
    elif name == "camera":
        painter.drawRoundedRect(QRectF(3, 7, 18, 13), 2, 2)
        painter.drawEllipse(QRectF(8, 10, 8, 7))
        painter.drawPolyline([QPointF(7, 7), QPointF(9, 4), QPointF(15, 4), QPointF(17, 7)])
    elif name == "plus":
        painter.drawLine(QPointF(5, 12), QPointF(19, 12))
        painter.drawLine(QPointF(12, 5), QPointF(12, 19))
    elif name == "loop":
        painter.drawArc(QRectF(4, 5, 16, 14), 25 * 16, 285 * 16)
        painter.drawPolyline([QPointF(17, 3), QPointF(21, 7), QPointF(16, 8)])
    elif name == "folder":
        path = QPainterPath(QPointF(3, 7))
        for x, y in ((3, 20), (21, 20), (21, 7), (12, 7), (10, 4), (3, 4), (3, 7)):
            path.lineTo(x, y)
        painter.drawPath(path)
    painter.restore()


class ActionButton(QPushButton):
    """A real accessible button with painted vector icon and optional keycaps."""

    def __init__(self, text: str, *, keycap: str = "", symbol: str = "", primary=False):
        super().__init__(text)
        self.keycap = keycap
        self.symbol = symbol
        self.primary = primary
        self.setMinimumHeight(36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(text or symbol)
        if primary:
            self.setObjectName("primary")

    def set_symbol(self, name: str):
        self.symbol = name
        self.update()

    def _key_width(self) -> int:
        metrics = QFontMetrics(time_font(8))
        return (
            sum(max(20, metrics.horizontalAdvance(key) + 12) + 4 for key in self.keycap.split("+"))
            if self.keycap
            else 0
        )

    def sizeHint(self) -> QSize:
        if self.symbol and not self.text() and not self.keycap:
            return QSize(38, 36)
        text = self.fontMetrics().horizontalAdvance(self.text())
        width = 24 + text + (26 if self.symbol else 0) + self._key_width()
        if self.keycap and self.text():
            width += 8
        return QSize(max(38, width), 36)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        option = QStyleOptionButton()
        self.initStyleOption(option)
        option.text = ""
        self.style().drawControl(QStyle.ControlElement.CE_PushButton, option, painter, self)
        color = QColor("#092e27" if self.primary else "#e5edf8")
        if not self.isEnabled():
            color = QColor("#6c7d91")
        painter.setPen(color)
        content = self.sizeHint().width() - 24
        x = max(10.0, (self.width() - content) / 2)
        if self.symbol:
            draw_symbol(painter, self.symbol, QRectF(x, (self.height() - 20) / 2, 20, 20), color)
            x += 26
        if self.text():
            painter.setFont(self.font())
            width = self.fontMetrics().horizontalAdvance(self.text())
            painter.drawText(
                QRectF(x, 0, width + 2, self.height()), Qt.AlignmentFlag.AlignVCenter, self.text()
            )
            x += width + (8 if self.keycap else 0)
        painter.setFont(time_font(8))
        for key in self.keycap.split("+") if self.keycap else []:
            width = max(20, painter.fontMetrics().horizontalAdvance(key) + 12)
            rect = QRectF(x, (self.height() - 21) / 2, width, 21)
            painter.setPen(QPen(QColor("#2c8b76" if self.primary else "#53667e"), 1))
            painter.setBrush(QColor("#7ae2c9" if self.primary else "#14202e"))
            painter.drawRoundedRect(rect, 4, 4)
            painter.setPen(color)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, key)
            x += width + 4


def button(text: str, action, *, primary=False, keycap="", symbol="", tooltip="") -> ActionButton:
    widget = ActionButton(text, keycap=keycap, symbol=symbol, primary=primary)
    widget.clicked.connect(action)
    widget.setToolTip(tooltip or f"{text}{f' ({keycap})' if keycap else ''}")
    return widget


class VolumeControl(QWidget):
    """A mute icon with a hover popup; expanding it never shifts the layout."""

    def __init__(self, audio, parent=None):
        super().__init__(parent)
        self.audio = audio
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.mute_button = ActionButton("", symbol="volume")
        self.mute_button.setFixedSize(38, 36)
        self.mute_button.clicked.connect(self.toggle)
        layout.addWidget(self.mute_button)
        self.setFixedWidth(38)
        self.popup = QFrame(self, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.popup.setObjectName("volumePopup")
        self.popup.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        popup_layout = QHBoxLayout(self.popup)
        popup_layout.setContentsMargins(12, 10, 12, 10)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setFixedWidth(120)
        self.slider.setValue(round(audio.volume() * 100))
        self.slider.valueChanged.connect(lambda value: self.audio.setVolume(value / 100))
        popup_layout.addWidget(self.slider)
        self.value_label = QLabel()
        self.value_label.setFont(time_font(9))
        self.value_label.setFixedWidth(38)
        popup_layout.addWidget(self.value_label)
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self._hide_if_outside)
        for widget in (self, self.mute_button, self.popup, self.slider):
            widget.installEventFilter(self)
        audio.volumeChanged.connect(self._sync)
        audio.mutedChanged.connect(self._sync)
        self._sync()

    def toggle(self):
        self.audio.setMuted(not self.audio.isMuted())

    def _sync(self, *_):
        muted = self.audio.isMuted() or self.audio.volume() == 0
        self.mute_button.set_symbol("muted" if muted else "volume")
        label = tr("取消静音") if self.audio.isMuted() else tr("静音")
        self.mute_button.setAccessibleName(label)
        self.mute_button.setToolTip(tr("{p0}（M）\n悬停调节音量", p0=label))
        self.value_label.setText(f"{round(self.audio.volume() * 100)}%")
        self.slider.blockSignals(True)
        self.slider.setValue(round(self.audio.volume() * 100))
        self.slider.blockSignals(False)

    def show_volume(self):
        self.hide_timer.stop()
        self.popup.adjustSize()
        point = self.mapToGlobal(
            QPoint(self.width() - self.popup.width(), -self.popup.height() - 7)
        )
        screen = QApplication.screenAt(self.mapToGlobal(QPoint(0, 0)))
        if screen:
            bounds = screen.availableGeometry()
            point.setX(max(bounds.left(), min(point.x(), bounds.right() - self.popup.width())))
        self.popup.move(point)
        self.popup.show()

    def _hide_if_outside(self):
        if not self.underMouse() and not self.popup.underMouse():
            self.popup.hide()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Enter:
            self.show_volume()
        elif event.type() == QEvent.Type.Leave:
            self.hide_timer.start(220)
        return super().eventFilter(watched, event)


class ClipDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        painter.save()
        styled = QStyleOptionViewItem(option)
        self.initStyleOption(styled, index)
        # Copy before clearing the style option: PySide may expose the property
        # as a wrapper referencing the option's own QIcon.
        icon = QIcon(styled.icon)
        # initStyleOption normalizes newlines to U+2028; read the model's
        # original text so duration/status get their own line and font.
        lines = str(index.data(Qt.ItemDataRole.DisplayRole) or "").splitlines()
        if not lines:
            lines = [""]
        styled.text = ""
        styled.icon = type(icon)()
        style = styled.widget.style() if styled.widget else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, styled, painter, styled.widget)
        rect = option.rect.adjusted(12, 8, -12, -8)
        left = rect.left()
        if not icon.isNull():
            icon.paint(painter, left, rect.top(), 88, 54)
            left += 100
        available = max(1, rect.right() - left)
        painter.setPen(QColor("#e6f1fc"))
        painter.setFont(time_font(10))
        painter.drawText(
            QRectF(left, rect.top(), available, 27),
            Qt.AlignmentFlag.AlignVCenter,
            painter.fontMetrics().elidedText(lines[0], Qt.TextElideMode.ElideRight, available),
        )
        if len(lines) > 1:
            painter.setFont(option.font)
            painter.setPen(QColor("#9eafc5"))
            painter.drawText(
                QRectF(left, rect.top() + 29, available, 24),
                Qt.AlignmentFlag.AlignVCenter,
                painter.fontMetrics().elidedText(lines[1], Qt.TextElideMode.ElideRight, available),
            )
        painter.restore()
