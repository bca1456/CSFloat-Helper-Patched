# modules/theme.py


class Theme:
    """Единая цветовая схема приложения.

    Все визуальные параметры собраны здесь. Для смены темы
    достаточно создать подкласс и переопределить нужные атрибуты.
    """

    # === Основные цвета ===
    PRIMARY = "#4147D5"
    PRIMARY_HOVER = "#3137B5"
    PRIMARY_PRESSED = "#2127A5"
    PRIMARY_LIGHT = "rgba(65, 71, 213, 0.1)"
    PRIMARY_MEDIUM = "rgba(65, 71, 213, 0.9)"

    # === Фон ===
    BG_WHITE = "#FFFFFF"
    BG_LIGHT = "#F5F9FC"
    BG_HOVER = "#EBF3FA"
    BG_SELECTION = "#E3F0FF"
    BG_TRANSPARENT = "transparent"

    # === Границы ===
    BORDER_INPUT = "#D1B3FF"
    BORDER_LIGHT = "#C5D9F1"
    BORDER_GRID = "#E6E0F2"

    # === Текст ===
    TEXT_PRIMARY = "#000000"
    TEXT_SECONDARY = "#666666"
    TEXT_PLACEHOLDER = "#A0A0A0"
    TEXT_WHITE = "white"

    # === Состояния ===
    HOVER_GRAY = "#E0E0E0"
    TOGGLE_OFF_BG = "#CCCCCC"
    TOGGLE_OFF_BORDER = "#999999"
    ERROR = "#FF4444"

    # === Тень кнопок (RGB, без альфа) ===
    SHADOW_RGB = (65, 71, 213)

    # === Шрифт ===
    FONT_FAMILY = "Oswald"
    FONT_SIZE = 11
    FONT_SIZE_SMALL = 10
    FONT_SIZE_TINY = 9
    FONT_SIZE_LARGE = 14

    # === Скругления ===
    RADIUS = 5
    RADIUS_SMALL = 3
    RADIUS_TOOLTIP = 4
    RADIUS_TOGGLE = 12
    RADIUS_RARITY = 10
    RADIUS_AVATAR = 14

    # =========================================================================
    # Готовые стили — генерируются из атрибутов выше
    # =========================================================================

    @classmethod
    def input_style(cls):
        """QLineEdit — фильтры, ввод цены."""
        return f"""
            QLineEdit {{
                border: 1px solid {cls.BORDER_INPUT};
                border-radius: {cls.RADIUS}px;
                padding: 2px 10px 2px 5px;
            }}
            QLineEdit:focus {{ border: 1px solid {cls.PRIMARY}; }}
        """

    @classmethod
    def input_style_with_placeholder(cls):
        """QLineEdit с кастомным placeholder (коллекции)."""
        return f"""
            QLineEdit {{
                border: 1px solid {cls.BORDER_INPUT};
                border-radius: {cls.RADIUS}px;
                padding-left: 5px;
                padding-right: 28px;
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
                background-color: {cls.BG_WHITE};
                color: {cls.PRIMARY};
                border: 1px solid {cls.BORDER_LIGHT};
                border-radius: {cls.RADIUS}px;
                font-family: {cls.FONT_FAMILY};
                font-weight: bold;
                font-size: {cls.FONT_SIZE_SMALL}pt;
                padding: 5px 15px;
                min-width: 80px;
            }}
            QPushButton:hover {{ background-color: {cls.BG_HOVER}; }}
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
                background-color: palette(base);
                gridline-color: {cls.BORDER_GRID};
                selection-background-color: {cls.BG_SELECTION};
                selection-color: {cls.TEXT_PRIMARY};
                color: palette(text);
            }}
            QTableWidget::item {{ padding-left: 0px; }}
            QTableWidget::item:selected {{ background-color: {cls.BG_SELECTION}; }}
            QTableWidget::item:selected:!active {{ background-color: {cls.BG_SELECTION}; }}
            QTableWidget::item:focus {{ outline: none; }}
            QHeaderView::section:vertical {{ font-weight: normal; }}
        """

    @classmethod
    def table_header_style(cls):
        """Стиль заголовка таблицы."""
        return f"""
            QHeaderView::section {{
                font-family: '{cls.FONT_FAMILY}';
                font-size: {cls.FONT_SIZE}pt;
                font-weight: normal;
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
    def toggle_on(cls):
        """ToggleSwitch — включён."""
        return f"""
            QPushButton {{
                background-color: {cls.PRIMARY};
                border: 2px solid {cls.PRIMARY_HOVER};
                border-radius: {cls.RADIUS_TOGGLE}px;
                text-align: right;
                padding-right: 5px;
                color: {cls.TEXT_WHITE};
                font-weight: bold;
                font-size: {cls.FONT_SIZE_TINY}pt;
            }}
        """

    @classmethod
    def toggle_off(cls):
        """ToggleSwitch — выключен."""
        return f"""
            QPushButton {{
                background-color: {cls.TOGGLE_OFF_BG};
                border: 2px solid {cls.TOGGLE_OFF_BORDER};
                border-radius: {cls.RADIUS_TOGGLE}px;
                text-align: left;
                padding-left: 5px;
                color: {cls.TEXT_SECONDARY};
                font-weight: bold;
                font-size: {cls.FONT_SIZE_TINY}pt;
            }}
        """

    @classmethod
    def condition_button(cls, position="middle"):
        """Кнопка состояния (FN/MW/FT/WW/BS).

        position: "first", "middle", "last"
        """
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
                background-color: {cls.BG_WHITE};
                color: {cls.PRIMARY};
            }}
            QPushButton:checked {{ background-color: {cls.PRIMARY}; color: {cls.BG_WHITE}; }}
            QPushButton:hover {{ background-color: {cls.HOVER_GRAY}; }}
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
                background-color: rgba(49, 55, 181, 1);
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
