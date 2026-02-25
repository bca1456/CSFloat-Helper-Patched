# modules/ui_tab1/main_widget.py

import logging
import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QCompleter
from modules.messagebox import critical
from PyQt6.QtGui import QCursor, QIcon
from PyQt6.QtCore import Qt, QSettings, pyqtSignal, pyqtSlot, QEvent, QThreadPool

from modules.theme import Theme
from modules.api import get_user_info, get_inventory_data, get_stall_data, get_schema
from modules.workers import ApiWorker, KeepOnlineWorker
from modules.collections_manager import update_collections_from_schema, get_collections
from modules.utils import key_id, migrate_settings, shutdown_image_pool
from .constants import refresh_collections
from modules.models.columns import (
    COL_NAME, COL_STICKERS, COL_KEYCHAINS, COL_FLOAT, COL_SEED,
    COL_DAYS, COL_PRICE, COL_LISTING_ID, COL_ASSET_ID, COL_CREATED_AT,
    COL_PRICE_VALUE, COL_API_KEY, COL_COLLECTION, COL_RARITY, COL_WEAR,
    DEFAULT_COLUMN_WIDTHS,
)
from modules.models.inventory_store import InventoryStore
from .custom_widgets import CustomToolTip, AccountSettingsDialog, ToggleSwitch
from .ui_components import (
    create_filter_inputs, create_float_filters,
    create_collection_filter, create_rarity_buttons, create_condition_buttons,
    create_action_buttons, create_inventory_table, change_icon_color,
)
from .filters import FilterController
from .table_population import TablePopulator
from .item_operations import ItemOperations


class Tab1(QWidget):
    apikey_changed = pyqtSignal(str)

    def __init__(self, api_keys, icon_path, parent=None):
        super().__init__(parent)

        self.api_keys = api_keys
        self.icon_path = icon_path
        self.settings = QSettings("MyCompany", "SteamInventoryApp")

        migrate_settings(api_keys)

        saved_id = self.settings.value("default_api_key", "")
        self.default_api_key = next(
            (k for k in api_keys if key_id(k) == saved_id),
            api_keys[0],
        )

        self.store = InventoryStore(api_keys, parent=self)
        self.filter_ctrl = FilterController(parent=self)

        for api_key in self.api_keys:
            desc = self.settings.value(f"account_{key_id(api_key)}_description", "", type=str)
            self.store.account_descriptions[api_key] = desc

        self.price_sort_order = Qt.SortOrder.AscendingOrder
        self.days_sort_order = Qt.SortOrder.AscendingOrder
        self.name_sort_order = Qt.SortOrder.AscendingOrder
        self.float_sort_order = Qt.SortOrder.AscendingOrder
        self.seed_sort_order = Qt.SortOrder.AscendingOrder

        self.tooltip = CustomToolTip()

        self.keep_online_worker = None
        self.init_keep_online_worker()

        self.initUI()

    def init_keep_online_worker(self):
        """Initialize Keep Online Worker."""
        self.keep_online_worker = KeepOnlineWorker()
        self.keep_online_worker.error_occurred.connect(self.on_keep_online_error)

        active_keys = []
        for api_key in self.api_keys:
            if self.settings.value(f"account_{key_id(api_key)}_keep_online", False, type=bool):
                active_keys.append(api_key)

        if active_keys:
            self.keep_online_worker.set_api_keys(active_keys)
            self.keep_online_worker.start()

    def on_keep_online_error(self, api_key: str, error_msg: str):
        """Handle Keep Online errors."""
        logging.warning(f"Keep Online error for {api_key[:8]}...: {error_msg}")

    def open_account_settings(self, api_key: str):
        """Open account settings dialog."""
        dialog = AccountSettingsDialog(api_key, self.settings, self)
        dialog.settings_saved.connect(self.on_settings_saved)
        dialog.exec()

    def on_settings_saved(self, api_key: str, keep_online: bool, description: str):
        """Handle account settings saved."""
        self.store.account_descriptions[api_key] = description
        self.settings.setValue(f"account_{key_id(api_key)}_keep_online", keep_online)
        self.settings.setValue(f"account_{key_id(api_key)}_description", description)
        self.settings.sync()

        if keep_online:
            self.keep_online_worker.add_api_key(api_key)
            if not self.keep_online_worker.isRunning():
                self.keep_online_worker.start()
        else:
            self.keep_online_worker.remove_api_key(api_key)

        logging.info(f"Settings saved for {api_key[:8]}...")
        logging.info(f"  Keep Online: {keep_online}")
        logging.info(f"  Description: {description}")

    def initUI(self):
        central_widget = QWidget(self)
        main_layout = QVBoxLayout(central_widget)
        self.setLayout(main_layout)

        self.name_filter, self.sticker_filter = create_filter_inputs(self)
        self.name_filter.textChanged.connect(self.apply_filters)
        self.sticker_filter.textChanged.connect(self.apply_filters)

        self.float_min_filter, self.float_max_filter = create_float_filters(self)
        self.float_min_filter.textChanged.connect(self.apply_filters)
        self.float_max_filter.textChanged.connect(self.apply_filters)

        self.collection_edit, self.dropdown_button = create_collection_filter(
            self, self.apply_filters,
        )

        self.rarity_buttons = create_rarity_buttons(self, self.update_rarity_filters)
        self.condition_buttons = create_condition_buttons(self, self.update_condition_filters)

        self.price_input, self.action_buttons = create_action_buttons(
            self, self.icon_path, {
                "sell": self.sell_items,
                "change_price": self.change_item_price,
                "delist": self.delist_items,
                "swap": self.swap_items,
                "user_info": self.show_user_info,
            },
        )

        self.inventory_table = create_inventory_table(
            self, self.icon_path, self.handle_header_click,
        )

        self.populator = TablePopulator(
            self.inventory_table, self.icon_path, self.font(), self,
        )

        self.ops = ItemOperations(
            self.inventory_table, self.store, self.icon_path,
            self.font(), self, self.apply_filters,
        )
        self.ops.bind_price_input(self.price_input)
        self.ops.bind_action_buttons(self.action_buttons)

        self.filter_ctrl.bind(self.inventory_table, {
            "name_filter": self.name_filter,
            "sticker_filter": self.sticker_filter,
            "float_min_filter": self.float_min_filter,
            "float_max_filter": self.float_max_filter,
            "collection_edit": self.collection_edit,
        })

        self.load_column_widths()

        self.theme_switch = ToggleSwitch(self, show_text=False, size=(28, 14))
        self.theme_switch.setChecked(Theme.current_theme == "dark")
        self.theme_switch.toggled_signal.connect(self._on_theme_toggle)
        self._position_theme_switch()

    def _on_theme_toggle(self, checked):
        self.window().switch_theme()

    def _position_theme_switch(self):
        if hasattr(self, 'theme_switch'):
            self.theme_switch.move(self.width() - 40, self.height() - 24)

    def refresh_styles(self):
        """Переприменить стили всех виджетов после смены темы."""
        from modules.models.columns import COL_KEYCHAINS
        from .constants import RARITY_COLOR_MAP

        # Фильтры
        self.name_filter.setStyleSheet(Theme.input_style())
        self.sticker_filter.setStyleSheet(Theme.input_style())
        self.float_min_filter.setStyleSheet(Theme.input_style())
        self.float_max_filter.setStyleSheet(Theme.input_style())
        self.collection_edit.setStyleSheet(Theme.input_style_with_placeholder())
        self.dropdown_button.setStyleSheet(Theme.dropdown_button())
        self.price_input.setStyleSheet(Theme.input_style())

        # Кнопки условий
        labels = ["FN", "MW", "FT", "WW", "BS"]
        for i, btn in enumerate(self.condition_buttons):
            if i == 0:
                pos = "first"
            elif i == len(labels) - 1:
                pos = "last"
            else:
                pos = "middle"
            btn.setStyleSheet(Theme.condition_button(pos))

        # Кнопки редкости
        rarities = list(RARITY_COLOR_MAP.keys())
        for i, btn in enumerate(self.rarity_buttons):
            if i < len(rarities):
                btn.setStyleSheet(Theme.rarity_button(RARITY_COLOR_MAP[rarities[i]]))

        # Иконки действий
        icon_map = {
            "sell": "sell.png",
            "change_price": "change.png",
            "delist": "delist.png",
            "relist": "swap.png",
            "user_info": "info.png",
        }
        for key, btn in self.action_buttons.items():
            icon_file = icon_map.get(key)
            if icon_file:
                full_path = os.path.join(self.icon_path, icon_file)
                colored = change_icon_color(full_path, Theme.PRIMARY)
                btn.setIcon(QIcon(colored))

        # Таблица
        self.inventory_table.setStyleSheet(Theme.table_style())
        self.inventory_table.horizontalHeader().setStyleSheet(Theme.table_header_style())

        # Иконка keychain в заголовке
        keychain_path = os.path.join(self.icon_path, "keychain.png")
        if os.path.exists(keychain_path):
            colored = change_icon_color(keychain_path, Theme.PRIMARY)
            self.inventory_table.horizontalHeaderItem(COL_KEYCHAINS).setIcon(QIcon(colored))

        # Тултип
        self.tooltip.setStyleSheet(Theme.tooltip_style())
        self.theme_switch.update()

    def eventFilter(self, obj, event):
        from PyQt6.QtWidgets import QWidget

        if isinstance(obj, QWidget) and hasattr(obj, '_tooltip_text'):
            et = event.type()

            if et == QEvent.Type.ToolTip:
                try:
                    gp = event.globalPosition().toPoint()
                except AttributeError:
                    gp = QCursor.pos()

                self.tooltip.show_text(getattr(obj, '_tooltip_text', ''), gp)
                return True

            if et == QEvent.Type.MouseMove:
                self.tooltip.move_to_cursor()
                return False

            if et == QEvent.Type.Leave:
                self.tooltip.hide()
                return False

        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)

        if hasattr(self, 'inventory_table'):
            new_table_height = self.height() - 132 - 34
            if new_table_height >= 620:
                self.inventory_table.setFixedHeight(new_table_height)

        self._position_theme_switch()

    def load_data(self, threadpool):
        """Load data from API."""
        self.store.clear()
        self.store.stall_total_count = len(self.api_keys)

        self.inventory_table.setRowCount(0)
        self.inventory_table.setSortingEnabled(False)
        self.ops._set_buttons_enabled(False)

        schema_worker = ApiWorker(self.fetch_schema)
        schema_worker.signals.result.connect(self.handle_schema_result)
        schema_worker.signals.error.connect(self.handle_schema_error)
        threadpool.start(schema_worker)

        for api_key in self.api_keys:
            worker = ApiWorker(self.fetch_user_and_inventory, api_key)
            worker.signals.result.connect(self.handle_api_result)
            worker.signals.error.connect(self.handle_api_error)
            threadpool.start(worker)

    def fetch_schema(self):
        """Fetch schema from API."""
        return get_schema()

    @pyqtSlot(object)
    def handle_schema_result(self, schema_data):
        """Handle schema result."""
        if schema_data:
            updated = update_collections_from_schema(schema_data)
            if updated:
                refresh_collections()
                self.update_collection_completer()
        else:
            logging.warning("Failed to load schema")

    @pyqtSlot(tuple)
    def handle_schema_error(self, error):
        """Handle schema error."""
        e, tb = error
        logging.error(f"Schema Error: {e}\n{tb}")

    def update_collection_completer(self):
        collections = get_collections()
        completer = QCompleter(collections, self)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.activated.connect(self.on_collection_selected)
        self.collection_edit.setCompleter(completer)

    def fetch_user_and_inventory(self, api_key):
        """Fetch user info and inventory."""
        user_info = get_user_info(api_key)
        inventory = get_inventory_data(api_key)
        return {"api_key": api_key, "user_info": user_info, "inventory": inventory}

    @pyqtSlot(object)
    def handle_api_result(self, result):
        """Handle user info and inventory result."""
        api_key = result.get("api_key")
        user_info = result.get("user_info")
        inventory = result.get("inventory")

        self.store.add_user_result(api_key, user_info, inventory)

        steam_id = user_info.get("steam_id") if user_info else None
        worker = ApiWorker(self.fetch_stall_data, api_key, steam_id)
        worker.signals.result.connect(self.handle_stall_result)
        worker.signals.error.connect(self.handle_stall_error)
        QThreadPool.globalInstance().start(worker)

    @pyqtSlot(tuple)
    def handle_api_error(self, error):
        """Handle API error."""
        e, tb = error
        logging.error(f"API Error: {e}\n{tb}")
        critical(self, "API Error", f"An error occurred while fetching data:\n{e}")

        self.store.add_stall_result([])
        if self.store.all_stalls_loaded():
            self.inventory_table.setSortingEnabled(True)
            self.ops._set_buttons_enabled(True)

    def fetch_stall_data(self, api_key, steam_id):
        """Fetch stall data."""
        if not steam_id:
            return {"api_key": api_key, "stall": []}

        stall_data = get_stall_data(api_key, steam_id)
        return {"api_key": api_key, "stall": stall_data or []}

    @pyqtSlot(object)
    def handle_stall_result(self, result):
        """Handle stall data result."""
        api_key = result.get("api_key")
        stall_data = result.get("stall", [])
        self.store.add_stall_result(stall_data)

        account_inventory = [item for item in self.store.inventory if item.get("api_key") == api_key]
        self.populator.append(account_inventory, stall_data)

        if self.store.all_stalls_loaded():
            self.inventory_table.setSortingEnabled(True)
            self.ops._set_buttons_enabled(True)

    @pyqtSlot(tuple)
    def handle_stall_error(self, error):
        """Handle stall data error."""
        e, tb = error
        logging.error(f"Stall Data Error: {e}\n{tb}")

        self.store.add_stall_result([])

        if self.store.all_stalls_loaded():
            self.inventory_table.setSortingEnabled(True)
            self.ops._set_buttons_enabled(True)

    def apply_filters(self):
        self.filter_ctrl.apply()

    @pyqtSlot(bool)
    def update_rarity_filters(self, checked):
        btn = self.sender()
        if btn:
            self.filter_ctrl.update_rarity(btn.rarity, checked)

    @pyqtSlot(bool)
    def update_condition_filters(self, checked):
        btn = self.sender()
        if btn:
            self.filter_ctrl.update_condition(btn.wear_condition, checked)

    def sell_items(self):
        self.ops.sell_items()

    def change_item_price(self):
        self.ops.change_item_price()

    def delist_items(self):
        self.ops.delist_items()

    def swap_items(self):
        self.ops.swap_items()

    def show_user_info(self):
        self.ops.show_user_info()

    def on_collection_selected(self, text):
        self.collection_edit.setText(text)
        self.apply_filters()

    def handle_header_click(self, logical_index: int):
        if logical_index == COL_NAME:
            self.name_sort_order = (
                Qt.SortOrder.DescendingOrder if self.name_sort_order == Qt.SortOrder.AscendingOrder
                else Qt.SortOrder.AscendingOrder
            )
            self.inventory_table.sortItems(COL_NAME, self.name_sort_order)
            self.filter_ctrl.last_sorted_column = COL_NAME
            self.filter_ctrl.last_sort_order = self.name_sort_order

        elif logical_index == COL_FLOAT:
            self.float_sort_order = (
                Qt.SortOrder.DescendingOrder if self.float_sort_order == Qt.SortOrder.AscendingOrder
                else Qt.SortOrder.AscendingOrder
            )
            self.inventory_table.sortItems(COL_FLOAT, self.float_sort_order)
            self.filter_ctrl.last_sorted_column = COL_FLOAT
            self.filter_ctrl.last_sort_order = self.float_sort_order

        elif logical_index == COL_SEED:
            self.seed_sort_order = (
                Qt.SortOrder.DescendingOrder if self.seed_sort_order == Qt.SortOrder.AscendingOrder
                else Qt.SortOrder.AscendingOrder
            )
            self.inventory_table.sortItems(COL_SEED, self.seed_sort_order)
            self.filter_ctrl.last_sorted_column = COL_SEED
            self.filter_ctrl.last_sort_order = self.seed_sort_order

        elif logical_index == COL_PRICE:
            self.price_sort_order = (
                Qt.SortOrder.DescendingOrder if self.price_sort_order == Qt.SortOrder.AscendingOrder
                else Qt.SortOrder.AscendingOrder
            )
            self.inventory_table.sortItems(COL_PRICE_VALUE, self.price_sort_order)
            self.filter_ctrl.last_sorted_column = COL_PRICE_VALUE
            self.filter_ctrl.last_sort_order = self.price_sort_order

        elif logical_index == COL_DAYS:
            self.days_sort_order = (
                Qt.SortOrder.DescendingOrder if self.days_sort_order == Qt.SortOrder.AscendingOrder
                else Qt.SortOrder.AscendingOrder
            )
            self.inventory_table.sortItems(COL_CREATED_AT, self.days_sort_order)
            self.filter_ctrl.last_sorted_column = COL_CREATED_AT
            self.filter_ctrl.last_sort_order = self.days_sort_order

    def load_column_widths(self):
        for i in range(self.inventory_table.columnCount()):
            key = f"tab1_column_width_{i}"
            if self.settings.contains(key):
                self.inventory_table.setColumnWidth(i, self.settings.value(key, type=int))
            else:
                self.inventory_table.setColumnWidth(i, DEFAULT_COLUMN_WIDTHS[i])

    def save_column_widths(self):
        for i in range(self.inventory_table.columnCount()):
            self.settings.setValue(f"tab1_column_width_{i}", self.inventory_table.columnWidth(i))

    def cleanup(self):
        """Останавливает фоновые потоки. Вызывается из SteamInventoryApp.closeEvent."""
        if self.keep_online_worker and self.keep_online_worker.isRunning():
            self.keep_online_worker.stop()
            self.keep_online_worker.wait(3000)
        shutdown_image_pool()
