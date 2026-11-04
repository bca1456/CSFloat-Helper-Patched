# modules/models/columns.py

COL_NAME = 0
COL_CSFLOAT_LOGIN = 1
COL_STICKERS = 2
COL_KEYCHAINS = 3
COL_FLOAT = 4
COL_SEED = 5
COL_DAYS = 6
COL_PRICE = 7
COL_LISTING_ID = 8
COL_ASSET_ID = 9
COL_CREATED_AT = 10
COL_PRICE_VALUE = 11
COL_API_KEY = 12
COL_COLLECTION = 13
COL_RARITY = 14
COL_WEAR = 15
COL_DEF_INDEX = 16
COL_PAINT_INDEX = 17
COL_INSPECT_LINK = 18
COL_ICON_URL = 19
COL_STICKER_INDEX = 20
COL_KEYCHAIN_INDEX = 21
COL_BOUGHT = 22

COLUMN_COUNT = 23

# Увеличивайте при изменении DEFAULT_COLUMN_WIDTHS, чтобы сбросить сохранённые в QSettings ширины.
COLUMN_LAYOUT_VERSION = 2

HIDDEN_COLUMNS = [
    COL_LISTING_ID, COL_ASSET_ID, COL_CREATED_AT,
    COL_PRICE_VALUE, COL_API_KEY, COL_COLLECTION,
    COL_RARITY, COL_WEAR, COL_DEF_INDEX, COL_PAINT_INDEX,
    COL_INSPECT_LINK, COL_ICON_URL, COL_STICKER_INDEX,
    COL_KEYCHAIN_INDEX,
]

DEFAULT_COLUMN_WIDTHS = {
    0: 290, 1: 70, 2: 180, 3: 27, 4: 155, 5: 35, 6: 58, 7: 80,
    8: 0, 9: 0, 10: 0, 11: 0, 12: 0, 13: 0, 14: 0, 15: 0,
    16: 0, 17: 0, 18: 0, 19: 0, 20: 0, 21: 0, 22: 110,
}

COLUMN_HEADERS = [
    "Name", "Login", "Stickers", "Keychains", "Float Value", "Seed", "On sale",
    "Price", "Listing ID", "Asset ID", "Created At", "Price Value",
    "API Key", "Collection", "Rarity", "Wear Condition",
    "Def Index", "Paint Index", "Inspect Link", "Icon URL", "Sticker Index",
    "Keychain Index", "Bought on CSFloat",
]
