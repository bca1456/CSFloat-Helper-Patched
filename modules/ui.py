# modules/ui.py

import os
from PyQt6.QtWidgets import QMainWindow, QApplication
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtCore import QThreadPool, Qt, QSettings
from modules.theme import Theme
from modules.ui_tab1 import Tab1


class SteamInventoryApp(QMainWindow):
    def __init__(self, api_keys):
        super().__init__()
        self.api_keys = api_keys
        self.threadpool = QThreadPool()
        self.iconpath = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "utils", "icons")
        )
        self.settings = QSettings("MyCompany", "SteamInventoryApp")
        self.initUI()

    def initUI(self):
        appfont = QFont(Theme.FONT_FAMILY)
        appfont.setPointSize(Theme.FONT_SIZE)
        appfont.setWeight(QFont.Weight.Normal)
        self.setFont(appfont)

        self.setWindowIcon(QIcon(os.path.join(self.iconpath, "steam.png")))
        self.setWindowTitle("CSFloat Helper")

        self.tab1 = Tab1(self.api_keys, self.iconpath, parent=self)
        self.setCentralWidget(self.tab1)

        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        fixed_width = 880
        fixed_height = 782
        self.setFixedWidth(fixed_width)
        self.setMinimumHeight(fixed_height)

        # Загружаем сохранённую высоту и позицию
        saved_height = self.settings.value("window_height", fixed_height, type=int)
        saved_x = self.settings.value("window_x", -1, type=int)
        saved_y = self.settings.value("window_y", -1, type=int)

        if saved_height >= fixed_height:
            self.resize(fixed_width, saved_height)
        else:
            self.resize(fixed_width, fixed_height)

        if saved_x != -1 and saved_y != -1:
            if self.is_position_valid(saved_x, saved_y):
                self.move(saved_x, saved_y)
            else:
                self.center_window()
        else:
            self.center_window()

        self.show()
        self.load_data()

    def is_position_valid(self, x, y):
        """Проверяет, что позиция окна валидна (не выходит за пределы экрана)"""
        screens = QApplication.screens()

        for screen in screens:
            screen_geometry = screen.availableGeometry()

            if (screen_geometry.x() <= x <= screen_geometry.x() + screen_geometry.width() and
                    screen_geometry.y() <= y <= screen_geometry.y() + screen_geometry.height()):
                return True

        return False

    def center_window(self):
        """Центрирует окно на экране."""
        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()

        window_size = self.size()

        x = screen_geometry.x() + (screen_geometry.width() - window_size.width()) // 2
        y = screen_geometry.y() + (screen_geometry.height() - window_size.height()) // 2

        self.move(x, y)

    def load_data(self):
        self.tab1.load_data(self.threadpool)

    def closeEvent(self, event):
        # Останавливаем фоновые потоки
        self.tab1.cleanup()

        # Сохраняем настройки перед закрытием
        self.tab1.save_column_widths()

        # Сохраняем текущие размеры и позицию окна
        self.settings.setValue("window_height", self.height())
        self.settings.setValue("window_x", self.x())
        self.settings.setValue("window_y", self.y())

        # Синхронизируем настройки
        self.settings.sync()

        event.accept()