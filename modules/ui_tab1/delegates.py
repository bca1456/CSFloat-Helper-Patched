# modules/ui_tab1/delegates.py

import os
from PyQt6.QtWidgets import QStyledItemDelegate, QStyle
from PyQt6.QtGui import QPixmap, QColor, QFont
from PyQt6.QtCore import Qt, QRect, QSize, QEvent, QPoint
from modules.theme import Theme


class PriceDelegate(QStyledItemDelegate):
    """Рисует цену с логотипом CSFloat без создания виджетов."""

    def __init__(self, icon_path, parent=None):
        super().__init__(parent)
        self._logo = None
        logo_path = os.path.join(icon_path, "csfloat_logo.png")
        if os.path.exists(logo_path):
            self._logo = QPixmap(logo_path).scaled(
                20, 20, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        self._font = QFont(Theme.FONT_FAMILY, Theme.FONT_SIZE)

    def paint(self, painter, option, index):
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(Theme.BG_SELECTION))

        price_cents = index.data(Qt.ItemDataRole.UserRole)
        if not price_cents:
            return

        painter.save()
        painter.setFont(self._font)

        x = option.rect.x() + 4
        y = option.rect.y()
        h = option.rect.height()

        if self._logo:
            logo_y = y + (h - 20) // 2
            painter.drawPixmap(x, logo_y, self._logo)
            x += 24

        painter.setPen(QColor(Theme.TEXT_PRIMARY))
        text_rect = QRect(x, y, option.rect.right() - x, h)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, f"${price_cents / 100:.2f}")

        painter.restore()

    def sizeHint(self, option, index):
        return QSize(83, 30)


class IconDelegate(QStyledItemDelegate):
    """Рисует иконки стикеров/брелков без создания виджетов."""

    ICON_SIZE = 20
    ICON_SPACING = 2

    def __init__(self, tooltip_widget=None, parent=None):
        super().__init__(parent)
        self._tooltip_widget = tooltip_widget

    def paint(self, painter, option, index):
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(Theme.BG_SELECTION))

        icons = index.data(Qt.ItemDataRole.UserRole)
        if not icons:
            return

        painter.save()

        x = option.rect.x() + 2
        y = option.rect.y() + (option.rect.height() - self.ICON_SIZE) // 2

        for entry in icons:
            pixmap = entry.get("pixmap")
            if pixmap and not pixmap.isNull():
                painter.drawPixmap(x, y, pixmap)
            x += self.ICON_SIZE + self.ICON_SPACING

        painter.restore()

    def sizeHint(self, option, index):
        icons = index.data(Qt.ItemDataRole.UserRole)
        if not icons:
            return QSize(27, 30)
        width = len(icons) * (self.ICON_SIZE + self.ICON_SPACING) + 4
        return QSize(max(width, 27), 30)

    def helpEvent(self, event, view, option, index):
        """Тултипы стикеров — определяем какой стикер под курсором."""
        if event.type() == QEvent.Type.ToolTip:
            icons = index.data(Qt.ItemDataRole.UserRole)
            if not icons:
                return False

            mouse_x = event.pos().x() - option.rect.x() - 2
            icon_idx = mouse_x // (self.ICON_SIZE + self.ICON_SPACING)

            if 0 <= icon_idx < len(icons):
                tooltip = icons[icon_idx].get("tooltip", "")
                if tooltip and self._tooltip_widget:
                    try:
                        gp = event.globalPos()
                    except AttributeError:
                        gp = QPoint()
                    self._tooltip_widget.show_text(tooltip, gp)
                    return True

        if event.type() == QEvent.Type.Leave and self._tooltip_widget:
            self._tooltip_widget.hide()

        return super().helpEvent(event, view, option, index)
