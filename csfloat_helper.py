import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon, QFontDatabase, QFont
from modules.ui import SteamInventoryApp
from modules.utils import load_config, init_callback_receiver


def main():
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