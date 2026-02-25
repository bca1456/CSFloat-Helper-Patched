# modules/ui_tab1/item_operations.py

import os
from datetime import datetime, timezone
from collections import defaultdict

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QTableWidgetItem, QDialog,
    QVBoxLayout, QFormLayout, QPushButton, QScrollArea, QGraphicsDropShadowEffect
)
from PyQt6.QtGui import QPixmap, QFont, QIcon, QColor, QPainter, QPainterPath
from PyQt6.QtCore import Qt, QPersistentModelIndex, QRectF, QThreadPool

from modules.api import bulk_list, bulk_delist, bulk_modify
from modules.workers import ApiWorker
from modules.utils import cache_image
from modules.messagebox import warning, information
from modules.theme import Theme
from modules.models.inventory_store import InventoryStore
from modules.models.columns import (
    COL_NAME, COL_STICKERS, COL_KEYCHAINS, COL_FLOAT, COL_SEED,
    COL_DAYS, COL_PRICE, COL_LISTING_ID, COL_ASSET_ID, COL_CREATED_AT,
    COL_PRICE_VALUE, COL_API_KEY, COL_COLLECTION, COL_RARITY, COL_WEAR,
)


class ItemOperations:
    """Операции с предметами: продажа, изменение цены, снятие, перевыставление."""

    def __init__(self, table, store, icon_path, font, parent_widget, apply_filters_fn):
        self.table = table
        self.store = store
        self.icon_path = icon_path
        self.font = font
        self.parent_widget = parent_widget
        self.apply_filters_fn = apply_filters_fn
        self.price_input = None
        self.action_buttons = {}
        self.threadpool = QThreadPool.globalInstance()

    def bind_price_input(self, price_input):
        self.price_input = price_input

    def bind_action_buttons(self, buttons):
        """Привязывает кнопки действий для блокировки во время операций."""
        self.action_buttons = buttons

    def _set_buttons_enabled(self, enabled):
        """Блокирует/разблокирует кнопки действий."""
        for btn in self.action_buttons.values():
            btn.setEnabled(enabled)

    # =========================================================================
    # Диалоги
    # =========================================================================

    def _show_confirmation_dialog(self, title, items_grouped, action_type="sell"):
        """Диалог подтверждения операции."""
        dialog = QDialog(self.parent_widget)
        Theme.apply_titlebar_theme(dialog)
        total_items = sum(items_grouped.values())

        titles = {
            "sell": f"Sell {total_items} item{'s' if total_items > 1 else ''}?",
            "change": f"Change price for {total_items} item{'s' if total_items > 1 else ''}?",
            "delist": f"Delist {total_items} item{'s' if total_items > 1 else ''}?",
            "swap": f"Relist {total_items} item{'s' if total_items > 1 else ''}?",
        }
        dialog.setWindowTitle(titles.get(action_type, f"Process {total_items} item{'s' if total_items > 1 else ''}?"))
        dialog.setMinimumWidth(350)
        dialog.setMaximumWidth(500)
        dialog.setMaximumHeight(400)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(250)
        scroll.setStyleSheet(Theme.scroll_area())

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(1)
        content_layout.setContentsMargins(6, 6, 6, 6)

        for key, count in items_grouped.items():
            if action_type in ("sell", "swap"):
                name, price = key
                text = f"{count}× {name} — ${price:.2f}" if count > 1 else f"{name} — ${price:.2f}"
            elif action_type == "change":
                name, old_price, new_price = key
                text = f"{count}× {name}: ${old_price:.2f} → ${new_price:.2f}" if count > 1 else f"{name}: ${old_price:.2f} → ${new_price:.2f}"
            elif action_type == "delist":
                name = key
                text = f"{count}× {name}" if count > 1 else name
            else:
                text = str(key)

            item_label = QLabel(text)
            item_label.setStyleSheet(Theme.item_label())
            item_label.setWordWrap(True)
            content_layout.addWidget(item_label)

        content_layout.addStretch()
        scroll.setWidget(content_widget)
        layout.addWidget(scroll)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(80, 28)
        cancel_btn.setStyleSheet(Theme.button_secondary())
        cancel_btn.clicked.connect(dialog.reject)

        confirm_btn = QPushButton("Confirm")
        confirm_btn.setFixedSize(80, 28)
        confirm_btn.setStyleSheet(Theme.button_primary())
        confirm_btn.clicked.connect(dialog.accept)
        confirm_btn.setDefault(True)

        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(confirm_btn)
        button_layout.addStretch()

        layout.addLayout(button_layout)

        return dialog.exec() == QDialog.DialogCode.Accepted

    def _show_grouped_operations(self, operations, title="Operations"):
        """Результат операций сгруппированный по имени."""
        grouped = defaultdict(int)
        for name, price in operations:
            grouped[(name, price)] += 1

        lines = []
        for (name, price), count in grouped.items():
            if count > 1:
                lines.append(f"{count}× {name} ${price:.2f}")
            else:
                lines.append(f"{name} ${price:.2f}")

        information(self.parent_widget, title, "\n".join(lines))

    def _show_price_change_operations(self, operations):
        """Результат изменения цен."""
        grouped = defaultdict(int)
        for name, old, new in operations:
            grouped[(name, old, new)] += 1

        lines = []
        for (name, old, new), count in grouped.items():
            if count > 1:
                lines.append(f"{count}× {name}: ${old:.2f} → ${new:.2f}")
            else:
                lines.append(f"{name}: ${old:.2f} → ${new:.2f}")

        information(self.parent_widget, "Price Changed", "\n".join(lines))

    def _show_grouped_delist(self, items):
        """Результат снятия с продажи."""
        grouped = defaultdict(int)
        for item in items:
            grouped[item] += 1

        lines = []
        for item, count in grouped.items():
            lines.append(f"{count}× {item}" if count > 1 else item)

        information(self.parent_widget, "Items Delisted", "\n".join(lines))

    # =========================================================================
    # Обновление таблицы
    # =========================================================================

    def _create_price_widget(self, price_cents):
        """Создаёт виджет цены с логотипом."""
        price_widget = QWidget()
        lay = QHBoxLayout(price_widget)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        logo = QLabel()
        logo_path = os.path.join(self.icon_path, "csfloat_logo.png")
        if os.path.exists(logo_path):
            logo.setPixmap(QPixmap(logo_path).scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio))
            logo.setStyleSheet(Theme.transparent_widget())
            lay.addWidget(logo)

        price_label = QLabel(f" ${price_cents / 100:.2f}")
        price_label.setFont(self.font)
        price_label.setStyleSheet(Theme.transparent_widget())
        lay.addWidget(price_label)
        lay.addStretch(1)

        price_widget.setStyleSheet(Theme.transparent_widget())
        price_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        return price_widget

    def _find_row_by_asset_id(self, asset_id):
        """Находит строку таблицы по asset_id."""
        for r in range(self.table.rowCount()):
            asset_it = self.table.item(r, COL_ASSET_ID)
            if asset_it and asset_it.text() == asset_id:
                return r
        return -1

    def _update_item_as_sold(self, asset_id, price_cents, listing_id):
        """Обновляет строку таблицы после продажи."""
        row = self._find_row_by_asset_id(asset_id)
        if row == -1:
            return

        created_at = datetime.now(timezone.utc).isoformat()

        days_item = QTableWidgetItem("0d 0h")
        days_item.setFont(self.font)
        self.table.setItem(row, COL_DAYS, days_item)

        self.table.setCellWidget(row, COL_PRICE, self._create_price_widget(price_cents))

        listing_item = QTableWidgetItem(str(listing_id))
        listing_item.setFont(self.font)
        self.table.setItem(row, COL_LISTING_ID, listing_item)

        created_item = QTableWidgetItem(created_at)
        created_item.setFont(self.font)
        self.table.setItem(row, COL_CREATED_AT, created_item)

        pv_item = QTableWidgetItem()
        pv_item.setData(Qt.ItemDataRole.DisplayRole, price_cents)
        pv_item.setData(Qt.ItemDataRole.UserRole, price_cents)
        pv_item.setFont(self.font)
        self.table.setItem(row, COL_PRICE_VALUE, pv_item)

    def _update_item_price(self, asset_id, new_price_cents):
        """Обновляет цену в таблице."""
        row = self._find_row_by_asset_id(asset_id)
        if row == -1:
            return

        self.table.setCellWidget(row, COL_PRICE, self._create_price_widget(new_price_cents))

        pv_item = QTableWidgetItem()
        pv_item.setData(Qt.ItemDataRole.DisplayRole, new_price_cents)
        pv_item.setData(Qt.ItemDataRole.UserRole, new_price_cents)
        pv_item.setFont(self.font)
        self.table.setItem(row, COL_PRICE_VALUE, pv_item)

    def _update_item_as_unsold(self, row):
        """Обновляет строку после снятия с продажи."""
        self.table.setItem(row, COL_DAYS, QTableWidgetItem(""))

        empty_price = QWidget()
        empty_price.setStyleSheet(Theme.transparent_widget())
        empty_price.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.table.setCellWidget(row, COL_PRICE, empty_price)

        self.table.setItem(row, COL_LISTING_ID, QTableWidgetItem(""))
        self.table.setItem(row, COL_CREATED_AT, QTableWidgetItem(""))
        self.table.setItem(row, COL_PRICE_VALUE, QTableWidgetItem(""))
        self.table.setRowHidden(row, False)

    def _update_item_as_unsold_by_asset_id(self, asset_id):
        """Обновляет строку после снятия с продажи. Поиск по asset_id."""
        row = self._find_row_by_asset_id(asset_id)
        if row != -1:
            self._update_item_as_unsold(row)

    # =========================================================================
    # Операции
    # =========================================================================

    def sell_items(self):
        """Продаёт выбранные предметы."""
        pw = self.parent_widget
        price_input = self.price_input.text().strip() if self.price_input else ""

        if "%" in price_input:
            warning(pw, "Warning", "Please remove the '%' sign from the price field before selling.")
            return

        selected = self.table.selectionModel().selectedRows()
        if not selected:
            warning(pw, "Warning", "Please select items to sell.")
            return

        selected_asset_ids = set()
        for idx in selected:
            row = idx.row()
            if not self.table.isRowHidden(row):
                it = self.table.item(row, COL_ASSET_ID)
                if it and it.text():
                    selected_asset_ids.add(it.text())

        if not price_input:
            warning(pw, "Warning", "Price field must be filled.")
            return

        try:
            price = float(price_input)
            if price < InventoryStore.MIN_PRICE / 100:
                warning(pw, "Warning", f"Price cannot be lower than ${InventoryStore.MIN_PRICE / 100:.2f}.")
                return
            if price * 100 > InventoryStore.MAX_PRICE:
                warning(pw, "Warning", f"Maximum allowed price is ${InventoryStore.MAX_PRICE / 100:.2f} USD")
                return
            price_cents = int(price * 100)
        except ValueError as e:
            warning(pw, "Error", f"Invalid price input: {e}")
            return

        items_to_sell = defaultdict(list)
        already_listed = []

        for row in range(self.table.rowCount()):
            asset_it = self.table.item(row, COL_ASSET_ID)
            if not asset_it or asset_it.text() not in selected_asset_ids:
                continue

            created_it = self.table.item(row, COL_CREATED_AT)
            price_val_it = self.table.item(row, COL_PRICE_VALUE)

            if (created_it and created_it.text()) or (price_val_it and price_val_it.text()):
                already_listed.append(self.table.item(row, COL_NAME).text())
                continue

            api_it = self.table.item(row, COL_API_KEY)
            if not api_it:
                continue

            items_to_sell[api_it.text()].append({
                "asset_id": asset_it.text(),
                "name": self.table.item(row, COL_NAME).text(),
                "price": price_cents,
            })

        if not items_to_sell:
            if already_listed:
                warning(pw, "Warning",
                        "The following items are already listed:\n" + "\n".join(already_listed))
            return

        grouped = defaultdict(int)
        for api_key, items in items_to_sell.items():
            for item in items:
                grouped[(item["name"], item["price"] / 100)] += 1

        if not self._show_confirmation_dialog("Sell Items", grouped, "sell"):
            return

        descriptions = dict(self.store.account_descriptions)

        def _do_sell():
            results = {}
            for api_key, items in items_to_sell.items():
                description = descriptions.get(api_key, "")
                bulk_items = []
                for item in items:
                    item_data = {
                        "asset_id": item["asset_id"],
                        "price": item["price"],
                        "type": "buy_now"
                    }
                    if description:
                        item_data["description"] = description
                    bulk_items.append(item_data)

                resp = bulk_list(api_key, bulk_items)
                results[api_key] = (items, resp)
            return results

        self._set_buttons_enabled(False)

        worker = ApiWorker(_do_sell)
        worker.signals.result.connect(lambda res: self._on_sell_result(res, already_listed))
        worker.signals.error.connect(self._on_sell_error)
        worker.signals.finished.connect(lambda: self._set_buttons_enabled(True))
        self.threadpool.start(worker)

    def _on_sell_result(self, results, already_listed):
        """Обработка результата продажи."""
        pw = self.parent_widget
        successful = []

        for api_key, (items, resp) in results.items():
            if resp is None:
                warning(pw, "Error", "Failed to list items. No response from server.")
                return

            listings = resp.get("data", []) if isinstance(resp, dict) else resp
            if not listings:
                warning(pw, "Error", "Failed to list items. Empty response from server.")
                return

            for i, listing in enumerate(listings):
                if i >= len(items):
                    break
                item = items[i]
                listing_id = listing.get("id", "")
                if listing_id:
                    successful.append((item["name"], item["price"] / 100))
                    self._update_item_as_sold(item["asset_id"], item["price"], listing_id)

        if successful:
            self.apply_filters_fn()
            self._show_grouped_operations(successful, "Items Sold")
            self.table.clearSelection()

        if already_listed:
            warning(pw, "Warning",
                    "The following items are already listed:\n" + "\n".join(already_listed))

    def _on_sell_error(self, error):
        """Обработка ошибки продажи."""
        e, tb = error
        warning(self.parent_widget, "Error", f"Failed to list items: {str(e)}")

    def change_item_price(self):
        """Изменяет цену выбранных предметов."""
        pw = self.parent_widget
        price_input = self.price_input.text().strip() if self.price_input else ""
        selected = self.table.selectionModel().selectedRows()

        if not selected:
            warning(pw, "Warning", "Please select items to change the price.")
            return

        if not price_input:
            warning(pw, "Warning", "Price field must be filled.")
            return

        selected_asset_ids = set()
        for idx in selected:
            row = idx.row()
            if not self.table.isRowHidden(row):
                it = self.table.item(row, COL_ASSET_ID)
                if it and it.text():
                    selected_asset_ids.add(it.text())

        items_to_change = defaultdict(list)

        for row in range(self.table.rowCount()):
            asset_it = self.table.item(row, COL_ASSET_ID)
            if not asset_it or asset_it.text() not in selected_asset_ids:
                continue

            listing_id_it = self.table.item(row, COL_LISTING_ID)
            if not listing_id_it or not listing_id_it.text():
                continue

            price_widget = self.table.cellWidget(row, COL_PRICE)
            if not price_widget:
                continue

            layout = price_widget.layout()
            if not layout:
                continue

            current_price_label = None
            for i in range(layout.count()):
                w = layout.itemAt(i).widget()
                if isinstance(w, QLabel) and "$" in w.text():
                    current_price_label = w
                    break

            if not current_price_label:
                continue

            try:
                current_price = float(current_price_label.text().strip().replace("$", "").strip())
            except:
                continue

            new_price_cents = self._calculate_new_price(price_input, current_price)
            if new_price_cents is None:
                return

            api_it = self.table.item(row, COL_API_KEY)
            if not api_it:
                continue

            items_to_change[api_it.text()].append({
                "asset_id": asset_it.text(),
                "name": self.table.item(row, COL_NAME).text(),
                "current_price": current_price,
                "new_price": new_price_cents / 100,
                "contract_id": listing_id_it.text(),
            })

        if not items_to_change:
            warning(pw, "Warning", "No listed items selected for price change.")
            return

        grouped = defaultdict(int)
        for api_key, items in items_to_change.items():
            for item in items:
                grouped[(item["name"], item["current_price"], item["new_price"])] += 1

        if not self._show_confirmation_dialog("Change Price", grouped, "change"):
            return

        def _do_change_price():
            results = {}
            for api_key, items in items_to_change.items():
                modifications = [
                    {"contract_id": item["contract_id"], "price": int(item["new_price"] * 100)}
                    for item in items
                ]
                resp = bulk_modify(api_key, modifications)
                results[api_key] = (items, resp)
            return results

        self._set_buttons_enabled(False)

        worker = ApiWorker(_do_change_price)
        worker.signals.result.connect(self._on_change_price_result)
        worker.signals.error.connect(self._on_change_price_error)
        worker.signals.finished.connect(lambda: self._set_buttons_enabled(True))
        self.threadpool.start(worker)

    def _on_change_price_result(self, results):
        """Обработка результата изменения цен."""
        pw = self.parent_widget
        successful = []

        for api_key, (items, resp) in results.items():
            if resp is None:
                warning(pw, "Error", "Failed to change prices. No response from server.")
                return

            listings = resp.get("data", []) if isinstance(resp, dict) else []
            if not listings:
                warning(pw, "Error", "Failed to change prices. Empty response from server.")
                return

            listing_map = {listing.get("id"): listing for listing in listings}

            for item in items:
                contract_id = item["contract_id"]
                if contract_id in listing_map:
                    successful.append((item["name"], item["current_price"], item["new_price"]))
                    self._update_item_price(item["asset_id"], int(item["new_price"] * 100))

        if successful:
            self._show_price_change_operations(successful)
            self.table.clearSelection()
        else:
            warning(pw, "Warning", "No prices were changed.")

    def _on_change_price_error(self, error):
        """Обработка ошибки изменения цен."""
        e, tb = error
        warning(self.parent_widget, "Error", f"Failed to change prices: {str(e)}")

    def _calculate_new_price(self, price_input, current_price):
        """Вычисляет новую цену."""
        pw = self.parent_widget

        if price_input.endswith("%"):
            percentage_str = price_input[:-1].strip()
            if not percentage_str:
                warning(pw, "Warning", "Please enter a number before the '%' symbol.")
                return None

            try:
                percentage_change = float(percentage_str)
            except ValueError:
                warning(pw, "Warning", "Only numbers are accepted for percentage changes.")
                return None

            if percentage_change == 0:
                warning(pw, "Warning", "Price will not change.")
                return None

            new_price = current_price * (1 + percentage_change / 100)
            new_price_cents = int(round(new_price * 100))

            if new_price_cents == int(current_price * 100):
                warning(pw, "Warning", "Price will not change.")
                return None

        elif price_input.startswith("+") or price_input.startswith("-"):
            try:
                change_value = float(price_input)
            except ValueError:
                warning(pw, "Error", "Only valid numeric values are accepted for price changes.")
                return None

            new_price = current_price + change_value
            new_price_cents = int(round(new_price * 100))

            if new_price_cents == int(current_price * 100):
                warning(pw, "Warning", "Price will not change.")
                return None

        else:
            try:
                new_price = float(price_input)
            except ValueError:
                warning(pw, "Error", "Only numbers or percentage changes are accepted.")
                return None

            new_price_cents = int(round(new_price * 100))

        if new_price_cents < InventoryStore.MIN_PRICE:
            warning(pw, "Warning", f"Price cannot be lower than ${InventoryStore.MIN_PRICE / 100:.2f}.")
            return None

        if new_price_cents > InventoryStore.MAX_PRICE:
            warning(pw, "Warning", f"Maximum allowed price is ${InventoryStore.MAX_PRICE / 100:.2f} USD")
            return None

        return new_price_cents

    def delist_items(self):
        """Снимает выбранные предметы с продажи."""
        pw = self.parent_widget
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            warning(pw, "Warning", "Please select items to delist.")
            return

        items_to_delist = defaultdict(list)
        persistents = []

        for idx in selected:
            row = idx.row()
            if not self.table.isRowHidden(row):
                persistent = QPersistentModelIndex(self.table.model().index(row, 0))
                persistents.append(persistent)

        for persistent in persistents:
            row = persistent.row()
            listing_id_it = self.table.item(row, COL_LISTING_ID)
            if not listing_id_it or not listing_id_it.text():
                continue

            api_it = self.table.item(row, COL_API_KEY)
            if not api_it:
                continue

            items_to_delist[api_it.text()].append({
                "persistent": persistent,
                "asset_id": self.table.item(row, COL_ASSET_ID).text(),
                "contract_id": listing_id_it.text(),
                "name": self.table.item(row, COL_NAME).text(),
            })

        if not items_to_delist:
            warning(pw, "Warning", "No listed items selected.")
            return

        grouped = defaultdict(int)
        for api_key, items in items_to_delist.items():
            for item in items:
                grouped[item["name"]] += 1

        if not self._show_confirmation_dialog("Delist Items", grouped, "delist"):
            return

        delist_api_data = {}
        for api_key, items in items_to_delist.items():
            delist_api_data[api_key] = [item["contract_id"] for item in items]

        def _do_delist():
            results = {}
            for api_key, contract_ids in delist_api_data.items():
                resp = bulk_delist(api_key, contract_ids)
                results[api_key] = resp
            return results

        self._set_buttons_enabled(False)

        worker = ApiWorker(_do_delist)
        worker.signals.result.connect(lambda res: self._on_delist_result(res, items_to_delist))
        worker.signals.error.connect(self._on_delist_error)
        worker.signals.finished.connect(lambda: self._set_buttons_enabled(True))
        self.threadpool.start(worker)

    def _on_delist_result(self, results, items_to_delist):
        """Обработка результата снятия с продажи."""
        self.table.setSortingEnabled(False)
        delisted = []

        for api_key, resp in results.items():
            if resp:
                for item in items_to_delist[api_key]:
                    row = self._find_row_by_asset_id(item["asset_id"])
                    if row != -1:
                        delisted.append(item["name"])
                        self._update_item_as_unsold(row)

        self.table.setSortingEnabled(True)

        if delisted:
            self._show_grouped_delist(delisted)
            self.table.clearSelection()

    def _on_delist_error(self, error):
        """Обработка ошибки снятия с продажи."""
        e, tb = error
        warning(self.parent_widget, "Error", f"Failed to delist items: {str(e)}")

    def swap_items(self):
        """Перевыставляет предметы."""
        pw = self.parent_widget
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            warning(pw, "Warning", "Please select items to relist.")
            return

        selected_asset_ids = set()
        for idx in selected:
            row = idx.row()
            if self.table.isRowHidden(row):
                continue
            it = self.table.item(row, COL_ASSET_ID)
            if it and it.text():
                selected_asset_ids.add(it.text())

        if not selected_asset_ids:
            warning(pw, "Warning", "No valid items selected.")
            return

        to_swap = defaultdict(list)

        for row in range(self.table.rowCount()):
            asset_it = self.table.item(row, COL_ASSET_ID)
            if not asset_it or asset_it.text() not in selected_asset_ids:
                continue

            api_it = self.table.item(row, COL_API_KEY)
            listing_it = self.table.item(row, COL_LISTING_ID)
            pv_it = self.table.item(row, COL_PRICE_VALUE)

            if not api_it or not api_it.text():
                continue
            if not listing_it or not listing_it.text():
                continue
            if not pv_it:
                continue

            price_cents = pv_it.data(Qt.ItemDataRole.UserRole)
            if price_cents is None:
                try:
                    price_cents = int(pv_it.data(Qt.ItemDataRole.DisplayRole))
                except Exception:
                    continue

            name_it = self.table.item(row, COL_NAME)
            name = name_it.text() if name_it else "Unknown"

            to_swap[api_it.text()].append({
                "asset_id": asset_it.text(),
                "contract_id": listing_it.text(),
                "price_cents": int(price_cents),
                "name": name,
            })

        if not to_swap:
            warning(pw, "Warning", "No listed items selected for relist.")
            return

        grouped = defaultdict(int)
        for apikey, items in to_swap.items():
            for it in items:
                grouped[(it["name"], it["price_cents"] / 100)] += 1

        if not self._show_confirmation_dialog("Relist Items", grouped, "swap"):
            return

        descriptions = dict(self.store.account_descriptions)

        def _do_swap():
            # Фаза 1: снимаем с продажи
            for apikey, items in to_swap.items():
                contract_ids = [it["contract_id"] for it in items]
                resp = bulk_delist(apikey, contract_ids)
                if not resp:
                    raise RuntimeError("Failed to delist items.")

            # Фаза 2: выставляем заново
            results = {}
            for apikey, items in to_swap.items():
                description = descriptions.get(apikey, "")
                bulk_items = []
                for it in items:
                    item_data = {
                        "asset_id": it["asset_id"],
                        "price": it["price_cents"],
                        "type": "buy_now"
                    }
                    if description:
                        item_data["description"] = description
                    bulk_items.append(item_data)

                resp = bulk_list(apikey, bulk_items)
                results[apikey] = (items, resp)
            return results

        self._set_buttons_enabled(False)

        worker = ApiWorker(_do_swap)
        worker.signals.result.connect(lambda res: self._on_swap_result(res, to_swap))
        worker.signals.error.connect(self._on_swap_error)
        worker.signals.finished.connect(lambda: self._set_buttons_enabled(True))
        self.threadpool.start(worker)

    def _on_swap_result(self, results, to_swap):
        """Обработка результата перевыставления."""
        pw = self.parent_widget
        self.table.setSortingEnabled(False)

        for apikey, items in to_swap.items():
            for it in items:
                self._update_item_as_unsold_by_asset_id(it["asset_id"])

        successful = []
        for apikey, (items, resp) in results.items():
            listings = resp.get("data", []) if isinstance(resp, dict) else resp
            if not listings:
                warning(pw, "Error", "Failed to relist items.")
                self.table.setSortingEnabled(True)
                return

            for i, listing in enumerate(listings):
                if i >= len(items):
                    break
                it = items[i]
                listing_id = listing.get("id")
                if listing_id:
                    self._update_item_as_sold(it["asset_id"], it["price_cents"], listing_id)
                    successful.append((it["name"], it["price_cents"] / 100.0))

        self.table.setSortingEnabled(True)

        if successful:
            self.apply_filters_fn()
            self._show_grouped_operations(successful, "Items Relisted")
            self.table.clearSelection()
        else:
            warning(pw, "Warning", "No items were relisted.")

    def _on_swap_error(self, error):
        """Обработка ошибки перевыставления."""
        e, tb = error
        warning(self.parent_widget, "Error", f"Failed to relist items: {str(e)}")

    def show_user_info(self):
        """Показывает информацию о пользователе."""
        if not self.store.user_infos:
            information(self.parent_widget, "User Info", "No user information available.")
            return

        dialog = QDialog(self.parent_widget)
        Theme.apply_titlebar_theme(dialog)
        dialog.setWindowTitle("User Information")

        layout = QVBoxLayout(dialog)

        label_font = QFont(Theme.FONT_FAMILY, Theme.FONT_SIZE)

        outer_layout = QHBoxLayout()

        for idx, user_info in enumerate(self.store.user_infos):
            vertical_layout = QVBoxLayout()

            # Avatar
            avatar_container = QWidget()
            avatar_container.setFixedSize(100, 100)

            avatar_url = user_info.get("avatar")
            avatar_path = cache_image(avatar_url) if avatar_url else None

            if avatar_path:
                avatar_label = QLabel(avatar_container)
                avatar_label.setFixedSize(100, 100)

                avatar_pixmap = QPixmap(avatar_path)
                rounded_pixmap = QPixmap(100, 100)
                rounded_pixmap.fill(Qt.GlobalColor.transparent)

                painter = QPainter(rounded_pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                path = QPainterPath()
                path.addRoundedRect(QRectF(0, 0, 100, 100), 5, 5)
                painter.setClipPath(path)
                painter.drawPixmap(
                    0, 0,
                    avatar_pixmap.scaled(
                        100, 100,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation
                    )
                )
                painter.end()

                avatar_label.setPixmap(rounded_pixmap)
                avatar_label.move(0, 0)

            avatar_container.setStyleSheet(Theme.avatar_container())

            settings_btn = QPushButton(avatar_container)
            settings_btn.setFixedSize(28, 28)
            settings_btn.move(70, 2)

            settings_icon_path = os.path.join(self.icon_path, "settings.png")
            if os.path.exists(settings_icon_path):
                settings_btn.setIcon(QIcon(settings_icon_path))
                settings_btn.setIconSize(settings_btn.size())

                glow_effect = QGraphicsDropShadowEffect()
                glow_effect.setBlurRadius(8)
                glow_effect.setXOffset(0)
                glow_effect.setYOffset(0)
                glow_effect.setColor(QColor(255, 255, 255, 240))
                settings_btn.setGraphicsEffect(glow_effect)

                settings_btn.setStyleSheet(Theme.settings_button_icon())
            else:
                settings_btn.setText("⚙")
                settings_btn.setStyleSheet(Theme.settings_button_text())

            api_key = user_info.get("api_key")
            settings_btn.clicked.connect(lambda checked, ak=api_key: self.parent_widget.open_account_settings(ak))

            vertical_layout.addWidget(avatar_container, alignment=Qt.AlignmentFlag.AlignHCenter)

            form_layout = QFormLayout()

            def create_labeled_row(label_text, value_text):
                label = QLabel(label_text)
                label.setFont(label_font)
                value = QLabel(value_text)
                value.setFont(label_font)
                form_layout.addRow(label, value)

            create_labeled_row("Username:", user_info.get("username", "N/A"))
            create_labeled_row("Steam ID:", user_info.get("steam_id", "N/A"))
            create_labeled_row("KYC:", user_info.get("know_your_customer", "N/A"))
            create_labeled_row("Balance:", f"${user_info.get('balance', 0) / 100:.2f}")
            create_labeled_row("Pending Balance:", f"${user_info.get('pending_balance', 0) / 100:.2f}")

            statistics = user_info.get("statistics", {})
            create_labeled_row("Total Sales:", f"${statistics.get('total_sales', 0) / 100:.2f}")
            create_labeled_row("Total Purchases:", f"${statistics.get('total_purchases', 0) / 100:.2f}")
            create_labeled_row("Median Trade Time:", f"{statistics.get('median_trade_time', 0) / 60.0:.0f} minutes")
            create_labeled_row("Total Avoided Trades:", str(statistics.get('total_avoided_trades', 0)))
            create_labeled_row("Total Failed Trades:", str(statistics.get('total_failed_trades', 0)))
            create_labeled_row("Total Verified Trades:", str(statistics.get('total_verified_trades', 0)))
            create_labeled_row("Total Trades:", str(statistics.get('total_trades', 0)))

            vertical_layout.addLayout(form_layout)
            outer_layout.addLayout(vertical_layout)

            if idx < len(self.store.user_infos) - 1:
                separator = QWidget()
                separator.setFixedWidth(1)
                separator.setMinimumHeight(300)
                separator.setStyleSheet(Theme.separator_gradient())
                outer_layout.addWidget(separator)

        layout.addLayout(outer_layout)
        dialog.setLayout(layout)
        dialog.exec()
