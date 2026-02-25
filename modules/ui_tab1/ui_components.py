import os
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QPushButton,
    QTableWidget, QHeaderView, QAbstractItemView, QSizePolicy,
    QCompleter, QListView
)
from PyQt6.QtGui import QIcon, QFont
from PyQt6.QtCore import Qt, QSize

from modules.theme import Theme
from modules.models.columns import (
    COL_KEYCHAINS, COLUMN_COUNT, COLUMN_HEADERS, HIDDEN_COLUMNS,
)
from .constants import RARITY_COLOR_MAP, get_cached_collections, WEAR_CONDITIONS_MAP
from .animated_buttons import AnimatedButtonCombo


def create_filter_inputs(parent):
    """Создаёт фильтры по имени и стикерам."""
    name_filter = QLineEdit(parent)
    name_filter.setPlaceholderText("Filter by Name")
    name_filter.move(20, 20)
    name_filter.setFixedSize(150, 24)
    name_filter.setStyleSheet(Theme.input_style())

    sticker_filter = QLineEdit(parent)
    sticker_filter.setPlaceholderText("Filter by Sticker")
    sticker_filter.move(20, 54)
    sticker_filter.setFixedSize(150, 24)
    sticker_filter.setStyleSheet(Theme.input_style())

    return name_filter, sticker_filter


def create_float_filters(parent):
    """Создаёт фильтры по Float."""
    float_min = QLineEdit(parent)
    float_min.setPlaceholderText("Min Float")
    float_min.move(200, 20)
    float_min.setFixedSize(75, 24)
    float_min.setStyleSheet(Theme.input_style())

    float_max = QLineEdit(parent)
    float_max.setPlaceholderText("Max Float")
    float_max.move(305, 20)
    float_max.setFixedSize(75, 24)
    float_max.setStyleSheet(Theme.input_style())

    return float_min, float_max



def create_collection_filter(parent, apply_filters_fn):
    """Фильтр коллекций с умной кнопкой dropdown."""
    layout = QHBoxLayout()

    collection_edit = QLineEdit(parent)
    collection_edit.setPlaceholderText("Filter by Collections")
    collection_edit.setFixedSize(150, 24)
    collection_edit.setFont(parent.font())
    collection_edit.setStyleSheet(Theme.input_style_with_placeholder())

    completer = QCompleter(get_cached_collections(), parent)
    completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
    completer.setFilterMode(Qt.MatchFlag.MatchContains)
    completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    popup = QListView()
    popup.setFont(parent.font())
    completer.setPopup(popup)
    collection_edit.setCompleter(completer)

    def on_collection_selected(text):
        collection_edit.setText(text)
        collection_edit.setCursorPosition(0)
        apply_filters_fn()

    completer.activated.connect(on_collection_selected)
    collection_edit.textChanged.connect(apply_filters_fn)

    dropdown_button = QPushButton("▼", parent)
    dropdown_button.setFixedSize(24, 24)
    dropdown_button.setFont(parent.font())
    dropdown_button.setStyleSheet(Theme.dropdown_button())

    def smart_dropdown_action():
        if collection_edit.text():
            collection_edit.clear()
        else:
            collection_edit.completer().complete()

    def update_button_icon():
        dropdown_button.setText("✕" if collection_edit.text() else "▼")

    dropdown_button.clicked.connect(smart_dropdown_action)
    collection_edit.textChanged.connect(update_button_icon)

    layout.addWidget(collection_edit)
    layout.addWidget(dropdown_button)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    container = QWidget(parent)
    container.setLayout(layout)
    container.move(20, 88)
    container.setFixedSize(150, 24)

    return collection_edit, dropdown_button


def create_rarity_buttons(parent, on_toggled_fn):
    """Создаёт кнопки фильтрации по редкости."""
    buttons = []
    x_start = 200
    y_start = 88
    spacing = 3

    for rarity, color in RARITY_COLOR_MAP.items():
        button = QPushButton(parent)
        button.setCheckable(True)
        button.setFixedSize(20, 20)
        button.setStyleSheet(Theme.rarity_button(color))
        button.rarity = rarity
        button.toggled.connect(on_toggled_fn)
        button.move(x_start, y_start)
        buttons.append(button)
        x_start += button.width() + spacing

    return buttons


def create_condition_buttons(parent, on_toggled_fn):
    """Создаёт кнопки фильтрации по состоянию."""
    buttons = []
    labels = ["FN", "MW", "FT", "WW", "BS"]
    x = 200
    y = 54
    w = 36
    h = 24

    for i, label in enumerate(labels):
        button = QPushButton(label, parent)
        button.setCheckable(True)
        button.setFixedSize(w, h)

        if i == 0:
            position = "first"
        elif i == len(labels) - 1:
            position = "last"
        else:
            position = "middle"

        button.setStyleSheet(Theme.condition_button(position))
        button.move(x, y)
        button.wear_condition = WEAR_CONDITIONS_MAP[label]
        button.toggled.connect(on_toggled_fn)
        buttons.append(button)
        x += w

    return buttons


def change_icon_color(icon_path, color_hex):
    from PyQt6.QtGui import QImage, QPainter, QColor, QPixmap
    from PyQt6.QtCore import Qt

    image = QImage(icon_path)
    if image.isNull():
        return QPixmap()

    image = image.convertToFormat(QImage.Format.Format_ARGB32)
    color = QColor(color_hex)
    
    for y in range(image.height()):
        for x in range(image.width()):
            pixel = image.pixelColor(x, y)
            if pixel.alpha() > 0:
                color.setAlpha(pixel.alpha())
                image.setPixelColor(x, y, color)
                
    return QPixmap.fromImage(image)


def create_action_buttons(parent, icon_path, callbacks):
    """Создаёт кнопки действий и поле ввода цены.

    callbacks — dict с ключами: sell, change_price, delist, swap, user_info
    """
    price_input = QLineEdit(parent)
    price_input.setPlaceholderText("Price")
    price_input.move(410, 20)
    price_input.setFixedSize(75, 24)
    price_input.setStyleSheet(Theme.input_style())

    button_configs = [
        ("sell.png", 537, "Sell", callbacks["sell"]),
        ("change.png", 597, "Change price", callbacks["change_price"]),
        ("delist.png", 657, "Delist", callbacks["delist"]),
        ("swap.png", 717, "Relist", callbacks["swap"]),
        ("info.png", 777, "User info", callbacks["user_info"]),
    ]

    buttons = {}
    for icon_name, x_pos, tooltip, callback in button_configs:
        btn = AnimatedButtonCombo(parent)
        
        full_icon_path = os.path.join(icon_path, icon_name)
        colored_pixmap = change_icon_color(full_icon_path, Theme.PRIMARY)
        btn.setIcon(QIcon(colored_pixmap))
        
        btn.setIconSize(QSize(50, 50))
        btn.setFixedSize(50, 50)
        btn.move(x_pos, 20)
        btn.setStyleSheet(Theme.button_icon())
        btn.clicked.connect(callback)
        btn.tooltip_text = tooltip
        btn.setMouseTracking(True)
        btn.installEventFilter(parent)
        buttons[tooltip.lower().replace(" ", "_")] = btn

    return price_input, buttons


def create_inventory_table(parent, icon_path, on_header_click_fn):
    """Создаёт таблицу инвентаря."""
    table = QTableWidget(parent)
    table.setColumnCount(COLUMN_COUNT)
    table.setHorizontalHeaderLabels(COLUMN_HEADERS)

    header_font = QFont(Theme.FONT_FAMILY)
    header_font.setPointSize(Theme.FONT_SIZE)
    header_font.setBold(False)
    table.horizontalHeader().setFont(header_font)

    table.horizontalHeader().setStyleSheet(Theme.table_header_style())

    keychain_icon_path = os.path.join(icon_path, "keychain.png")
    if os.path.exists(keychain_icon_path):
        colored_pixmap = change_icon_color(keychain_icon_path, Theme.PRIMARY)
        table.horizontalHeaderItem(COL_KEYCHAINS).setIcon(QIcon(colored_pixmap))
        table.horizontalHeaderItem(COL_KEYCHAINS).setText("")

    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSortingEnabled(True)
    table.horizontalHeader().setSectionsClickable(True)
    table.horizontalHeader().setSortIndicatorShown(True)

    for i in range(COLUMN_COUNT):
        if i < 7:
            table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
        else:
            table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)

    for col in HIDDEN_COLUMNS:
        table.setColumnHidden(col, True)

    table.horizontalHeader().sectionClicked.connect(on_header_click_fn)
    table.setFixedWidth(840)
    table.setMinimumHeight(620)
    table.move(20, 132)
    table.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

    table.setStyleSheet(Theme.table_style())

    table.verticalHeader().setDefaultSectionSize(30)
    table.setIconSize(QSize(10, 30))

    return table
