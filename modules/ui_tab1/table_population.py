# modules/ui_tab1/table_population.py

import os
import re
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QTableWidgetItem, QApplication
from PyQt6.QtGui import QPixmap, QIcon, QColor, QBrush, QPainter
from PyQt6.QtCore import Qt
from modules.utils import cache_image_async, calculate_days_on_sale
from modules.theme import Theme
from modules.models.columns import (
    COL_NAME, COL_STICKERS, COL_KEYCHAINS, COL_FLOAT, COL_SEED,
    COL_DAYS, COL_PRICE, COL_LISTING_ID, COL_ASSET_ID, COL_CREATED_AT,
    COL_PRICE_VALUE, COL_API_KEY, COL_COLLECTION, COL_RARITY, COL_WEAR,
)
from .constants import RARITY_COLOR_MAP


def create_color_icon(color: QColor, width: int = 5, height: int = 30) -> QIcon:
    """Создаёт цветную иконку для редкости."""
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setBrush(QBrush(color))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRect(0, 0, width, height)
    painter.end()
    return QIcon(pixmap)


class TablePopulator:
    """Заполнение таблицы инвентаря."""

    def __init__(self, table, icon_path, font, event_filter_target):
        self.table = table
        self.icon_path = icon_path
        self.font = font
        self.event_filter_target = event_filter_target

    def populate(self, inventory, stall):
        """Заполняет таблицу с нуля."""
        self.table.setRowCount(0)
        self.table.setSortingEnabled(False)
        self._add_items(inventory, stall)
        self.table.setSortingEnabled(True)

    def append(self, inventory, stall):
        """Добавляет предметы в таблицу без очистки."""
        self._add_items(inventory, stall)

    def _add_items(self, inventory, stall):
        """Добавляет строки в таблицу батчами."""
        stall_dict = {}
        for st in (stall or []):
            asset_id = st.get("item", {}).get("asset_id")
            if asset_id:
                stall_dict[asset_id] = st

        batch_size = 100
        total_items = len(inventory)

        for batch_start in range(0, total_items, batch_size):
            batch_end = min(batch_start + batch_size, total_items)
            batch_items = inventory[batch_start:batch_end]

            for item in batch_items:
                row = self.table.rowCount()
                self.table.insertRow(row)

                asset_id = str(item.get("asset_id", ""))
                market_hash_name = item.get("market_hash_name", "")

                rarity_value = int(item.get("rarity", 1)) or 1
                color = RARITY_COLOR_MAP.get(rarity_value, QColor("white"))
                color_icon = create_color_icon(color)

                name_item = QTableWidgetItem(market_hash_name)
                name_item.setIcon(color_icon)
                name_item.setFont(self.font)
                name_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                self.table.setItem(row, COL_NAME, name_item)

                self._populate_stickers(row, item)
                self._populate_keychains(row, item)
                self._populate_float(row, item)
                self._populate_seed(row, item)

                stall_item = stall_dict.get(asset_id)
                if stall_item:
                    self._populate_stall_data(row, stall_item)
                else:
                    self._populate_empty_stall_data(row)

                self._populate_hidden_columns(row, item, asset_id, market_hash_name)

            QApplication.processEvents()

    def _populate_stickers(self, row, item):
        """Заполняет стикеры с асинхронной загрузкой иконок."""
        stickers = item.get("stickers", []) or []
        sticker_layout = QHBoxLayout()
        sticker_layout.setContentsMargins(0, 0, 0, 0)
        sticker_layout.setSpacing(2)

        for st in stickers:
            sticker_url = st.get("icon_url")
            if not sticker_url:
                continue

            lbl = QLabel()
            lbl.setFixedSize(20, 20)
            sticker_text = st.get("name", "Unknown")
            lbl._tooltip_text = sticker_text
            lbl.setMouseTracking(True)
            lbl.installEventFilter(self.event_filter_target)
            lbl.setStyleSheet("")

            def create_callback(label):
                def on_loaded(path):
                    if path and os.path.exists(path):
                        pixmap = QPixmap(path)
                        if not pixmap.isNull():
                            label.setPixmap(pixmap.scaled(
                                20, 20,
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation
                            ))

                return on_loaded

            cache_image_async(sticker_url, create_callback(lbl))
            sticker_layout.addWidget(lbl)

        sticker_layout.addStretch(1)

        sticker_widget = QWidget()
        sticker_widget.setLayout(sticker_layout)
        sticker_widget.setStyleSheet(Theme.transparent_widget())
        sticker_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.table.setCellWidget(row, COL_STICKERS, sticker_widget)

    def _populate_keychains(self, row, item):
        """Заполняет брелки с асинхронной загрузкой иконок."""
        keychains = item.get("keychains", []) or []
        keychain_layout = QHBoxLayout()
        keychain_layout.setContentsMargins(0, 0, 0, 0)
        keychain_layout.setSpacing(2)

        for kc in keychains:
            keychain_url = kc.get("icon_url")
            if not keychain_url:
                continue

            lbl = QLabel()
            lbl.setFixedSize(20, 20)
            keychain_name = kc.get("name", "Unknown")
            keychain_pattern = kc.get("pattern", "")

            if keychain_pattern:
                tooltip_text = f"{keychain_name}\n#{keychain_pattern}"
            else:
                tooltip_text = keychain_name

            lbl._tooltip_text = tooltip_text
            lbl.setMouseTracking(True)
            lbl.installEventFilter(self.event_filter_target)
            lbl.setStyleSheet("")

            def create_callback(label):
                def on_loaded(path):
                    if path and os.path.exists(path):
                        pixmap = QPixmap(path)
                        if not pixmap.isNull():
                            label.setPixmap(pixmap.scaled(
                                20, 20,
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation
                            ))

                return on_loaded

            cache_image_async(keychain_url, create_callback(lbl))
            keychain_layout.addWidget(lbl)

        keychain_layout.addStretch(1)

        keychain_widget = QWidget()
        keychain_widget.setLayout(keychain_layout)
        keychain_widget.setStyleSheet(Theme.transparent_widget())
        keychain_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.table.setCellWidget(row, COL_KEYCHAINS, keychain_widget)

    def _populate_float(self, row, item):
        """Заполняет Float Value."""
        float_value = item.get("float_value")
        float_text = f"{float_value:.14f}" if isinstance(float_value, (int, float)) else ""
        float_item = QTableWidgetItem(float_text)
        float_item.setFont(self.font)
        self.table.setItem(row, COL_FLOAT, float_item)

    def _populate_seed(self, row, item):
        """Заполняет Paint Seed."""
        paint_seed = item.get("paint_seed")
        seed_text = str(paint_seed) if paint_seed is not None else ""
        seed_item = QTableWidgetItem(seed_text)
        seed_item.setFont(self.font)
        if paint_seed is not None:
            seed_item.setData(Qt.ItemDataRole.UserRole, int(paint_seed))
        self.table.setItem(row, COL_SEED, seed_item)

    def _populate_stall_data(self, row, stall_item):
        """Заполняет данные о продаже."""
        days_text = calculate_days_on_sale(stall_item.get("created_at", ""))
        days_item = QTableWidgetItem(days_text)
        days_item.setFont(self.font)
        self.table.setItem(row, COL_DAYS, days_item)

        price_cents = int(stall_item.get("price", 0)) or 0
        price_str = f"{price_cents / 100:.2f}"

        price_widget = QWidget()
        price_layout = QHBoxLayout(price_widget)
        price_layout.setContentsMargins(0, 0, 0, 0)
        price_layout.setSpacing(4)

        logo = QLabel()
        logo_path = os.path.join(self.icon_path, "csfloat_logo.png")
        if os.path.exists(logo_path):
            logo.setPixmap(QPixmap(logo_path).scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio))
            logo.setStyleSheet(Theme.transparent_widget())
            price_layout.addWidget(logo)

        price_label = QLabel(f"${price_str}")
        price_label.setFont(self.font)
        price_label.setStyleSheet(Theme.transparent_widget())
        price_layout.addWidget(price_label)
        price_layout.addStretch(1)

        price_widget.setStyleSheet(Theme.transparent_widget())
        price_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.table.setCellWidget(row, COL_PRICE, price_widget)

        listing_id_item = QTableWidgetItem(str(stall_item.get("id", "")))
        listing_id_item.setFont(self.font)
        self.table.setItem(row, COL_LISTING_ID, listing_id_item)

        created_at_item = QTableWidgetItem(str(stall_item.get("created_at", "")))
        created_at_item.setFont(self.font)
        self.table.setItem(row, COL_CREATED_AT, created_at_item)

        price_value_item = QTableWidgetItem()
        price_value_item.setData(Qt.ItemDataRole.DisplayRole, price_cents)
        price_value_item.setData(Qt.ItemDataRole.UserRole, price_cents)
        price_value_item.setFont(self.font)
        self.table.setItem(row, COL_PRICE_VALUE, price_value_item)

    def _populate_empty_stall_data(self, row):
        """Заполняет пустые ячейки для предметов не на продаже."""
        self.table.setItem(row, COL_DAYS, QTableWidgetItem(""))

        empty_price = QWidget()
        empty_price.setStyleSheet(Theme.transparent_widget())
        empty_price.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.table.setCellWidget(row, COL_PRICE, empty_price)

        self.table.setItem(row, COL_LISTING_ID, QTableWidgetItem(""))
        self.table.setItem(row, COL_CREATED_AT, QTableWidgetItem(""))
        self.table.setItem(row, COL_PRICE_VALUE, QTableWidgetItem(""))

    def _populate_hidden_columns(self, row, item, asset_id, market_hash_name):
        """Заполняет скрытые колонки (API Key, Collection, Rarity, Wear)."""
        api_key_item = QTableWidgetItem(item.get("api_key", "NA") or "NA")
        api_key_item.setFont(self.font)
        self.table.setItem(row, COL_API_KEY, api_key_item)

        collection = item.get("collection", "NA") or "NA"

        if collection.startswith("The "):
            collection = collection[4:]

        collection = re.sub(r"\u2605", "", collection)

        collection_item = QTableWidgetItem(collection)
        collection_item.setFont(self.font)
        self.table.setItem(row, COL_COLLECTION, collection_item)

        rarity_item = QTableWidgetItem(str(item.get("rarity", "NA") or "NA"))
        rarity_item.setFont(self.font)
        self.table.setItem(row, COL_RARITY, rarity_item)

        wear_name = item.get("wear_name", "NA") or "NA"
        if wear_name == "NA":
            m = re.search(r"\((.+?)\)", market_hash_name)
            wear_name = m.group(1) if m else "NA"

        wear_item = QTableWidgetItem(wear_name)
        wear_item.setFont(self.font)
        self.table.setItem(row, COL_WEAR, wear_item)

        asset_item = QTableWidgetItem(asset_id)
        asset_item.setFont(self.font)
        self.table.setItem(row, COL_ASSET_ID, asset_item)
