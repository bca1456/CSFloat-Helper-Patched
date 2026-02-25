# modules/messagebox.py

from PyQt6.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, \
    QDialogButtonBox
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtCore import Qt
import os

from modules.theme import Theme


def styled_message_box(parent=None, title="", text="", icon=QMessageBox.Icon.Information,
                       buttons=QMessageBox.StandardButton.Ok, detailed_text=""):
    """Создает стилизованный QMessageBox."""
    msg_box = QMessageBox(parent)
    msg_box.setWindowTitle(title)
    msg_box.setText(text)
    msg_box.setIcon(icon)
    msg_box.setStandardButtons(buttons)

    if detailed_text:
        msg_box.setDetailedText(detailed_text)

    font = QFont(Theme.FONT_FAMILY)
    font.setPointSize(Theme.FONT_SIZE)
    font.setWeight(QFont.Weight.Normal)
    msg_box.setFont(font)

    msg_box.setStyleSheet(Theme.messagebox_style())

    for child in msg_box.children():
        if isinstance(child, QDialogButtonBox):
            child.setCenterButtons(True)
            break

    Theme.apply_titlebar_theme(msg_box)
    return msg_box


def warning(parent, title, text):
    """Стилизованное предупреждение."""
    return styled_message_box(parent, title, text, QMessageBox.Icon.Warning).exec()


def information(parent, title, text):
    """Стилизованное информационное сообщение."""
    return styled_message_box(parent, title, text, QMessageBox.Icon.Information).exec()


def critical(parent, title, text):
    """Стилизованное сообщение об ошибке."""
    return styled_message_box(parent, title, text, QMessageBox.Icon.Critical).exec()


def question(parent, title, text):
    """Стилизованный вопрос."""
    return styled_message_box(parent, title, text, QMessageBox.Icon.Question,
                              QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No).exec()


def show_warning(parent, title, text):
    return warning(parent, title, text)


def show_information(parent, title, text):
    return information(parent, title, text)


def show_error(parent, title, text):
    return critical(parent, title, text)
