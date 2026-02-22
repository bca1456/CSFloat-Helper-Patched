# modules/models/inventory_store.py

from PyQt6.QtCore import QObject


class InventoryStore(QObject):
    """Хранилище данных инвентаря и пользователей."""

    MAX_PRICE = 10_000_000
    MIN_PRICE = 3

    def __init__(self, api_keys, parent=None):
        super().__init__(parent)
        self.api_keys = api_keys
        self.user_infos = []
        self.inventory = []
        self.stall = []
        self.account_descriptions = {}
        self.stall_loaded_count = 0
        self.stall_total_count = 0

    def add_user_result(self, api_key, user_info, inventory):
        """Добавить результат загрузки пользователя."""
        if user_info:
            user_info["api_key"] = api_key
            self.user_infos.append(user_info)

        if inventory:
            for it in inventory:
                it["api_key"] = api_key
            self.inventory.extend(inventory)

    def add_stall_result(self, stall_data):
        """Добавить результат загрузки stall."""
        if stall_data:
            self.stall.extend(stall_data)
        self.stall_loaded_count += 1

    def all_users_loaded(self):
        """Все ли пользователи загружены."""
        return len(self.user_infos) == len(self.api_keys)

    def all_stalls_loaded(self):
        """Все ли stall данные загружены."""
        return self.stall_loaded_count >= self.stall_total_count

    def clear(self):
        """Сбросить все данные."""
        self.user_infos.clear()
        self.inventory.clear()
        self.stall.clear()
        self.stall_loaded_count = 0
        self.stall_total_count = 0
