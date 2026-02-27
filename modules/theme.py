# modules/theme.py


_LIGHT_PALETTE = {
    "PRIMARY": "#4147D5",
    "PRIMARY_HOVER": "#3137B5",
    "PRIMARY_PRESSED": "#2127A5",
    "PRIMARY_LIGHT": "rgba(65, 71, 213, 0.1)",
    "PRIMARY_MEDIUM": "rgba(65, 71, 213, 0.9)",
    "BG_WHITE": "#FFFFFF",
    "BG_LIGHT": "#F5F9FC",
    "BG_HOVER": "#EBF3FA",
    "BG_SELECTION": "#E3F0FF",
    "BORDER_INPUT": "#D1B3FF",
    "BORDER_LIGHT": "#C5D9F1",
    "BORDER_GRID": "#E6E0F2",
    "TEXT_PRIMARY": "#000000",
    "TEXT_SECONDARY": "#666666",
    "TEXT_PLACEHOLDER": "#A0A0A0",
    "TEXT_WHITE": "white",
    "HOVER_GRAY": "#E0E0E0",
    "ERROR": "#FF4444",
    "SHADOW_RGB": (65, 71, 213),
}

_DARK_PALETTE = {
    "PRIMARY": "#F5A623",
    "PRIMARY_HOVER": "#FFB74D",
    "PRIMARY_PRESSED": "#F57C00",
    "PRIMARY_LIGHT": "rgba(245, 166, 35, 0.15)",
    "PRIMARY_MEDIUM": "rgba(245, 166, 35, 0.8)",
    "BG_WHITE": "#16181D",
    "BG_LIGHT": "#1E2028",
    "BG_HOVER": "#2A2D38",
    "BG_SELECTION": "#3D2E1A",
    "BORDER_INPUT": "#343846",
    "BORDER_LIGHT": "#2A2D38",
    "BORDER_GRID": "#232630",
    "TEXT_PRIMARY": "#E6E8F0",
    "TEXT_SECONDARY": "#8A91A6",
    "TEXT_PLACEHOLDER": "#5B6178",
    "TEXT_WHITE": "#FFFFFF",
    "HOVER_GRAY": "#2A2D38",
    "ERROR": "#FF5555",
    "SHADOW_RGB": (245, 166, 35),
}

_PALETTES = {"light": _LIGHT_PALETTE, "dark": _DARK_PALETTE}


class Theme:
    """Единая цветовая схема приложения.

    Переключение темы: Theme.set_theme("light") / Theme.set_theme("dark").
    После переключения все @classmethod стили автоматически используют новые цвета.
    """

    current_theme = "dark"

    # Цвета (перезаписываются в set_theme)
    PRIMARY = _DARK_PALETTE["PRIMARY"]
    PRIMARY_HOVER = _DARK_PALETTE["PRIMARY_HOVER"]
    PRIMARY_PRESSED = _DARK_PALETTE["PRIMARY_PRESSED"]
    PRIMARY_LIGHT = _DARK_PALETTE["PRIMARY_LIGHT"]
    PRIMARY_MEDIUM = _DARK_PALETTE["PRIMARY_MEDIUM"]

    BG_WHITE = _DARK_PALETTE["BG_WHITE"]
    BG_LIGHT = _DARK_PALETTE["BG_LIGHT"]
    BG_HOVER = _DARK_PALETTE["BG_HOVER"]
    BG_SELECTION = _DARK_PALETTE["BG_SELECTION"]
    BG_TRANSPARENT = "transparent"

    BORDER_INPUT = _DARK_PALETTE["BORDER_INPUT"]
    BORDER_LIGHT = _DARK_PALETTE["BORDER_LIGHT"]
    BORDER_GRID = _DARK_PALETTE["BORDER_GRID"]

    TEXT_PRIMARY = _DARK_PALETTE["TEXT_PRIMARY"]
    TEXT_SECONDARY = _DARK_PALETTE["TEXT_SECONDARY"]
    TEXT_PLACEHOLDER = _DARK_PALETTE["TEXT_PLACEHOLDER"]
    TEXT_WHITE = _DARK_PALETTE["TEXT_WHITE"]

    HOVER_GRAY = _DARK_PALETTE["HOVER_GRAY"]
    ERROR = _DARK_PALETTE["ERROR"]

    SHADOW_RGB = _DARK_PALETTE["SHADOW_RGB"]

    # === Шрифт (не зависит от темы) ===
    FONT_FAMILY = "Oswald"
    FONT_SIZE = 11
    FONT_SIZE_SMALL = 10
    FONT_SIZE_TINY = 9
    FONT_SIZE_LARGE = 14

    # === Скругления ===
    RADIUS = 5
    RADIUS_SMALL = 3
    RADIUS_TOOLTIP = 4
    RADIUS_RARITY = 10
    RADIUS_AVATAR = 14

    @classmethod
    def set_theme(cls, name):
        """Переключить тему. name: 'light' или 'dark'."""
        palette = _PALETTES.get(name, _DARK_PALETTE)
        for attr, value in palette.items():
            setattr(cls, attr, value)
        cls.current_theme = name

    @staticmethod
    def apply_titlebar_theme(widget):
        """Применяет тему к titlebar окна (Windows DWM)."""
        import sys
        if sys.platform != "win32":
            return
        try:
            import ctypes
            hwnd = int(widget.winId())
            is_dark = 1 if Theme.current_theme == "dark" else 0
            val = ctypes.c_int(is_dark)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(val), ctypes.sizeof(val))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(val), ctypes.sizeof(val))
        except Exception:
            pass

    # =========================================================================
    # Готовые стили
    # =========================================================================

    @classmethod
    def global_style(cls):
        return f"""
            QMainWindow, QDialog, QMessageBox {{
                background-color: {cls.BG_WHITE};
            }}
            QWidget {{
                color: {cls.TEXT_PRIMARY};
            }}
            QLabel, QCheckBox, QRadioButton, QGroupBox, QToolTip {{
                color: {cls.TEXT_PRIMARY};
            }}
            QListView {{
                background-color: {cls.BG_LIGHT};
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER_LIGHT};
            }}
            QListView::item:selected {{
                background-color: {cls.BG_SELECTION};
            }}
            QToolTip {{
                background-color: {cls.BG_HOVER};
                border: 1px solid {cls.BORDER_LIGHT};
                border-radius: {cls.RADIUS_SMALL}px;
                padding: 4px;
            }}
            QScrollBar:vertical {{
                background-color: transparent;
                width: 12px;
                margin: 0px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background-color: {cls.BORDER_INPUT};
                min-height: 20px;
                border-radius: 3px;
                margin: 2px 3px;
                border: none;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {cls.PRIMARY};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
                border: none;
                background: none;
                subcontrol-origin: margin;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
                border: none;
            }}
            QScrollBar:horizontal {{
                background-color: transparent;
                height: 12px;
                margin: 0px;
                border: none;
            }}
            QScrollBar::handle:horizontal {{
                background-color: {cls.BORDER_INPUT};
                min-width: 20px;
                border-radius: 3px;
                margin: 3px 2px;
                border: none;
            }}
            QScrollBar::handle:horizontal:hover {{
                background-color: {cls.PRIMARY};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
                border: none;
                background: none;
                subcontrol-origin: margin;
            }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: none;
                border: none;
            }}
            QAbstractScrollArea::corner {{
                background-color: {cls.BG_WHITE};
            }}
        """

    @classmethod
    def input_style(cls):
        """QLineEdit — фильтры, ввод цены."""
        return f"""
            QLineEdit {{
                background-color: {cls.BG_LIGHT};
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER_INPUT};
                border-radius: {cls.RADIUS}px;
                padding: 0px 10px 2px 5px;
            }}
            QLineEdit:focus {{ border: 1px solid {cls.PRIMARY}; }}
        """

    @classmethod
    def input_style_with_placeholder(cls):
        """QLineEdit с кастомным placeholder (коллекции)."""
        return f"""
            QLineEdit {{
                background-color: {cls.BG_LIGHT};
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER_INPUT};
                border-radius: {cls.RADIUS}px;
                padding: 0px 28px 2px 5px;
                font-size: {cls.FONT_SIZE}pt;
            }}
            QLineEdit::placeholder {{
                color: {cls.TEXT_PLACEHOLDER};
                font-size: {cls.FONT_SIZE_SMALL}pt;
                font-family: {cls.FONT_FAMILY};
            }}
            QLineEdit:focus {{
                border: 1px solid {cls.PRIMARY};
            }}
        """

    @classmethod
    def input_error_style(cls):
        """QLineEdit в состоянии ошибки."""
        return f"""
            QLineEdit {{
                background-color: {cls.BG_LIGHT};
                color: {cls.TEXT_PRIMARY};
                border: 2px solid {cls.ERROR};
                border-radius: {cls.RADIUS}px;
                padding: 5px;
            }}
        """

    @classmethod
    def input_dialog_style(cls):
        """QLineEdit в диалоговых окнах (с увеличенным padding)."""
        return f"""
            QLineEdit {{
                background-color: {cls.BG_LIGHT};
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER_INPUT};
                border-radius: {cls.RADIUS}px;
                padding: 5px;
            }}
            QLineEdit:focus {{
                border: 1px solid {cls.PRIMARY};
            }}
        """

    @classmethod
    def button_primary(cls):
        """Основная кнопка — подтверждение, сохранение."""
        return f"""
            QPushButton {{
                background-color: {cls.PRIMARY};
                color: {cls.TEXT_WHITE};
                border: none;
                border-radius: {cls.RADIUS}px;
                font-family: {cls.FONT_FAMILY};
                font-weight: bold;
                font-size: {cls.FONT_SIZE_SMALL}pt;
                padding: 5px 15px;
                min-width: 80px;
            }}
            QPushButton:hover {{ background-color: {cls.PRIMARY_HOVER}; }}
            QPushButton:pressed {{ background-color: {cls.PRIMARY_PRESSED}; }}
        """

    @classmethod
    def button_secondary(cls):
        """Вторичная кнопка — отмена."""
        return f"""
            QPushButton {{
                background-color: {cls.BG_LIGHT};
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER_INPUT};
                border-radius: {cls.RADIUS}px;
                font-family: {cls.FONT_FAMILY};
                font-weight: bold;
                font-size: {cls.FONT_SIZE_SMALL}pt;
                padding: 5px 15px;
                min-width: 80px;
            }}
            QPushButton:hover {{ background-color: {cls.HOVER_GRAY}; }}
        """

    @classmethod
    def button_icon(cls):
        """Кнопка-иконка без рамки (sell, delist, etc.)."""
        return "border: none;"

    @classmethod
    def dropdown_button(cls):
        """Кнопка-dropdown для фильтра коллекций."""
        return f"""
            QPushButton {{
                background-color: {cls.BG_TRANSPARENT};
                color: {cls.PRIMARY};
                border: none;
                font-size: {cls.FONT_SIZE_LARGE}pt;
                font-weight: bold;
                padding-bottom: 2px;
            }}
            QPushButton:hover {{
                background-color: {cls.PRIMARY_LIGHT};
                border-radius: {cls.RADIUS_SMALL}px;
            }}
        """

    @classmethod
    def scroll_area(cls):
        """QScrollArea в диалогах."""
        return f"""
            QScrollArea {{
                border: 1px solid {cls.BORDER_LIGHT};
                border-radius: {cls.RADIUS}px;
                background-color: {cls.BG_LIGHT};
            }}
            QScrollArea > QWidget > QWidget {{
                background-color: transparent;
            }}
        """

    @classmethod
    def item_label(cls):
        """Подпись предмета в диалогах подтверждения."""
        return f"padding: 2px 4px; font-size: {cls.FONT_SIZE_SMALL}pt; font-family: '{cls.FONT_FAMILY}';"

    @classmethod
    def messagebox_style(cls):
        """Стиль для QMessageBox."""
        return f"""
            QMessageBox {{
                background-color: {cls.BG_WHITE};
                font-family: {cls.FONT_FAMILY};
                font-size: {cls.FONT_SIZE}pt;
                color: {cls.TEXT_PRIMARY};
            }}
            QMessageBox QLabel {{
                color: {cls.TEXT_PRIMARY};
                font-family: {cls.FONT_FAMILY};
                font-size: {cls.FONT_SIZE}pt;
            }}
            QMessageBox QPushButton {{
                background-color: {cls.PRIMARY};
                color: {cls.TEXT_WHITE};
                border: none;
                border-radius: {cls.RADIUS}px;
                font-family: {cls.FONT_FAMILY};
                font-weight: bold;
                font-size: {cls.FONT_SIZE_SMALL}pt;
                padding: 5px 15px;
                min-width: 80px;
            }}
            QMessageBox QPushButton:hover {{ background-color: {cls.PRIMARY_HOVER}; }}
            QMessageBox QPushButton:pressed {{ background-color: {cls.PRIMARY_PRESSED}; }}
        """

    @classmethod
    def table_style(cls):
        """Стиль для QTableWidget."""
        return f"""
            QTableWidget {{
                background-color: {cls.BG_WHITE};
                alternate-background-color: {cls.BG_LIGHT};
                gridline-color: {cls.BORDER_GRID};
                selection-background-color: {cls.BG_SELECTION};
                selection-color: {cls.TEXT_PRIMARY};
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER_LIGHT};
                border-radius: {cls.RADIUS}px;
            }}
            QTableView {{
                background-color: {cls.BG_WHITE};
            }}
            QTableWidget::item {{ padding-left: 5px; }}
            QTableWidget::item:selected {{ background-color: {cls.BG_SELECTION}; }}
            QTableWidget::item:selected:!active {{ background-color: {cls.BG_SELECTION}; }}
            QTableWidget::item:focus {{ outline: none; }}
            QHeaderView::section:vertical {{
                font-weight: normal;
                background-color: {cls.BG_LIGHT};
                color: {cls.TEXT_SECONDARY};
                border: none;
                border-right: 1px solid {cls.BORDER_GRID};
                padding-right: 4px;
                padding-left: 2px;
            }}
            QTableCornerButton::section {{
                background-color: {cls.BG_LIGHT};
                border: none;
                border-right: 1px solid {cls.BORDER_GRID};
                border-bottom: 2px solid {cls.BORDER_GRID};
            }}
        """

    @classmethod
    def table_header_style(cls):
        """Стиль заголовка таблицы."""
        return f"""
            QHeaderView {{
                background-color: {cls.BG_LIGHT};
                border: none;
            }}
            QHeaderView::section {{
                background-color: {cls.BG_LIGHT};
                color: {cls.PRIMARY};
                font-family: '{cls.FONT_FAMILY}';
                font-size: {cls.FONT_SIZE}pt;
                font-weight: normal;
                border: none;
                border-right: 1px solid {cls.BORDER_GRID};
                border-bottom: 2px solid {cls.BORDER_GRID};
                padding: 0px 4px;
            }}
        """

    @classmethod
    def table_header_color(cls):
        """Цвет текста в заголовке таблицы."""
        return f"color: {cls.PRIMARY};"

    @classmethod
    def tooltip_style(cls):
        """Кастомный тултип."""
        return (
            f"QFrame {{\n"
            f"  background-color: {cls.BG_HOVER};\n"
            f"  border: 1px solid {cls.BORDER_LIGHT};\n"
            f"  border-radius: {cls.RADIUS_TOOLTIP}px;\n"
            f"}}\n"
            f"QLabel {{\n"
            f"  color: {cls.TEXT_PRIMARY};\n"
            f"  background: {cls.BG_TRANSPARENT};\n"
            f"  font-family: '{cls.FONT_FAMILY}';\n"
            f"  font-size: {cls.FONT_SIZE_SMALL}pt;\n"
            f"}}\n"
        )

    @classmethod
    def condition_button(cls, position="middle"):
        """Кнопка состояния (FN/MW/FT/WW/BS)."""
        if position == "first":
            radius = (
                f"border-top-left-radius: {cls.RADIUS}px;\n"
                f"                    border-bottom-left-radius: {cls.RADIUS}px;"
            )
        elif position == "last":
            radius = (
                f"border-top-right-radius: {cls.RADIUS}px;\n"
                f"                    border-bottom-right-radius: {cls.RADIUS}px;"
            )
        else:
            radius = ""

        return f"""
            QPushButton {{
                border: 1px solid {cls.BORDER_INPUT};
                {radius}
                background-color: {cls.BG_LIGHT};
                color: {cls.TEXT_SECONDARY};
                padding-bottom: 1px;
            }}
            QPushButton:checked {{ background-color: {cls.PRIMARY}; color: {cls.BG_WHITE}; border: 1px solid {cls.PRIMARY}; padding-bottom: 1px; }}
            QPushButton:hover:!checked {{ background-color: {cls.HOVER_GRAY}; color: {cls.TEXT_PRIMARY}; }}
        """

    @classmethod
    def rarity_button(cls, color):
        """Кнопка редкости с динамическим QColor."""
        return f"""
            QPushButton {{
                border: 3px solid {color.name()};
                border-radius: {cls.RADIUS_RARITY}px;
                background-color: {color.lighter(150).name()};
                padding-left: 3px;
            }}
            QPushButton:checked {{
                background-color: {color.darker(135).name()};
                padding-left: 0px;
            }}
        """

    @classmethod
    def transparent_widget(cls):
        """Прозрачный фон для виджетов в ячейках таблицы."""
        return f"background: {cls.BG_TRANSPARENT};"

    @classmethod
    def text_color(cls, color):
        """Цвет текста (для счётчиков, лейблов)."""
        return f"color: {color};"

    @classmethod
    def avatar_container(cls):
        """Контейнер аватара в диалоге user info."""
        return f"""
            QWidget {{
                background: {cls.BG_TRANSPARENT};
                border: 1px solid {cls.BORDER_INPUT};
                border-radius: {cls.RADIUS}px;
            }}
        """

    @classmethod
    def settings_button_icon(cls):
        """Кнопка настроек поверх аватара (с иконкой)."""
        return f"""
            QPushButton {{
                background: {cls.BG_TRANSPARENT};
                border: none;
                border-radius: {cls.RADIUS_AVATAR}px;
            }}
            QPushButton:hover {{
                background-color: {cls.PRIMARY_LIGHT};
            }}
        """

    @classmethod
    def settings_button_text(cls):
        """Кнопка настроек поверх аватара (текстовый fallback)."""
        return f"""
            QPushButton {{
                background-color: {cls.PRIMARY_MEDIUM};
                border: 1px solid {cls.BG_WHITE};
                border-radius: {cls.RADIUS_AVATAR}px;
                color: {cls.TEXT_WHITE};
                font-size: 12pt;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {cls.PRIMARY_PRESSED};
            }}
        """

    @classmethod
    def separator_gradient(cls):
        """Вертикальный разделитель между аккаунтами."""
        return """
            background: qlineargradient(
                x1:0, y1:0, x2:0, y2:1,
                stop:0 rgba(189, 189, 189, 0),
                stop:0.5 rgba(189, 189, 189, 1),
                stop:1 rgba(189, 189, 189, 0)
            );
        """
