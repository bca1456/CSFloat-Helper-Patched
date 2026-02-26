# modules/ui_tab1/table_population.py

import os
import re
from PyQt6.QtWidgets import QTableWidgetItem
from PyQt6.QtGui import QPixmap, QIcon, QColor, QBrush, QPainter
from PyQt6.QtCore import Qt, QTimer
from modules.utils import cache_image_async, calculate_days_on_sale
from modules.models.columns import (
    COL_NAME, COL_STICKERS, COL_KEYCHAINS, COL_FLOAT, COL_SEED,
    COL_DAYS, COL_PRICE, COL_LISTING_ID, COL_ASSET_ID, COL_CREATED_AT,
    COL_PRICE_VALUE, COL_API_KEY, COL_COLLECTION, COL_RARITY, COL_WEAR,
)
from .constants import RARITY_COLOR_MAP


class EmptyLastItem(QTableWidgetItem):
    """QTableWidgetItem, пустые значения которого всегда внизу при сортировке."""

    def __lt__(self, other):
        self_text = self.text()
        other_text = other.text()

        if not self_text and not other_text:
            return False

        header = self.tableWidget().horizontalHeader()
        ascending = header.sortIndicatorOrder() == Qt.SortOrder.AscendingOrder

        if not self_text:
            return not ascending
        if not other_text:
            return ascending

        return self_text < other_text


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
    """Заполнение таблицы инвентаря через асинхронные батчи."""

    BATCH_SIZE = 100

    def __init__(self, table, icon_path):
        self.table = table
        self.icon_path = icon_path
        self.asset_index = {}
        self._queue = []
        self._pending = []
        self._processing = False
        self.on_finished = None

    def populate(self, inventory, stall):
        """Заполняет таблицу с нуля."""
        self.asset_index = {}
        self._queue.clear()
        self._pending.clear()
        self._processing = False
        self.table.setRowCount(0)
        self._enqueue(inventory, stall)

    def append(self, inventory, stall):
        """Добавляет предметы в таблицу (через очередь)."""
        self._enqueue(inventory, stall)

    def _enqueue(self, inventory, stall):
        self._queue.append((inventory, stall))
        if not self._processing:
            self._start_next()

    def _start_next(self):
        if not self._queue:
            self._processing = False
            if self.on_finished:
                self.on_finished()
            return

        self._processing = True
        inventory, stall = self._queue.pop(0)

        stall_dict = {}
        for st in (stall or []):
            asset_id = st.get("item", {}).get("asset_id")
            if asset_id:
                stall_dict[asset_id] = st

        self._pending = [(item, stall_dict) for item in inventory]
        self._process_batch()

    def _process_batch(self):
        batch = self._pending[:self.BATCH_SIZE]
        self._pending = self._pending[self.BATCH_SIZE:]

        for item, stall_dict in batch:
            self._add_single_row(item, stall_dict)

        if self._pending:
            QTimer.singleShot(0, self._process_batch)
        else:
            self._start_next()

    def _add_single_row(self, item, stall_dict):
        """Добавляет одну строку в таблицу."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        asset_id = str(item.get("asset_id", ""))
        market_hash_name = item.get("market_hash_name", "")

        rarity_value = int(item.get("rarity", 1)) or 1
        color = RARITY_COLOR_MAP.get(rarity_value, QColor("white"))
        color_icon = create_color_icon(color)

        name_item = QTableWidgetItem(market_hash_name)
        name_item.setIcon(color_icon)
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

    def _populate_icon_cells(self, row, item, field, column):
        """Заполняет ячейку с данными иконок для делегата."""
        entries = item.get(field, []) or []
        icon_data = []

        for entry in entries:
            icon_url = entry.get("icon_url")
            if not icon_url:
                continue

            name = entry.get("name", "Unknown")
            pattern = entry.get("pattern", "")
            tooltip = f"{name}\n#{pattern}" if pattern else name

            icon_data.append({"name": name, "tooltip": tooltip, "pixmap": None})

            idx = len(icon_data) - 1

            def _make_cb(data_list, i):
                def on_loaded(path):
                    if not path or not os.path.exists(path):
                        return
                    pm = QPixmap(path).scaled(
                        20, 20,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    if i < len(data_list):
                        data_list[i]["pixmap"] = pm
                        self.table.viewport().update()
                return on_loaded

            cache_image_async(icon_url, _make_cb(icon_data, idx))

        cell_item = QTableWidgetItem()
        cell_item.setData(Qt.ItemDataRole.UserRole, icon_data if icon_data else None)
        self.table.setItem(row, column, cell_item)

    def _populate_stickers(self, row, item):
        """Заполняет стикеры."""
        self._populate_icon_cells(row, item, "stickers", COL_STICKERS)

    def _populate_keychains(self, row, item):
        """Заполняет брелки."""
        self._populate_icon_cells(row, item, "keychains", COL_KEYCHAINS)

    def _populate_float(self, row, item):
        """Заполняет Float Value."""
        float_value = item.get("float_value")
        float_text = f"{float_value:.14f}" if isinstance(float_value, (int, float)) else ""
        float_item = EmptyLastItem(float_text)
        self.table.setItem(row, COL_FLOAT, float_item)

    def _populate_seed(self, row, item):
        """Заполняет Paint Seed."""
        paint_seed = item.get("paint_seed")
        seed_text = str(paint_seed) if paint_seed is not None else ""
        seed_item = QTableWidgetItem(seed_text)
        if paint_seed is not None:
            seed_item.setData(Qt.ItemDataRole.UserRole, int(paint_seed))
        self.table.setItem(row, COL_SEED, seed_item)

    def _populate_stall_data(self, row, stall_item):
        """Заполняет данные о продаже."""
        days_text = calculate_days_on_sale(stall_item.get("created_at", ""))
        days_item = QTableWidgetItem(days_text)
        self.table.setItem(row, COL_DAYS, days_item)

        price_cents = int(stall_item.get("price", 0)) or 0
        price_item = QTableWidgetItem()
        price_item.setData(Qt.ItemDataRole.UserRole, price_cents)
        self.table.setItem(row, COL_PRICE, price_item)

        listing_id_item = QTableWidgetItem(str(stall_item.get("id", "")))
        self.table.setItem(row, COL_LISTING_ID, listing_id_item)

        created_at_item = QTableWidgetItem(str(stall_item.get("created_at", "")))
        self.table.setItem(row, COL_CREATED_AT, created_at_item)

        price_value_item = QTableWidgetItem()
        price_value_item.setData(Qt.ItemDataRole.DisplayRole, price_cents)
        price_value_item.setData(Qt.ItemDataRole.UserRole, price_cents)
        self.table.setItem(row, COL_PRICE_VALUE, price_value_item)

    def _populate_empty_stall_data(self, row):
        """Заполняет пустые ячейки для предметов не на продаже."""
        self.table.setItem(row, COL_DAYS, QTableWidgetItem(""))
        self.table.setItem(row, COL_PRICE, QTableWidgetItem())
        self.table.setItem(row, COL_LISTING_ID, QTableWidgetItem(""))
        self.table.setItem(row, COL_CREATED_AT, QTableWidgetItem(""))
        self.table.setItem(row, COL_PRICE_VALUE, QTableWidgetItem(""))

    def _populate_hidden_columns(self, row, item, asset_id, market_hash_name):
        """Заполняет скрытые колонки (API Key, Collection, Rarity, Wear)."""
        api_key_item = QTableWidgetItem(item.get("api_key", "NA") or "NA")
        self.table.setItem(row, COL_API_KEY, api_key_item)

        collection = item.get("collection", "NA") or "NA"

        if collection.startswith("The "):
            collection = collection[4:]

        collection = re.sub(r"\u2605", "", collection)

        collection_item = QTableWidgetItem(collection)
        self.table.setItem(row, COL_COLLECTION, collection_item)

        rarity_item = QTableWidgetItem(str(item.get("rarity", "NA") or "NA"))
        self.table.setItem(row, COL_RARITY, rarity_item)

        wear_name = item.get("wear_name", "NA") or "NA"
        if wear_name == "NA":
            m = re.search(r"\((.+?)\)", market_hash_name)
            wear_name = m.group(1) if m else "NA"

        wear_item = QTableWidgetItem(wear_name)
        self.table.setItem(row, COL_WEAR, wear_item)

        asset_item = QTableWidgetItem(asset_id)
        self.table.setItem(row, COL_ASSET_ID, asset_item)
        self.asset_index[asset_id] = asset_item
