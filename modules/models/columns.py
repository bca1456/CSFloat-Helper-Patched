# modules/models/columns.py

COL_NAME = 0
COL_STICKERS = 1
COL_KEYCHAINS = 2
COL_FLOAT = 3
COL_SEED = 4
COL_DAYS = 5
COL_PRICE = 6
COL_LISTING_ID = 7
COL_ASSET_ID = 8
COL_CREATED_AT = 9
COL_PRICE_VALUE = 10
COL_API_KEY = 11
COL_COLLECTION = 12
COL_RARITY = 13
COL_WEAR = 14
COL_DEF_INDEX = 15
COL_PAINT_INDEX = 16
COL_INSPECT_LINK = 17
COL_ICON_URL = 18
COL_STICKER_INDEX = 19

COLUMN_COUNT = 20

HIDDEN_COLUMNS = [
    COL_LISTING_ID, COL_ASSET_ID, COL_CREATED_AT,
    COL_PRICE_VALUE, COL_API_KEY, COL_COLLECTION,
    COL_RARITY, COL_WEAR, COL_DEF_INDEX, COL_PAINT_INDEX,
    COL_INSPECT_LINK, COL_ICON_URL, COL_STICKER_INDEX,
]

DEFAULT_COLUMN_WIDTHS = {
    0: 320, 1: 140, 2: 27, 3: 124, 4: 37, 5: 60, 6: 83,
    7: 0, 8: 0, 9: 0, 10: 0, 11: 0, 12: 0, 13: 0, 14: 0,
    15: 0, 16: 0, 17: 0, 18: 0, 19: 0,
}

COLUMN_HEADERS = [
    "Name", "Stickers", "Keychains", "Float Value", "Seed", "On sale",
    "Price", "Listing ID", "Asset ID", "Created At", "Price Value",
    "API Key", "Collection", "Rarity", "Wear Condition",
    "Def Index", "Paint Index", "Inspect Link", "Icon URL", "Sticker Index",
]
