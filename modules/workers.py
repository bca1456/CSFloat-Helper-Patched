# modules/workers.py

from PyQt6.QtCore import QObject, pyqtSignal, QRunnable, pyqtSlot, QThread

import traceback
import time

from modules.api import get_user_info


class WorkerSignals(QObject):
    """Сигналы для worker threads."""

    result = pyqtSignal(object)
    error = pyqtSignal(tuple)
    finished = pyqtSignal()


class ApiWorker(QRunnable):
    """Worker для выполнения API-запросов в фоне."""

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.signals.result.emit(result)
        except Exception as e:
            traceback.print_exc()
            self.signals.error.emit((e, traceback.format_exc()))
        finally:
            self.signals.finished.emit()


class KeepOnlineWorker(QThread):
    """Worker для поддержания онлайна аккаунтов (GET /me каждые 20 секунд)."""

    error_occurred = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.api_keys = []
        self._running = True
        self.interval = 20

    def set_api_keys(self, keys: list):
        """Установить список активных API-ключей."""
        self.api_keys = keys.copy()

    def add_api_key(self, api_key: str):
        """Добавить API-ключ в список."""
        if api_key not in self.api_keys:
            self.api_keys.append(api_key)

    def remove_api_key(self, api_key: str):
        """Удалить API-ключ из списка."""
        if api_key in self.api_keys:
            self.api_keys.remove(api_key)

    def stop(self):
        """Остановить worker."""
        self._running = False

    def run(self):
        """Главный цикл - пингуем все активные ключи каждые 20 секунд."""
        while self._running:
            for api_key in self.api_keys.copy():
                try:
                    user = get_user_info(api_key)
                    if user is None:
                        raise RuntimeError("GET /me returned no user")
                except Exception as e:
                    self.error_occurred.emit(api_key, str(e))

            for _ in range(self.interval):
                if not self._running:
                    break
                time.sleep(1)
