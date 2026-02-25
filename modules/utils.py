import os
import json
import urllib.request
import urllib.error
import hashlib
import logging
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import threading
from PyQt6.QtCore import QMetaObject, Qt, Q_ARG, QObject, QSettings, pyqtSlot

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CACHE_DIR = os.path.join(_BASE_DIR, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

imageloader_pool = ThreadPoolExecutor(max_workers=4)
cache_lock = threading.Lock()

_downloading = {}
_downloading_lock = threading.Lock()

_callback_receiver = None


class CallbackReceiver(QObject):
    """Принимает и выполняет callbacks в главном потоке Qt."""

    @pyqtSlot(object)
    def _invoke_callback(self, callback_fn):
        try:
            callback_fn()
        except Exception as e:
            print(f"Error in callback: {e}")


def init_callback_receiver():
    """Инициализировать CallbackReceiver. Вызывать после создания QApplication."""
    global _callback_receiver
    _callback_receiver = CallbackReceiver()


def load_config():
    config_path = os.path.join(_BASE_DIR, "config.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Config file not found: {config_path}")
        return {}


def key_id(api_key: str) -> str:
    """Короткий идентификатор ключа для QSettings (без утечки ключа в реестр)."""
    return hashlib.sha256(api_key.encode()).hexdigest()[:16]


def migrate_settings(api_keys: list):
    """Миграция настроек: старые ключи реестра (с plaintext API key) → новые (с хешем).

    Читает старые записи вида account_{api_key}_*, записывает как account_{key_id}_*,
    удаляет старые. Также мигрирует default_api_key.
    """
    settings = QSettings("MyCompany", "SteamInventoryApp")
    migrated = False

    for api_key in api_keys:
        kid = key_id(api_key)
        suffixes = ["_keep_online", "_description"]

        for suffix in suffixes:
            old_key = f"account_{api_key}{suffix}"
            new_key = f"account_{kid}{suffix}"

            if settings.contains(old_key):
                value = settings.value(old_key)
                if not settings.contains(new_key):
                    settings.setValue(new_key, value)
                settings.remove(old_key)
                migrated = True

    # default_api_key: если хранится сам ключ — заменить на хеш
    saved_default = settings.value("default_api_key", "")
    if saved_default and saved_default in api_keys:
        settings.setValue("default_api_key", key_id(saved_default))
        migrated = True

    if migrated:
        settings.sync()
        logging.info("Settings migrated: API keys removed from registry")


def get_image_extension(url: str, content_type: str = None) -> str:
    """Определяет расширение файла на основе URL или Content-Type."""
    if '.' in url.split('/')[-1]:
        parts = url.split('/')[-1].split('.')
        if len(parts) > 1:
            ext = parts[-1].split('?')[0]
            if ext.lower() in ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg']:
                return f'.{ext.lower()}'

    if content_type:
        if 'png' in content_type.lower():
            return '.png'
        elif 'jpeg' in content_type.lower() or 'jpg' in content_type.lower():
            return '.jpg'
        elif 'gif' in content_type.lower():
            return '.gif'
        elif 'webp' in content_type.lower():
            return '.webp'
        elif 'svg' in content_type.lower():
            return '.svg'

    return '.png'


def get_hashed_filename(url: str, extension: str) -> str:
    """Создает короткое хэшированное имя файла на основе URL."""
    url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
    return f"{url_hash}{extension}"


def invoke_callback_in_main_thread(callback, *args):
    """Вызывает callback в главном потоке Qt."""
    if _callback_receiver and callback:
        def wrapper():
            callback(*args)

        QMetaObject.invokeMethod(
            _callback_receiver,
            "_invoke_callback",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(object, wrapper)
        )
    elif callback:
        callback(*args)


def cache_image(url: str):
    """Кэширует изображение с коротким хэшированным именем файла."""
    if not url:
        return None

    extension = get_image_extension(url)
    hashed_filename = get_hashed_filename(url, extension)
    filepath = os.path.join(CACHE_DIR, hashed_filename)

    if os.path.exists(filepath):
        return filepath

    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            content_type = response.headers.get('Content-Type', '')
            extension = get_image_extension(url, content_type)
            hashed_filename = get_hashed_filename(url, extension)
            filepath = os.path.join(CACHE_DIR, hashed_filename)

            if os.path.exists(filepath):
                return filepath

            with open(filepath, 'wb') as f:
                f.write(response.read())

            return filepath

    except Exception as e:
        print(f"Failed to download image from {url}: {e}")
        return None


def cache_image_async(url: str, callback=None):
    """Асинхронно кэширует изображение с защитой от race condition."""
    if not url:
        if callback:
            callback(None)
        return

    if not url.startswith("http"):
        url = f"https://steamcommunity-a.akamaihd.net/economy/image/{url}"

    extension = get_image_extension(url)
    hashed_filename = get_hashed_filename(url, extension)
    filepath = os.path.join(CACHE_DIR, hashed_filename)

    if os.path.exists(filepath):
        if callback:
            callback(filepath)
        return

    with _downloading_lock:
        if url in _downloading:
            if callback:
                _downloading[url].append(callback)
            return
        else:
            _downloading[url] = [callback] if callback else []

    def download():
        try:
            if os.path.exists(filepath):
                with _downloading_lock:
                    callbacks = _downloading.pop(url, [])
                for cb in callbacks:
                    if cb:
                        invoke_callback_in_main_thread(cb, filepath)
                return

            with urllib.request.urlopen(url, timeout=10) as response:
                content_type = response.headers.get('Content-Type', '')
                final_ext = get_image_extension(url, content_type)
                final_name = get_hashed_filename(url, final_ext)
                filepath_final = os.path.join(CACHE_DIR, final_name)

                temp_filepath = filepath_final + '.tmp'
                with open(temp_filepath, 'wb') as f:
                    f.write(response.read())

                with cache_lock:
                    if not os.path.exists(filepath_final):
                        os.replace(temp_filepath, filepath_final)
                    elif os.path.exists(temp_filepath):
                        os.remove(temp_filepath)

                with _downloading_lock:
                    callbacks = _downloading.pop(url, [])
                for cb in callbacks:
                    if cb:
                        invoke_callback_in_main_thread(cb, filepath_final)

        except Exception as e:
            print(f"Failed to download image from {url}: {e}")
            with _downloading_lock:
                callbacks = _downloading.pop(url, [])
            for cb in callbacks:
                if cb:
                    invoke_callback_in_main_thread(cb, None)

    imageloader_pool.submit(download)


def calculate_days_on_sale(created_at: str) -> str:
    """Вычисляет количество дней и часов с момента выставления на продажу."""
    try:
        created_at_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = now - created_at_dt

        days = delta.days
        hours = delta.seconds // 3600

        return f"{days}d {hours}h"
    except Exception as e:
        print(f"Error parsing date: {e}")
        return ""
