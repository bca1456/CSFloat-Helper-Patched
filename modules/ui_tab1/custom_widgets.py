# modules/ui_tab1/custom_widgets.py

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QDialog, QFormLayout,
    QPushButton, QHBoxLayout, QLineEdit
)
from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtGui import QCursor, QFont

from modules.theme import Theme


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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(50, 24)
        self._update_style()
        self.clicked.connect(self._on_click)

    def _on_click(self):
        self._update_style()
        self.toggled_signal.emit(self.isChecked())

    def _update_style(self):
        if self.isChecked():
            self.setStyleSheet(Theme.toggle_on())
            self.setText("ON")
        else:
            self.setStyleSheet(Theme.toggle_off())
            self.setText("OFF")

    def setChecked(self, checked: bool):
        super().setChecked(checked)
        self._update_style()


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

        self.current_keep_online = self.settings.value(
            f"account/{api_key}/keep_online", False, type=bool
        )
        self.current_description = self.settings.value(
            f"account/{api_key}/description", "", type=str
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

        self.settings.setValue(f"account/{self.api_key}/keep_online", keep_online)
        self.settings.setValue(f"account/{self.api_key}/description", description)

        self.settings.sync()

        self.settings_saved.emit(self.api_key, keep_online, description)

        self.accept()
