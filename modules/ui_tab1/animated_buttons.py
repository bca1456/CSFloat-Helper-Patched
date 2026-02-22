# modules/ui_tab1/animated_buttons.py

from PyQt6.QtWidgets import QPushButton, QGraphicsDropShadowEffect
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QRect
from PyQt6.QtGui import QColor

from modules.theme import Theme


class AnimatedButtonCombo(QPushButton):
    """Кнопка с комбинированной анимацией: масштаб 10% + тень"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_geometry = None
        self._scale_animation = None

        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(0)
        self.shadow.setXOffset(0)
        self.shadow.setYOffset(3)
        self.shadow.setColor(QColor(*Theme.SHADOW_RGB, 0))
        self.setGraphicsEffect(self.shadow)

        self._shadow_animation = None

    def enterEvent(self, event):
        if self._original_geometry is None:
            self._original_geometry = self.geometry()

        original = self._original_geometry
        scale_factor = 1.1
        new_width = int(original.width() * scale_factor)
        new_height = int(original.height() * scale_factor)

        offset_x = (new_width - original.width()) // 2
        offset_y = (new_height - original.height()) // 2

        target_rect = QRect(
            original.x() - offset_x,
            original.y() - offset_y,
            new_width,
            new_height
        )

        self._scale_animation = QPropertyAnimation(self, b"geometry")
        self._scale_animation.setDuration(150)
        self._scale_animation.setStartValue(self.geometry())
        self._scale_animation.setEndValue(target_rect)
        self._scale_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._scale_animation.start()

        self._shadow_animation = QPropertyAnimation(self.shadow, b"blurRadius")
        self._shadow_animation.setDuration(150)
        self._shadow_animation.setStartValue(0)
        self._shadow_animation.setEndValue(20)
        self._shadow_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._shadow_animation.start()

        self.shadow.setColor(QColor(*Theme.SHADOW_RGB, 180))

        super().enterEvent(event)

    def leaveEvent(self, event):
        if self._original_geometry:
            self._scale_animation = QPropertyAnimation(self, b"geometry")
            self._scale_animation.setDuration(150)
            self._scale_animation.setStartValue(self.geometry())
            self._scale_animation.setEndValue(self._original_geometry)
            self._scale_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._scale_animation.start()

        self._shadow_animation = QPropertyAnimation(self.shadow, b"blurRadius")
        self._shadow_animation.setDuration(150)
        self._shadow_animation.setStartValue(20)
        self._shadow_animation.setEndValue(0)
        self._shadow_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._shadow_animation.start()

        self.shadow.setColor(QColor(*Theme.SHADOW_RGB, 0))

        super().leaveEvent(event)
