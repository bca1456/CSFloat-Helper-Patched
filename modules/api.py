# modules/api.py

import gzip
import urllib.request
import urllib.error
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
API_INVENTORY = "https://csfloat.com/api/v1/me/inventory?limit=100"
API_STALL = "https://csfloat.com/api/v1/users/{steam_id}/stall?limit=999"
LISTINGS_URL = "https://csfloat.com/api/v1/listings"
BULK_LIST_URL = "https://csfloat.com/api/v1/listings/bulk-list"
BULK_DELIST_URL = "https://csfloat.com/api/v1/listings/bulk-delist"
BULK_MODIFY_URL = "https://csfloat.com/api/v1/listings/bulk-modify"
API_SCHEMA = "https://csfloat.com/api/v1/schema"

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
}


def _strip_inventory(items):
    """Оставляет только нужные поля для экономии памяти."""
    return [{k: v for k, v in item.items() if k in _INVENTORY_FIELDS} for item in items]


def get_inventory_data(api_key: str):
    """Get inventory data with automatic retry on errors."""
    def _get():
        headers = {"Authorization": api_key}
        all_items = []
        seen_asset_ids = set()
        limit = 100

        def _append_unique(items):
            added = 0
            for item in (items or []):
                aid = str(item.get("asset_id", ""))
                if aid and aid in seen_asset_ids:
                    continue
                if aid:
                    seen_asset_ids.add(aid)
                all_items.append(item)
                added += 1
            return added

        # 1) Base request
        req = urllib.request.Request(API_INVENTORY, headers=headers)
        data = _request_json(req)
        if isinstance(data, dict):
            page_items = data.get("items") or data.get("data") or []
            next_cursor = data.get("cursor") or data.get("next_cursor")
        elif isinstance(data, list):
            page_items = data
            next_cursor = None
        else:
            print("Unexpected response format.")
            return []

        _append_unique(page_items)

        # 2) Cursor pagination
        cursor_guard = set()
        while next_cursor and next_cursor not in cursor_guard:
            cursor_guard.add(next_cursor)
            url = f"{API_INVENTORY}&cursor={next_cursor}"
            req = urllib.request.Request(url, headers=headers)
            page = _request_json(req)
            if isinstance(page, dict):
                page_items = page.get("items") or page.get("data") or []
                next_cursor = page.get("cursor") or page.get("next_cursor")
            elif isinstance(page, list):
                page_items = page
                next_cursor = None
            else:
                break
            if not page_items:
                break
            _append_unique(page_items)

        # 3) Fallback pagination by offset/page (some backends do not return cursor)
        #    Stop when page is empty or nothing new is added.
        for i in range(1, 31):
            offset_url = f"{API_INVENTORY}&offset={i * limit}&limit={limit}"
            req = urllib.request.Request(offset_url, headers=headers)
            page = _request_json(req)
            if isinstance(page, dict):
                page_items = page.get("items") or page.get("data") or []
            elif isinstance(page, list):
                page_items = page
            else:
                page_items = []
            if not page_items:
                break
            added = _append_unique(page_items)
            if added == 0:
                break

        for p in range(2, 31):
            page_url = f"{API_INVENTORY}&page={p}&limit={limit}"
            req = urllib.request.Request(page_url, headers=headers)
            page = _request_json(req)
            if isinstance(page, dict):
                page_items = page.get("items") or page.get("data") or []
            elif isinstance(page, list):
                page_items = page
            else:
                page_items = []
            if not page_items:
                break
            added = _append_unique(page_items)
            if added == 0:
                break

        return _strip_inventory(all_items)

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