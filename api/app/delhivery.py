"""Thin Delhivery LTL client over httpx: pincode service, freight estimate, delivery time (TAT).

The token stays on the server (DELHIVERY_TOKEN). Every function returns None on any failure (no token, timeout,
non-2xx, bad JSON) so the seller types freight and lead time by hand, as before. What comes back is only ever a
suggestion the seller can edit: the raw reply is kept so nothing is guessed about its shape.
"""
import os
import re
from typing import Any, Optional

import httpx

TIMEOUT_S = 6.0
_PIN = re.compile(r"^[1-9][0-9]{5}$")


def _base() -> str:
    return os.environ.get("DELHIVERY_BASE_URL", "https://ltl-clients-api-dev.delhivery.com").rstrip("/")


def _token() -> str:
    return os.environ.get("DELHIVERY_TOKEN", "")


def enabled() -> bool:
    return bool(_token())


def valid_pin(pin: str) -> bool:
    return bool(_PIN.match((pin or "").strip()))


def _headers() -> dict:
    return {"Authorization": f"Bearer {_token()}", "Content-Type": "application/json"}


def _call(method: str, path: str, **kw) -> Optional[Any]:
    if not enabled():
        return None
    try:
        r = httpx.request(method, _base() + path, headers=_headers(), timeout=TIMEOUT_S, **kw)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def pincode_service(pin: str, weight_kg: float = 1) -> Optional[Any]:
    """Can Delhivery serve this pincode at this weight?"""
    if not valid_pin(pin):
        return None
    return _call("GET", f"/pincode-service/{pin.strip()}", params={"weight": weight_kg})


def freight_estimate(source_pin: str, consignee_pin: str, weight_g: int, *, length_cm: float = 10, width_cm: float = 10,
                     height_cm: float = 10, box_count: int = 1, inv_amount: float = 0, payment_mode: str = "prepaid",
                     freight_mode: str = "fod", rov_insurance: bool = True) -> Optional[Any]:
    if not (valid_pin(source_pin) and valid_pin(consignee_pin)) or weight_g <= 0:
        return None
    body = {
        "dimensions": [{"length_cm": length_cm, "width_cm": width_cm, "height_cm": height_cm, "box_count": box_count}],
        "weight_g": int(weight_g), "cheque_payment": False, "source_pin": source_pin.strip(),
        "consignee_pin": consignee_pin.strip(), "payment_mode": payment_mode, "inv_amount": inv_amount,
        "freight_mode": freight_mode, "rov_insurance": rov_insurance,
    }
    return _call("POST", "/freight/estimate", json=body)


def tat_estimate(origin_pin: str, destination_pin: str) -> Optional[Any]:
    if not (valid_pin(origin_pin) and valid_pin(destination_pin)):
        return None
    return _call("GET", "/tat/estimate", params={"origin_pin": origin_pin.strip(), "destination_pin": destination_pin.strip()})


def find_number(data: Any, *names: str) -> Optional[float]:
    """First numeric value under any of these keys, searched through nested dicts and lists. None if absent.

    The vendor reply shape is not guaranteed, so a suggestion is only offered when a clearly named number exists.
    """
    wanted = {n.lower() for n in names}
    stack = [data]
    while stack:
        cur = stack.pop(0)
        if isinstance(cur, dict):
            for k, v in cur.items():
                if str(k).lower() in wanted and isinstance(v, (int, float)) and not isinstance(v, bool):
                    return float(v)
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return None
