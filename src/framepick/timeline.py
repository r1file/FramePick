"""Two-scale, fixed-width time windows. Never decodes or scans a video."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFontMetrics, QMouseEvent, QPainter, QPen, QWheelEvent
from PySide6.QtWidgets import QWidget

from framepick.controls import time_font
from framepick.i18n import tr
from framepick.model import Clip, timecode


class Timeline(QWidget):
    seekRequested = Signal(int)
    windowMoved = Signal(int)

    def __init__(self, *, overview: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self.overview = overview
        self.total_ms = 0
        self.position_ms = 0
        self.selection_start = 0
        self.selection_duration = 5000
        self.span_ms = 60_000
        self.clips: list[Clip] = []
        self._view = (0, 1)
        self._drag: str | None = None
        self._drag_offset = 0
        self._pointer_x = 0.0
        self._scroll_timer = QTimer(self)
        self._scroll_timer.setInterval(30)
        self._scroll_timer.timeout.connect(self._autoscroll)
        self.setFixedHeight(56 if overview else 82)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(tr("全片时间轴") if overview else tr("局部精调时间轴"))
        self.setToolTip(tr("点击定位；拖动青色窗口整体平移。局部时间轴可用滚轮缩放。"))

    def set_state(self, total: int, position: int, start: int, duration: int, clips: list[Clip]):
        self.total_ms = total
        self.position_ms = position
        self.selection_start = start
        self.selection_duration = duration
        self.clips = clips
        if not self._drag:
            if self.overview:
                self._view = (0, max(1, total))
            else:
                span = min(max(1000, self.span_ms), max(1, total))
                origin = max(0, min(position - span // 2, total - span))
                self._view = (origin, origin + span)
        self.update()

    def _x(self, milliseconds: int) -> float:
        low, high = self._view
        return 14 + (milliseconds - low) / max(1, high - low) * max(1, self.width() - 28)

    def _time(self, x: float) -> int:
        low, high = self._view
        value = low + (x - 14) / max(1, self.width() - 28) * (high - low)
        return max(0, min(self.total_ms, round(value)))

    def _selection_rect(self) -> QRectF:
        left = self._x(self.selection_start)
        right = self._x(self.selection_start + self.selection_duration)
        return QRectF(left, 27, max(7.0, right - left), self.height() - 47)

    def _axis_labels(self, step: int) -> list[tuple[int, str, QRectF]]:
        low, high = self._view
        metrics = QFontMetrics(time_font(9))
        values = [low, high, *range(math.ceil(low / step) * step, high + 1, step)]
        labels = []
        seen = set()
        # Boundary labels get first choice of space, including non-round EOF times.
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            precision = step < 1000 or (value in (low, high) and value % 1000 != 0)
            text = timecode(value, precision=precision)
            width = metrics.horizontalAdvance(text) + 6
            left = max(10.0, min(self._x(value) - width / 2, self.width() - 10 - width))
            rect = QRectF(left, 3, width, max(20, metrics.height() + 2))
            if value not in (low, high) and any(
                rect.adjusted(-7, 0, 7, 0).intersects(previous[2]) for previous in labels
            ):
                continue
            labels.append((value, text, rect))
        return labels

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#171f2b"))
        if not self.total_ms:
            painter.setPen(QColor("#8492a6"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, tr("打开视频后开始选取"))
            return
        low, high = self._view
        painter.setClipRect(self.rect().adjusted(9, 0, -9, 0))
        span = high - low
        target_step = span / max(2, self.width() / 125)
        steps = [
            100,
            200,
            500,
            1000,
            2000,
            5000,
            10000,
            15000,
            30000,
            60000,
            120000,
            300000,
            600000,
            1800000,
            3600000,
        ]
        step = next((value for value in steps if value >= target_step), 3600000)
        font = time_font(9)
        painter.setFont(font)
        for tick in range(math.ceil(low / step) * step, high + 1, step):
            x = self._x(tick)
            painter.setPen(QColor("#2b3748"))
            painter.drawLine(QPointF(x, 24), QPointF(x, self.height() - 16))
        painter.setPen(QColor("#c1d0e3"))
        for _value, text, rect in self._axis_labels(step):
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        for clip in self.clips:
            if clip.end_ms < low or clip.start_ms > high:
                continue
            rect = QRectF(
                self._x(clip.start_ms),
                self.height() - 17,
                max(3.0, self._x(clip.end_ms) - self._x(clip.start_ms)),
                6,
            )
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#e5af67"))
            painter.drawRoundedRect(rect, 2, 2)
        painter.setPen(QPen(QColor("#62dfc7"), 1.6))
        painter.setBrush(QColor(67, 211, 184, 46))
        rect = self._selection_rect()
        painter.drawRoundedRect(rect, 4, 4)
        if not self.overview and rect.width() > 65:
            painter.setPen(QColor("#a8f2e3"))
            painter.drawText(
                rect, Qt.AlignmentFlag.AlignCenter, f"{self.selection_duration / 1000:g} s"
            )
        x = self._x(self.position_ms)
        painter.setPen(QPen(QColor("#f5f8fc"), 1.5))
        painter.drawLine(QPointF(x, 22), QPointF(x, self.height() - 18))

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() != Qt.MouseButton.LeftButton or not self.total_ms:
            return
        if self._selection_rect().contains(event.position()):
            self._drag = "window"
            self._drag_offset = self._time(event.position().x()) - self.selection_start
        else:
            self._drag = "seek"
            self.seekRequested.emit(self._time(event.position().x()))
        self._pointer_x = event.position().x()
        if not self.overview:
            self._scroll_timer.start()

    def mouseMoveEvent(self, event: QMouseEvent):
        if not self._drag:
            return
        self._pointer_x = event.position().x()
        value = self._time(event.position().x())
        if self._drag == "window":
            start = max(0, min(value - self._drag_offset, self.total_ms - self.selection_duration))
            self.windowMoved.emit(start)
        else:
            self.seekRequested.emit(value)

    def mouseReleaseEvent(self, _event):
        self._scroll_timer.stop()
        self._drag = None
        self.update()

    def _autoscroll(self):
        if not self._drag or self.overview:
            return
        edge = 40
        x = self._pointer_x
        strength = (
            min(1.0, (x - (self.width() - edge)) / edge)
            if x > self.width() - edge
            else max(-1.0, (x - edge) / edge)
            if x < edge
            else 0
        )
        if not strength:
            return
        low, high = self._view
        span = high - low
        origin = max(0, min(self.total_ms - span, low + round(span * 0.025 * strength)))
        if origin == low:
            return
        self._view = (origin, origin + span)
        value = self._time(x)
        if self._drag == "window":
            start = max(0, min(value - self._drag_offset, self.total_ms - self.selection_duration))
            self.windowMoved.emit(start)
        else:
            self.seekRequested.emit(value)
        self.update()

    def hideEvent(self, event):
        self._scroll_timer.stop()
        self._drag = None
        super().hideEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        if self.overview:
            event.ignore()
            return
        factor = 0.75 if event.angleDelta().y() > 0 else 1.333333
        self.span_ms = round(max(5000, min(600_000, self.span_ms * factor)))
        self.set_state(
            self.total_ms,
            self.position_ms,
            self.selection_start,
            self.selection_duration,
            self.clips,
        )
        event.accept()
