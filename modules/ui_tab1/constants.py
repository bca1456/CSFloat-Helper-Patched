# modules/ui_tab1/constants.py

from PyQt6.QtGui import QColor
from modules.collections_manager import get_collections

RARITY_COLOR_MAP = {
    1: QColor(176, 195, 217),  # Consumer Grade
    2: QColor(94, 152, 217),   # Industrial Grade
    3: QColor(75, 105, 255),   # Mil-Spec Grade
    4: QColor(136, 71, 255),   # Restricted
    5: QColor(211, 44, 230),   # Classified
    6: QColor(235, 75, 75),    # Covert
    7: QColor("orange"),       # StatTrak
    8: QColor(228, 174, 57),   # Souvenir
}

_collections_cache = None


def get_cached_collections():
    """Ленивая загрузка коллекций — вызов get_collections() при первом обращении."""
    global _collections_cache
    if _collections_cache is None:
        _collections_cache = get_collections()
    return _collections_cache


def refresh_collections():
    """Сбросить кэш коллекций для повторной загрузки."""
    global _collections_cache
    _collections_cache = None

WEAR_CONDITIONS_MAP = {
    "FN": "Factory New",
    "MW": "Minimal Wear",
    "FT": "Field-Tested",
    "WW": "Well-Worn",
    "BS": "Battle-Scarred",
}
