# modules/ui_tab1/filters.py

from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtWidgets import QLabel
from modules.models.columns import (
    COL_NAME, COL_FLOAT, COL_RARITY, COL_WEAR, COL_STICKERS, COL_COLLECTION,
)


class FilterController(QObject):
    """Управление фильтрацией таблицы инвентаря."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.table = None
        self.inputs = {}

        self.selected_conditions = set()
        self.selected_rarities = set()
        self.stattrack_filter = False
        self.souvenir_filter = False

        self.last_sorted_column = None
        self.last_sort_order = None

    def bind(self, table, inputs):
        """Привязать таблицу и поля ввода.

        inputs — dict с ключами: name_filter, sticker_filter,
        float_min_filter, float_max_filter, collection_edit
        """
        self.table = table
        self.inputs = inputs

    def update_rarity(self, rarity, checked):
        """Обновить фильтр по редкости."""
        if rarity == 7:
            self.stattrack_filter = checked
        elif rarity == 8:
            self.souvenir_filter = checked
        else:
            if checked:
                self.selected_rarities.add(rarity)
            else:
                self.selected_rarities.discard(rarity)

        self.apply()

    def update_condition(self, wear_condition, checked):
        """Обновить фильтр по состоянию."""
        if checked:
            self.selected_conditions.add(wear_condition)
        else:
            self.selected_conditions.discard(wear_condition)

        self.apply()

    @pyqtSlot()
    def apply(self):
        """Применить все фильтры к таблице."""
        if not self.table:
            return

        name_filter = self.inputs["name_filter"].text().lower()
        sticker_filter = self.inputs["sticker_filter"].text().lower()
        collection_filter = self.inputs["collection_edit"].text().strip().lower()

        try:
            min_float = float(self.inputs["float_min_filter"].text()) if self.inputs["float_min_filter"].text() else None
            max_float = float(self.inputs["float_max_filter"].text()) if self.inputs["float_max_filter"].text() else None
        except ValueError:
            min_float = None
            max_float = None

        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, COL_NAME)
            name_txt = (name_item.text().lower() if name_item else "")

            float_item = self.table.item(row, COL_FLOAT)
            float_txt = float_item.text() if float_item else ""
            float_val = float(float_txt) if float_txt else None

            rarity_item = self.table.item(row, COL_RARITY)
            rarity_val = int(rarity_item.text()) if rarity_item and rarity_item.text().isdigit() else None

            wear_item = self.table.item(row, COL_WEAR)
            wear_val = wear_item.text() if wear_item else "N/A"

            stickers_widget = self.table.cellWidget(row, COL_STICKERS)
            sticker_names = ""
            if stickers_widget and stickers_widget.layout():
                lay = stickers_widget.layout()
                for i in range(lay.count()):
                    w = lay.itemAt(i).widget()
                    if isinstance(w, QLabel) and hasattr(w, '_tooltip_text'):
                        sticker_names += w._tooltip_text.lower()

            matches_name = name_filter in name_txt
            matches_sticker = sticker_filter in sticker_names
            matches_float = (
                (min_float is None or (float_val is not None and float_val >= min_float))
                and (max_float is None or (float_val is not None and float_val <= max_float))
            )

            if self.selected_rarities:
                matches_rarity = rarity_val in self.selected_rarities
            else:
                matches_rarity = True

            if self.stattrack_filter:
                matches_stattrack = "stattrak™" in name_txt
            else:
                matches_stattrack = True

            if self.souvenir_filter:
                matches_souvenir = "souvenir" in name_txt
            else:
                matches_souvenir = True

            if self.selected_conditions:
                matches_condition = wear_val in self.selected_conditions
            else:
                matches_condition = True

            if collection_filter:
                c_item = self.table.item(row, COL_COLLECTION)
                c_txt = (c_item.text().strip().lower() if c_item else "")
                matches_collection = (c_txt == collection_filter)
            else:
                matches_collection = True

            self.table.setRowHidden(
                row,
                not (
                    matches_name and matches_sticker and matches_float and
                    matches_rarity and matches_stattrack and matches_souvenir and
                    matches_condition and matches_collection
                ),
            )

        if self.last_sorted_column is not None and self.last_sort_order is not None:
            self.table.sortItems(self.last_sorted_column, self.last_sort_order)
