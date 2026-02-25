# modules/ui_tab1/custom_widgets.py

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QDialog, QFormLayout,
    QPushButton, QHBoxLayout, QLineEdit
)
from PyQt6.QtCore import Qt, QPoint, pyqtSignal, pyqtProperty, QPropertyAnimation, QRectF
from PyQt6.QtGui import QCursor, QFont, QPainter, QPainterPath, QColor, QBrush, QPen

from modules.theme import Theme
from modules.utils import key_id


class CustomToolTip(QFrame):
    """Универсальный кастомный тултип."""

    def __init__(self):
        super().__init__(None, Qt.WindowType.ToolTip)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)

        self.label = QLabel(self)
        self.label.setText("")
        lay.addWidget(self.label)

        self.setStyleSheet(Theme.tooltip_style())
        self.hide()

    def show_text(self, text: str, global_pos):
        """Показать tooltip с текстом в указанной позиции."""
        self.label.setText(text)
        self.adjustSize()
        self.move(global_pos + QPoint(12, 16))
        self.show()

    def move_to_cursor(self):
        """Переместить tooltip к курсору."""
        if self.isVisible():
            self.move(QCursor.pos() + QPoint(12, 16))


class ToggleSwitch(QPushButton):
    """Кастомный свайпер-переключатель."""

    toggled_signal = pyqtSignal(bool)

    def __init__(self, parent=None, show_text=True, size=None):
        super().__init__(parent)
        self.setCheckable(True)
        self._show_text = show_text
        w, h = size or (50, 24)
        self.setFixedSize(w, h)
        self._radius = h / 2
        self._circle_position = 2.0
        self.clicked.connect(self._on_click)

    @pyqtProperty(float)
    def circle_position(self):
        return self._circle_position

    @circle_position.setter
    def circle_position(self, pos):
        self._circle_position = pos
        self.update()

    def _on_click(self):
        self.toggled_signal.emit(self.isChecked())
        self._animate()

    def setChecked(self, checked: bool):
        super().setChecked(checked)
        self._circle_position = (self.width() - self.height() + 2) if checked else 2.0
        self.update()

    def _animate(self):
        self.anim = QPropertyAnimation(self, b"circle_position")
        self.anim.setDuration(150)
        self.anim.setEndValue(float(self.width() - self.height() + 2) if self.isChecked() else 2.0)
        self.anim.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self.isChecked():
            bg_color = QColor(Theme.PRIMARY)
            circle_color = QColor(Theme.TEXT_WHITE)
            text = "ON" if self._show_text else ""
        else:
            if Theme.current_theme == "dark":
                bg_color = QColor(Theme.BG_LIGHT).lighter(150)
                circle_color = QColor(Theme.TEXT_SECONDARY)
            else:
                bg_color = QColor(Theme.TEXT_SECONDARY)
                circle_color = QColor(Theme.TEXT_WHITE)
            text = "OFF" if self._show_text else ""

        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, self.width(), self.height()), self._radius, self._radius)
        painter.fillPath(path, QBrush(bg_color))

        circle_rect = QRectF(self._circle_position, 2.0, self.height() - 4.0, self.height() - 4.0)
        painter.setBrush(QBrush(circle_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(circle_rect)

        if text:
            painter.setPen(QPen(QColor(Theme.TEXT_WHITE if self.isChecked() else Theme.TEXT_SECONDARY)))
            font = self.font()
            font.setPointSize(Theme.FONT_SIZE_TINY)
            font.setBold(True)
            painter.setFont(font)
            
            if self.isChecked():
                painter.drawText(QRectF(0, 0, self.width() - self.height() + 2, self.height()), Qt.AlignmentFlag.AlignCenter, text)
            else:
                painter.drawText(QRectF(self.height() - 2, 0, self.width() - self.height() + 2, self.height()), Qt.AlignmentFlag.AlignCenter, text)


class AccountSettingsDialog(QDialog):
    """Настройка аккаунта"""

    settings_saved = pyqtSignal(str, bool, str)

    def __init__(self, api_key: str, settings, parent=None):
        super().__init__(parent)
        self.api_key = api_key
        self.settings = settings

        self.setWindowTitle("Account Settings")
        self.setMinimumWidth(350)
        self.setModal(True)
        Theme.apply_titlebar_theme(self)

        self.current_keep_online = self.settings.value(
            f"account_{key_id(api_key)}_keep_online", False, type=bool
        )
        self.current_description = self.settings.value(
            f"account_{key_id(api_key)}_description", "", type=str
        )

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        label_font = QFont(Theme.FONT_FAMILY, Theme.FONT_SIZE)

        keep_online_layout = QHBoxLayout()
        keep_online_label = QLabel("Keep Online:")
        keep_online_label.setFont(label_font)

        self.keep_online_switch = ToggleSwitch()
        self.keep_online_switch.setChecked(self.current_keep_online)

        keep_online_layout.addWidget(keep_online_label)
        keep_online_layout.addStretch()
        keep_online_layout.addWidget(self.keep_online_switch)

        layout.addLayout(keep_online_layout)

        self.description_input = QLineEdit()
        self.description_input.setPlaceholderText("Trade Description")
        self.description_input.setText(self.current_description)
        self.description_input.setFont(QFont(Theme.FONT_FAMILY, Theme.FONT_SIZE_SMALL))
        self.description_input.textChanged.connect(self._validate_description)
        self.description_input.setStyleSheet(Theme.input_dialog_style())
        layout.addWidget(self.description_input)

        counter_layout = QHBoxLayout()
        counter_layout.addStretch()
        self.char_counter = QLabel()
        self.char_counter.setFont(QFont(Theme.FONT_FAMILY, Theme.FONT_SIZE_TINY))
        self.char_counter.setStyleSheet(Theme.text_color(Theme.TEXT_SECONDARY))
        counter_layout.addWidget(self.char_counter)
        layout.addSpacing(-17)
        layout.addLayout(counter_layout)
        self._update_counter()

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(80, 28)
        cancel_btn.setStyleSheet(Theme.button_secondary())
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("Save")
        save_btn.setFixedSize(80, 28)
        save_btn.setStyleSheet(Theme.button_primary())
        save_btn.clicked.connect(self._save_settings)
        save_btn.setDefault(True)

        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(save_btn)
        button_layout.addStretch()

        layout.addLayout(button_layout)

    def _validate_description(self):
        """Валидация по байтам (32 байта UTF-8)."""
        text = self.description_input.text()
        byte_count = len(text.encode('utf-8'))
        is_valid = byte_count <= 32

        if not is_valid:
            self.description_input.setStyleSheet(Theme.input_error_style())
        else:
            self.description_input.setStyleSheet(Theme.input_dialog_style())

        self._update_counter()
        return is_valid

    def _update_counter(self):
        """Обновить счетчик байтов."""
        text = self.description_input.text()
        byte_count = len(text.encode('utf-8'))

        color = Theme.ERROR if byte_count > 32 else Theme.TEXT_SECONDARY
        self.char_counter.setStyleSheet(Theme.text_color(color))
        self.char_counter.setText(f"{byte_count}/32 bytes")

    def _save_settings(self):
        """Сохранить настройки."""
        if not self._validate_description():
            return

        keep_online = self.keep_online_switch.isChecked()
        description = self.description_input.text()

        self.settings.setValue(f"account_{key_id(self.api_key)}_keep_online", keep_online)
        self.settings.setValue(f"account_{key_id(self.api_key)}_description", description)

        self.settings.sync()

        self.settings_saved.emit(self.api_key, keep_online, description)

        self.accept()
