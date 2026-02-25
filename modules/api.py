# modules/api.py

import json
import urllib.request
import urllib.error
import time

# API endpoints
API_USER_INFO = "https://csfloat.com/api/v1/me"
API_INVENTORY = "https://csfloat.com/api/v1/me/inventory"
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
    """Helper to read JSON response."""
    with urllib.request.urlopen(req) as response:
        raw = response.read()
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))


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


def get_inventory_data(api_key: str):
    """Get inventory data with automatic retry on errors."""
    def _get():
        headers = {"Authorization": api_key}
        req = urllib.request.Request(API_INVENTORY, headers=headers)
        data = _request_json(req)
        if isinstance(data, dict) and "items" in data:
            return data["items"]
        if isinstance(data, list):
            return data
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
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as response:
            raw = response.read()
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as http_err:
        if http_err.code == 400:
            error_data = json.load(http_err)
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
        data=json.dumps(payload).encode("utf-8"),
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
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req) as response:
            raw = response.read()
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as http_err:
        if http_err.code == 400:
            error_data = json.load(http_err)
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