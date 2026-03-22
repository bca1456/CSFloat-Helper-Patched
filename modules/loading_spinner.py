# modules/loading_spinner.py

from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QPen
from PyQt6.QtCore import Qt, QTimer, QRectF


class LoadingSpinner(QWidget):
    """Анимированный спиннер загрузки. Рисует вращающуюся дугу."""

    def __init__(self, parent=None, size=48, line_width=4, color=None):
        super().__init__(parent)
        from modules.theme import Theme

        self._size = size
        self._line_width = line_width
        self._color = QColor(color) if color else QColor(Theme.PRIMARY)
        self._angle = 0
        self._span = 80

        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)
        self._timer.setInterval(16)  # ~60 fps

    def start(self):
        self._timer.start()
        self.show()

    def stop(self):
        self._timer.stop()
        self.hide()

    def is_spinning(self):
        return self._timer.isActive()

    def _rotate(self):
        self._angle = (self._angle - 6) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen(self._color, self._line_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        margin = self._line_width / 2 + 1
        rect = QRectF(margin, margin, self._size - 2 * margin, self._size - 2 * margin)
        painter.drawArc(rect, self._angle * 16, self._span * 16)

        painter.end()


class LoadingOverlay(QWidget):
    """Полупрозрачный оверлей со спиннером и текстом по центру виджета."""

    def __init__(self, parent=None, text=""):
        super().__init__(parent)
        from modules.theme import Theme

        self._text = text
        self._spinner = LoadingSpinner(self, size=40, line_width=3)
        self._bg_color = QColor(Theme.BG_WHITE)
        self._bg_color.setAlpha(200)
        self._text_color = QColor(Theme.TEXT_SECONDARY)

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.hide()

    def start(self, text=""):
        if text:
            self._text = text
        self._reposition()
        self.show()
        self.raise_()
        self._spinner.start()

    def stop(self):
        self._spinner.stop()
        self.hide()

    def set_text(self, text):
        self._text = text
        self.update()

    def _reposition(self):
        if self.parent():
            self.setGeometry(self.parent().rect())
        cx = self.width() // 2 - self._spinner.width() // 2
        text_height = 20 if self._text else 0
        total_h = self._spinner.height() + text_height
        cy = (self.height() - total_h) // 2
        self._spinner.move(cx, cy)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._bg_color)

        if self._text:
            from modules.theme import Theme
            from PyQt6.QtGui import QFont

            painter.setPen(self._text_color)
            painter.setFont(QFont(Theme.FONT_FAMILY, Theme.FONT_SIZE_SMALL))
            text_y = self._spinner.y() + self._spinner.height() + 6
            text_rect = QRectF(0, text_y, self.width(), 20)
            painter.drawText(
                text_rect,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                self._text,
            )
        painter.end()
