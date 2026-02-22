# modules/workers.py

from PyQt6.QtCore import QObject, pyqtSignal, QRunnable, pyqtSlot, QThread, QMutex

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
        self._api_keys = []
        self._mutex = QMutex()
        self._running = True
        self.interval = 20

    def set_api_keys(self, keys: list):
        """Установить список активных API-ключей."""
        self._mutex.lock()
        self._api_keys = keys.copy()
        self._mutex.unlock()

    def add_api_key(self, api_key: str):
        """Добавить API-ключ в список."""
        self._mutex.lock()
        if api_key not in self._api_keys:
            self._api_keys.append(api_key)
        self._mutex.unlock()

    def remove_api_key(self, api_key: str):
        """Удалить API-ключ из списка."""
        self._mutex.lock()
        if api_key in self._api_keys:
            self._api_keys.remove(api_key)
        self._mutex.unlock()

    def stop(self):
        """Остановить worker."""
        self._running = False

    def run(self):
        """Главный цикл - пингуем все активные ключи каждые 20 секунд."""
        while self._running:
            self._mutex.lock()
            keys_snapshot = self._api_keys.copy()
            self._mutex.unlock()

            for api_key in keys_snapshot:
                if not self._running:
                    break
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
