# modules/collections_manager.py

import os
import json
from datetime import datetime, timezone

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CACHE_DIR = os.path.join(_BASE_DIR, "cache")
COLLECTIONS_FILE = os.path.join(CACHE_DIR, "collections.json")

os.makedirs(CACHE_DIR, exist_ok=True)

UPDATE_INTERVAL_DAYS = 30

# name → key (ключи заполнятся при загрузке схемы)
DEFAULT_COLLECTIONS = {
    "2018 Inferno Collection": "",
    "2018 Nuke Collection": "",
    "2021 Dust 2 Collection": "",
    "2021 Mirage Collection": "",
    "2021 Train Collection": "",
    "2021 Vertigo Collection": "",
    "Achroma Collection": "",
    "Alpha Collection": "",
    "Ancient Collection": "",
    "Anubis Collection": "",
    "Arms Deal 2 Collection": "",
    "Arms Deal 3 Collection": "",
    "Arms Deal Collection": "",
    "Ascent Collection": "",
    "Assault Collection": "",
    "Aztec Collection": "",
    "Baggage Collection": "",
    "Bank Collection": "",
    "Blacksite Collection": "",
    "Boreal Collection": "",
    "Bravo Collection": "",
    "Breakout Collection": "",
    "CS20 Collection": "",
    "Cache Collection": "",
    "Canals Collection": "",
    "Chop Shop Collection": "",
    "Chroma 2 Collection": "",
    "Chroma 3 Collection": "",
    "Chroma Collection": "",
    "Clutch Collection": "",
    "Cobblestone Collection": "",
    "Control Collection": "",
    "Danger Zone Collection": "",
    "Dreams & Nightmares Collection": "",
    "Dust 2 Collection": "",
    "Dust Collection": "",
    "Falchion Collection": "",
    "Fever Collection": "",
    "Fracture Collection": "",
    "Gallery Collection": "",
    "Gamma 2 Collection": "",
    "Gamma Collection": "",
    "Genesis Collection": "",
    "Glove Collection": "",
    "Gods and Monsters Collection": "",
    "Graphic Design Collection": "",
    "Harlequin Collection": "",
    "Havoc Collection": "",
    "Horizon Collection": "",
    "Huntsman Collection": "",
    "Inferno Collection": "",
    "Italy Collection": "",
    "Kilowatt Collection": "",
    "Lake Collection": "",
    "Limited Edition Item": "",
    "Militia Collection": "",
    "Mirage Collection": "",
    "Norse Collection": "",
    "Nuke Collection": "",
    "Office Collection": "",
    "Operation Broken Fang Collection": "",
    "Operation Hydra Collection": "",
    "Operation Riptide Collection": "",
    "Overpass 2024 Collection": "",
    "Overpass Collection": "",
    "Phoenix Collection": "",
    "Prisma 2 Collection": "",
    "Prisma Collection": "",
    "Radiant Collection": "",
    "Recoil Collection": "",
    "Revolution Collection": "",
    "Revolver Case Collection": "",
    "Rising Sun Collection": "",
    "Safehouse Collection": "",
    "Shadow Collection": "",
    "Shattered Web Collection": "",
    "Snakebite Collection": "",
    "Spectrum 2 Collection": "",
    "Spectrum Collection": "",
    "Sport & Field Collection": "",
    "St. Marc Collection": "",
    "Train 2025 Collection": "",
    "Train Collection": "",
    "Vanguard Collection": "",
    "Vertigo Collection": "",
    "Wildfire Collection": "",
    "Winter Offensive Collection": "",
    "X-Ray Collection": "",
    "eSports 2013 Collection": "",
    "eSports 2013 Winter Collection": "",
    "eSports 2014 Summer Collection": "",
}


def _load_raw():
    """Загружает весь JSON из файла."""
    if not os.path.exists(COLLECTIONS_FILE):
        return None
    try:
        with open(COLLECTIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading collections: {e}")
        return None


def _load_collection_map():
    """Загружает dict name→key из файла."""
    data = _load_raw()
    if data is None:
        return None

    # Миграция со старого формата
    if "collections" in data and isinstance(data["collections"], list):
        keys = data.get("collection_keys", {})
        merged = {name: keys.get(name, "") for name in data["collections"]}
        return merged

    return data.get("data", None)


def _save(collection_map, set_updated=True):
    """Сохраняет name→key dict в файл."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    sorted_map = dict(sorted(collection_map.items()))
    out = {"data": sorted_map}
    if set_updated:
        out["last_updated"] = datetime.now(timezone.utc).isoformat()
    try:
        with open(COLLECTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving collections: {e}")


def load_collections():
    """Загружает список названий коллекций (для UI)."""
    cmap = _load_collection_map()
    if cmap is None:
        _save(DEFAULT_COLLECTIONS, set_updated=False)
        return sorted(DEFAULT_COLLECTIONS.keys())
    return sorted(cmap.keys())


def needs_update():
    """Проверяет нужно ли обновлять коллекции (раз в 30 дней)."""
    data = _load_raw()
    if data is None:
        return True

    last_updated = data.get("last_updated")
    if not last_updated:
        return True

    try:
        dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - dt).days
        return age >= UPDATE_INTERVAL_DAYS
    except Exception:
        return True


def update_collections_from_schema(schema_data):
    """Обновляет коллекции на основе данных из API схемы."""
    if not schema_data or "collections" not in schema_data:
        return False

    current = _load_collection_map() or dict(DEFAULT_COLLECTIONS)

    changed = False
    for collection in schema_data["collections"]:
        name = collection.get("name", "")
        key = collection.get("key", "")
        if not name:
            continue
        if name.startswith("The "):
            name = name[4:]

        if name not in current:
            current[name] = key
            changed = True
        elif key and current[name] != key:
            current[name] = key
            changed = True

    _save(current, set_updated=True)
    return changed


def get_collections():
    """Возвращает список названий коллекций (для UI)."""
    return load_collections()


def get_collection_keys():
    """Возвращает маппинг name → key (для API запросов)."""
    cmap = _load_collection_map()
    if cmap is None:
        return {}
    return {name: key for name, key in cmap.items() if key}
