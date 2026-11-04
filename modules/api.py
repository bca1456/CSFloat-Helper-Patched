# modules/api.py

import gzip
import hashlib
import logging
import os
import threading
import urllib.request
import urllib.error
import urllib.parse
import time
from datetime import datetime, timedelta, timezone

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
API_TRADES = "https://csfloat.com/api/v1/me/trades"
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

# Purchase history cache
_PURCHASES_CACHE_VERSION = 2
_PURCHASES_CACHE_TTL = 30 * 60  # 30 минут
_PURCHASES_INCREMENTAL_OVERLAP = 14 * 24 * 60 * 60  # 14 дней
_PURCHASES_MAX_PAGES = 5
_PURCHASES_PAGE_LIMIT = 1000
_PURCHASES_CACHE_LOCK = threading.Lock()

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PURCHASES_CACHE_FILE = os.path.join(_BASE_DIR, "cache", "purchases_cache.json")


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


def _purchases_cache_key(api_key: str) -> str:
    """Короткий идентификатор аккаунта для кэша покупок."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]


def _parse_iso_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _load_purchases_cache():
    try:
        with open(_PURCHASES_CACHE_FILE, "rb") as f:
            data = _loads(f.read())
        if (
            isinstance(data, dict)
            and data.get("version") == _PURCHASES_CACHE_VERSION
            and isinstance(data.get("accounts"), dict)
        ):
            return data
    except FileNotFoundError:
        pass
    except Exception as e:
        logging.warning("Failed to load purchases cache: %s", e)
    return {"version": _PURCHASES_CACHE_VERSION, "accounts": {}}


def _save_purchases_cache(cache):
    tmp = f"{_PURCHASES_CACHE_FILE}.{os.getpid()}.tmp"
    try:
        os.makedirs(os.path.dirname(_PURCHASES_CACHE_FILE), exist_ok=True)
        with open(tmp, "wb") as f:
            f.write(_dumps(cache))
        os.replace(tmp, _PURCHASES_CACHE_FILE)
    except Exception as e:
        logging.warning("Failed to save purchases cache: %s", e)
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass


def _norm_value(value):
    return "" if value is None else str(value)


def purchase_item_key(item):
    """Стабильный ключ предмета для сопоставления покупок с инвентарём.

    Steam asset_id меняется после трейда, поэтому используем характеристики предмета.
    """
    name = _norm_value(item.get("market_hash_name"))
    float_value = item.get("float_value")
    if float_value is not None:
        try:
            float_value = round(float(float_value), 12)
        except (TypeError, ValueError):
            float_value = None

    if float_value is not None:
        return "|".join([
            "float",
            name,
            f"{float_value:.12f}",
            _norm_value(item.get("paint_seed")),
            _norm_value(item.get("paint_index")),
            _norm_value(item.get("def_index")),
        ])

    return "|".join([
        "name",
        name,
        _norm_value(item.get("keychain_pattern")),
        _norm_value(item.get("sticker_index")),
    ])


def _merge_purchases(base, new):
    """Объединяет покупки, оставляя более свежую запись для одинаковых предметов."""
    result = dict(base or {})
    for key, info in (new or {}).items():
        old = result.get(key)
        if old is None or str(info.get("purchased_at") or "") >= str(old.get("purchased_at") or ""):
            result[key] = info
    return result


def _fetch_purchases(api_key, cutoff=None, max_pages=_PURCHASES_MAX_PAGES,
                     limit=_PURCHASES_PAGE_LIMIT):
    """Загружает покупки, останавливаясь при выходе за cutoff (инкрементально)."""
    headers = {"Authorization": api_key}
    purchases = {}
    total = None
    collected = 0
    effective_limit = limit

    for page in range(max_pages):
        params = {
            "role": "buyer",
            "state": "verified",
            "limit": limit,
            "page": page,
        }
        url = f"{API_TRADES}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers=headers)
        data = _request_json(req)
        trades = data.get("trades") or []
        if not trades:
            break

        if total is None:
            total = data.get("count")

        if page == 0 and len(trades) < effective_limit:
            # Сервер может ограничивать размер страницы меньше запрошенного.
            effective_limit = len(trades)

        oldest = None
        for trade in trades:
            created = _parse_iso_datetime(
                trade.get("created_at") or trade.get("verified_at")
            )
            if created is not None and (oldest is None or created < oldest):
                oldest = created

            contract = trade.get("contract") or {}
            item = contract.get("item") or {}
            if not item.get("market_hash_name"):
                continue

            info = {
                "price": int(contract.get("price") or 0),
                "purchased_at": (
                    trade.get("verified_at")
                    or trade.get("accepted_at")
                    or contract.get("sold_at")
                    or trade.get("created_at")
                    or ""
                ),
                "market_hash_name": item.get("market_hash_name", ""),
                "float_value": item.get("float_value"),
                "paint_seed": item.get("paint_seed"),
                "paint_index": item.get("paint_index"),
                "def_index": item.get("def_index"),
                "keychain_pattern": item.get("keychain_pattern"),
                "sticker_index": item.get("sticker_index"),
            }
            purchases = _merge_purchases(purchases, {purchase_item_key(info): info})

        collected += len(trades)
        if cutoff is not None and oldest is not None and oldest < cutoff:
            break
        if total is not None and collected >= int(total):
            break
        if len(trades) < effective_limit:
            break

    return purchases


def get_purchased_assets(api_key: str, force_refresh: bool = False):
    """Возвращает {item_key: {price, purchased_at}} с кэшированием и инкрементальной догрузкой."""
    cache_key = _purchases_cache_key(api_key)
    now = time.time()

    with _PURCHASES_CACHE_LOCK:
        cache = _load_purchases_cache()
        entry = cache.get("accounts", {}).get(cache_key) or {}
        cached = dict(entry.get("purchases") or {})
        last_sync = float(entry.get("last_sync") or 0)

    if not force_refresh and last_sync and (now - last_sync) < _PURCHASES_CACHE_TTL:
        return cached

    cutoff = None
    if last_sync:
        cutoff = datetime.fromtimestamp(last_sync, tz=timezone.utc) - timedelta(
            seconds=_PURCHASES_INCREMENTAL_OVERLAP
        )

    try:
        fetched = _retry_request(_fetch_purchases, api_key, cutoff) or {}
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        logging.error("get_purchased_assets error: %s", e)
        return cached

    merged = _merge_purchases(cached, fetched)

    with _PURCHASES_CACHE_LOCK:
        cache = _load_purchases_cache()
        accounts = cache.setdefault("accounts", {})
        entry = accounts.get(cache_key) or {}
        purchases = _merge_purchases(entry.get("purchases") or {}, merged)
        accounts[cache_key] = {
            "last_sync": now,
            "purchases": purchases,
        }
        _save_purchases_cache(cache)

    return merged


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