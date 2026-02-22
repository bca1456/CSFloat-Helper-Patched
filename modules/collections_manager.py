# modules/collections_manager.py

import os
import json
from datetime import datetime, timezone

CACHE_DIR = "cache"
COLLECTIONS_FILE = os.path.join(CACHE_DIR, "collections.json")

os.makedirs(CACHE_DIR, exist_ok=True)

DEFAULT_COLLECTIONS = [
    "2018 Inferno Collection",
    "2018 Nuke Collection",
    "2021 Dust 2 Collection",
    "2021 Mirage Collection",
    "2021 Train Collection",
    "2021 Vertigo Collection",
    "Achroma Collection",
    "Alpha Collection",
    "Ancient Collection",
    "Anubis Collection",
    "Arms Deal 2 Collection",
    "Arms Deal 3 Collection",
    "Arms Deal Collection",
    "Ascent Collection",
    "Assault Collection",
    "Aztec Collection",
    "Baggage Collection",
    "Bank Collection",
    "Blacksite Collection",
    "Boreal Collection",
    "Bravo Collection",
    "Breakout Collection",
    "CS20 Collection",
    "Cache Collection",
    "Canals Collection",
    "Chop Shop Collection",
    "Chroma 2 Collection",
    "Chroma 3 Collection",
    "Chroma Collection",
    "Clutch Collection",
    "Cobblestone Collection",
    "Control Collection",
    "Danger Zone Collection",
    "Dreams & Nightmares Collection",
    "Dust 2 Collection",
    "Dust Collection",
    "Falchion Collection",
    "Fever Collection",
    "Fracture Collection",
    "Gallery Collection",
    "Gamma 2 Collection",
    "Gamma Collection",
    "Genesis Collection",
    "Glove Collection",
    "Gods and Monsters Collection",
    "Graphic Design Collection",
    "Harlequin Collection",
    "Havoc Collection",
    "Horizon Collection",
    "Huntsman Collection",
    "Inferno Collection",
    "Italy Collection",
    "Kilowatt Collection",
    "Lake Collection",
    "Limited Edition Item",
    "Militia Collection",
    "Mirage Collection",
    "Norse Collection",
    "Nuke Collection",
    "Office Collection",
    "Operation Broken Fang Collection",
    "Operation Hydra Collection",
    "Operation Riptide Collection",
    "Overpass 2024 Collection",
    "Overpass Collection",
    "Phoenix Collection",
    "Prisma 2 Collection",
    "Prisma Collection",
    "Radiant Collection",
    "Recoil Collection",
    "Revolution Collection",
    "Revolver Case Collection",
    "Rising Sun Collection",
    "Safehouse Collection",
    "Shadow Collection",
    "Shattered Web Collection",
    "Snakebite Collection",
    "Spectrum 2 Collection",
    "Spectrum Collection",
    "Sport & Field Collection",
    "St. Marc Collection",
    "Train 2025 Collection",
    "Train Collection",
    "Vanguard Collection",
    "Vertigo Collection",
    "Wildfire Collection",
    "Winter Offensive Collection",
    "X-Ray Collection",
    "eSports 2013 Collection",
    "eSports 2013 Winter Collection",
    "eSports 2014 Summer Collection",
]


def load_collections():
    """Загружает список коллекций из файла."""
    if not os.path.exists(COLLECTIONS_FILE):
        save_collections(DEFAULT_COLLECTIONS)
        return DEFAULT_COLLECTIONS

    try:
        with open(COLLECTIONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("collections", DEFAULT_COLLECTIONS)
    except Exception as e:
        print(f"Error loading collections: {e}")
        return DEFAULT_COLLECTIONS


def save_collections(collections):
    """Сохраняет список коллекций в файл."""
    os.makedirs(CACHE_DIR, exist_ok=True)

    data = {
        "collections": sorted(collections),
        "last_updated": datetime.now(timezone.utc).isoformat()
    }
    try:
        with open(COLLECTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving collections: {e}")


def update_collections_from_schema(schema_data):
    """Обновляет список коллекций на основе данных из API схемы."""
    if not schema_data or "collections" not in schema_data:
        return False

    current_collections = set(load_collections())

    new_collections = set()
    for collection in schema_data["collections"]:
        collection_name = collection.get("name", "")
        if collection_name:
            if collection_name.startswith("The "):
                collection_name = collection_name[4:]
            new_collections.add(collection_name)

    updated_collections = current_collections | new_collections

    added = updated_collections - current_collections
    if added:
        save_collections(list(updated_collections))
        return True
    else:
        return False


def get_collections():
    """Возвращает список коллекций (для использования в UI)."""
    return load_collections()
