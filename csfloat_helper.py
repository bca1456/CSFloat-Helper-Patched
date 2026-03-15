import sys
import os
import logging
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon, QFontDatabase, QFont
from modules.ui import SteamInventoryApp
from modules.utils import load_config, init_callback_receiver


def _setup_logging():
    """Пишет лог в файл (при запуске через pythonw консоль недоступна)."""
    log_dir = os.path.dirname(os.path.abspath(__file__))
    log_file = os.path.join(log_dir, "csfloat_helper.log")
    try:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        fh.setFormatter(fmt)
        root = logging.getLogger()
        root.addHandler(fh)
        root.setLevel(logging.DEBUG)
    except Exception:
        pass


def main():
    _setup_logging()
    if sys.platform == "win32":
        import ctypes
        myappid = 'csfloat.helper.app.2'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    app = QApplication(sys.argv)
    init_callback_receiver()

    font_path = os.path.join(os.path.dirname(__file__), "utils", "fonts", "Oswald.ttf")
    if os.path.exists(font_path):
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id != -1:
            font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
            app_font = QFont(font_family)
            app_font.setPointSize(11)
            app_font.setWeight(QFont.Weight.Normal)
            app.setFont(app_font)

    icon_path = os.path.join(os.path.dirname(__file__), "utils", "icons", "steam.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    else:
        print(f"[!] Icon not found: {icon_path}")

    # Загрузка конфигурации и API-ключей
    config = load_config()
    api_keys = config.get("api_keys", [])
    if not api_keys:
        print("No API keys found in the config file.")
        sys.exit(1)

    # Создание окна
    window = SteamInventoryApp(api_keys=api_keys)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()