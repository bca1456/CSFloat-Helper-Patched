# modules/api.py

import gzip
import logging
import os
import urllib.request
import urllib.error
import urllib.parse
import time

try:
    import orjson as _json_mod

    def _loads(data):
        return _json_mod.loads(data)

    def _dumps(obj):
        return _json_mod.dumps(obj)
except ImportError:
    import json as _json_mod

    def _loads(data):
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return _json_mod.loads(data)

    def _dumps(obj):
        return _json_mod.dumps(obj).encode("utf-8")

# API endpoints
API_USER_INFO = "https://csfloat.com/api/v1/me"
API_INVENTORY = "https://csfloat.com/api/v1/me/inventory"
API_STALL = "https://csfloat.com/api/v1/users/{steam_id}/stall?limit=999"
LISTINGS_URL = "https://csfloat.com/api/v1/listings"
BULK_LIST_URL = "https://csfloat.com/api/v1/listings/bulk-list"
BULK_DELIST_URL = "https://csfloat.com/api/v1/listings/bulk-delist"
BULK_MODIFY_URL = "https://csfloat.com/api/v1/listings/bulk-modify"
API_SCHEMA = "https://csfloat.com/api/v1/schema"
API_HISTORY_SALES = "https://csfloat.com/api/v1/history/{market_hash_name}/sales"
API_HISTORY_GRAPH = "https://csfloat.com/api/v1/history/{market_hash_name}/graph"
API_BUY_ORDERS_ITEM = "https://csfloat.com/api/v1/buy-orders/item"
API_BUY_ORDERS_SIMILAR = "https://csfloat.com/api/v1/buy-orders/similar-orders"

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY = 1.0  # секунды


def _request_json(req: urllib.request.Request):
    """Helper to read JSON response with gzip support."""
    req.add_header("Accept-Encoding", "gzip")
    with urllib.request.urlopen(req) as response:
        raw = response.read()
        if not raw:
            return {}
        if response.headers.get("Content-Encoding") == "gzip" or raw[:2] == b'\x1f\x8b':
            raw = gzip.decompress(raw)
        return _loads(raw)


def _retry_request(func, *args, max_retries=MAX_RETRIES, retry_delay=RETRY_DELAY, **kwargs):
    """
    Retry wrapper for API requests.
    Automatically retries on HTTP 400/500 errors and network issues.
    """
    last_error = None

    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except urllib.error.HTTPError as e:
            last_error = e
            if e.code == 400 or 500 <= e.code < 600:
                if attempt < max_retries - 1:
                    print(f"HTTP {e.code} error, retrying ({attempt + 1}/{max_retries})...")
                    time.sleep(retry_delay * (attempt + 1))
                    continue
            raise
        except urllib.error.URLError as e:
            last_error = e
            if attempt < max_retries - 1:
                print(f"Network error, retrying ({attempt + 1}/{max_retries})...")
                time.sleep(retry_delay * (attempt + 1))
                continue
            raise

    if last_error:
        raise last_error


def get_user_info(api_key: str):
    """Get user info with automatic retry on errors."""
    def _get():
        headers = {"Authorization": api_key}
        req = urllib.request.Request(API_USER_INFO, headers=headers)
        data = _request_json(req)
        return data.get("user", {})

    try:
        return _retry_request(_get)
    except urllib.error.HTTPError as e:
        print(f"HTTP error occurred: {e}")
        return None
    except urllib.error.URLError as e:
        print(f"Other error occurred: {e}")
        return None


_INVENTORY_FIELDS = {
    "asset_id", "market_hash_name", "rarity", "float_value",
    "paint_seed", "wear_name", "collection", "stickers", "keychains",
    "def_index", "paint_index", "sticker_index", "inspect_link", "icon_url",
    "keychain_index", "keychain_pattern",
}


def _strip_inventory(items):
    """Оставляет только нужные поля для экономии памяти."""
    return [{k: v for k, v in item.items() if k in _INVENTORY_FIELDS} for item in items]


def get_inventory_data(api_key: str):
    """Get inventory data with automatic retry on errors."""
    def _get():
        headers = {"Authorization": api_key}
        req = urllib.request.Request(API_INVENTORY, headers=headers)
        data = _request_json(req)
        if isinstance(data, dict) and "items" in data:
            return _strip_inventory(data["items"])
        if isinstance(data, list):
            return _strip_inventory(data)
        print("Unexpected response format.")
        return []

    try:
        return _retry_request(_get)
    except urllib.error.HTTPError as e:
        print(f"HTTP error occurred: {e}")
        return None
    except urllib.error.URLError as e:
        print(f"Other error occurred: {e}")
        return None


def get_stall_data(api_key: str, steam_id: str):
    """Get stall data with automatic retry on errors."""
    def _get():
        headers = {"Authorization": api_key}
        url = API_STALL.format(steam_id=steam_id)
        req = urllib.request.Request(url, headers=headers)
        data = _request_json(req)
        return data.get("data", [])

    try:
        return _retry_request(_get)
    except urllib.error.HTTPError as e:
        print(f"HTTP error occurred: {e}")
        return None
    except urllib.error.URLError as e:
        print(f"Other error occurred: {e}")
        return None


def bulk_list(api_key: str, items: list):
    """Bulk list items on CSFloat."""
    url = BULK_LIST_URL
    payload = {"items": items}
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(
        url,
        data=_dumps(payload),
        headers=headers,
        method="POST",
    )
    try:
        return _request_json(req)
    except urllib.error.HTTPError as http_err:
        if http_err.code == 400:
            error_data = _loads(http_err.read())
            if error_data.get("code") == 4:
                raise ValueError("Item overpriced. You need to complete KYC.") from http_err
        raise ValueError(f"HTTP error occurred: {http_err}") from http_err
    except urllib.error.URLError as err:
        raise ValueError(f"An unexpected error occurred: {err}") from err


def bulk_delist(api_key: str, contract_ids: list):
    """Bulk delist items from CSFloat."""
    url = BULK_DELIST_URL
    payload = {"contract_ids": contract_ids}
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(
        url,
        data=_dumps(payload),
        headers=headers,
        method="PATCH",
    )
    try:
        return _request_json(req)
    except urllib.error.HTTPError as e:
        print(f"HTTP error occurred: {e}")
        return None
    except urllib.error.URLError as e:
        print(f"Other error occurred: {e}")
        return None


def bulk_modify(api_key: str, modifications: list):
    """Bulk modify prices of listed items."""
    url = BULK_MODIFY_URL
    payload = {"modifications": modifications}
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(
        url,
        data=_dumps(payload),
        headers=headers,
        method="PATCH",
    )
    try:
        return _request_json(req)
    except urllib.error.HTTPError as http_err:
        if http_err.code == 400:
            error_data = _loads(http_err.read())
            if error_data.get("code") == 4:
                raise ValueError("Item overpriced. You need to complete KYC.") from http_err
        raise ValueError(f"HTTP error occurred: {http_err}") from http_err
    except urllib.error.URLError as err:
        raise ValueError(f"An unexpected error occurred: {err}") from err


def get_schema():
    """Получает схему (коллекции) с CSFloat API."""
    try:
        req = urllib.request.Request(API_SCHEMA)
        data = _request_json(req)
        return data
    except urllib.error.HTTPError as e:
        print(f"HTTP error occurred: {e}")
        return None
    except urllib.error.URLError as e:
        print(f"Other error occurred: {e}")
        return None


# ═══════════════════════════════════════════════════════════
# Item Info API — listings, sales, buy orders, graph
# ═══════════════════════════════════════════════════════════


def get_item_listings(api_key, def_index, paint_index=None, sticker_index=None,
                      category=1, min_float=None, max_float=None, limit=50,
                      keychain_index=None, cursor=None, paint_seed=None,
                      min_fade=None, max_fade=None, min_blue=None, max_blue=None,
                      min_keychain_pattern=None, max_keychain_pattern=None,
                      sort_by=None, collection=None, rarity=None):
    """Получает текущие листинги предмета."""
    def _get():
        params = {"type": "buy_now"}

        if collection:
            params["collection"] = collection
            params["rarity"] = rarity
            params["category"] = category
            params["sort_by"] = sort_by or "lowest_price"
            params["limit"] = limit
            if min_float is not None:
                params["min_float"] = min_float
            if max_float is not None:
                params["max_float"] = max_float
            if paint_seed is not None:
                params["paint_seed"] = paint_seed
            if min_fade is not None:
                params["min_fade"] = min_fade
            if max_fade is not None:
                params["max_fade"] = max_fade
            if min_blue is not None:
                params["min_blue"] = min_blue
            if max_blue is not None:
                params["max_blue"] = max_blue
        elif keychain_index:
            params["keychain_index"] = keychain_index
            params["sort_by"] = sort_by or "lowest_price"
            params["limit"] = limit
            if min_keychain_pattern is not None:
                params["min_keychain_pattern"] = min_keychain_pattern
            if max_keychain_pattern is not None:
                params["max_keychain_pattern"] = max_keychain_pattern
        elif paint_index:
            params["def_index"] = def_index
            params["paint_index"] = paint_index
            params["category"] = category
            params["limit"] = limit
            if sort_by:
                params["sort_by"] = sort_by
            if min_float is not None:
                params["min_float"] = min_float
            if max_float is not None:
                params["max_float"] = max_float
            if paint_seed is not None:
                params["paint_seed"] = paint_seed
            if min_fade is not None:
                params["min_fade"] = min_fade
            if max_fade is not None:
                params["max_fade"] = max_fade
            if min_blue is not None:
                params["min_blue"] = min_blue
            if max_blue is not None:
                params["max_blue"] = max_blue
        elif sticker_index:
            params["def_index"] = def_index
            params["sticker_index"] = sticker_index
            params["sort_by"] = sort_by or "lowest_price"
            params["limit"] = min(limit, 40)
        else:
            params["def_index"] = def_index
            params["sort_by"] = sort_by or "lowest_price"
            params["limit"] = min(limit, 40)

        if cursor:
            params["cursor"] = cursor

        url = f"{LISTINGS_URL}?{urllib.parse.urlencode(params)}"
        headers = {"Authorization": api_key}
        req = urllib.request.Request(url, headers=headers)
        data = _request_json(req)
        return data

    try:
        return _retry_request(_get)
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        logging.error(f"get_item_listings error: {e}")
        return None


def get_item_sales(api_key, market_hash_name):
    """Получает историю продаж предмета."""
    def _get():
        encoded = urllib.parse.quote(market_hash_name, safe="")
        url = API_HISTORY_SALES.format(market_hash_name=encoded)
        headers = {"Authorization": api_key}
        req = urllib.request.Request(url, headers=headers)
        data = _request_json(req)
        return data

    try:
        return _retry_request(_get)
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        logging.error(f"get_item_sales error: {e}")
        return None


def get_item_buy_orders(api_key, inspect_link=None, market_hash_name=None, limit=5):
    """Получает buy orders для предмета."""
    def _get():
        headers = {"Authorization": api_key}

        if inspect_link:
            params = {"url": inspect_link, "limit": limit}
            url = f"{API_BUY_ORDERS_ITEM}?{urllib.parse.urlencode(params)}"
            req = urllib.request.Request(url, headers=headers)
        else:
            # POST для предметов без inspect_link
            headers["Content-Type"] = "application/json"
            payload = {"market_hash_name": market_hash_name}
            url = f"{API_BUY_ORDERS_SIMILAR}?limit={limit}"
            req = urllib.request.Request(
                url, data=_dumps(payload), headers=headers, method="POST",
            )

        data = _request_json(req)
        return data

    try:
        return _retry_request(_get)
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        logging.error(f"get_item_buy_orders error: {e}")
        return None


def get_item_graph(api_key, market_hash_name):
    """Получает график цен предмета."""
    def _get():
        encoded = urllib.parse.quote(market_hash_name, safe="")
        url = API_HISTORY_GRAPH.format(market_hash_name=encoded)
        headers = {"Authorization": api_key}
        req = urllib.request.Request(url, headers=headers)
        data = _request_json(req)
        return data

    try:
        return _retry_request(_get)
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        logging.error(f"get_item_graph error: {e}")
        return None