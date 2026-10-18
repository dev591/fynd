"""Razorpay Orders API over httpx, ported from the team's existing Razorpay test-mode project (same behaviour, no SDK).

Create an order with auto-capture, let Razorpay Checkout take the payment in the browser, then verify the HMAC signature on the
server and confirm the payment really was captured before anything is applied. Transport failures are retried with jittered
backoff and every call has a timeout. Keys come from the environment only; only the public key id ever reaches the browser.
Test mode only unless RAZORPAY_ALLOW_LIVE=true, so a live key pasted by mistake cannot take real money.
"""
import hmac
import hashlib
import os
import random
import time
from typing import Optional

import httpx

BASE = "https://api.razorpay.com/v1"
TIMEOUT_S = 30.0                 # above normal provider latency; an unbounded call would hang the request
_SLEEP = time.sleep              # replaced in tests


class PaymentError(Exception):
    """A Razorpay call failed in a way the caller can report cleanly."""


def key_id() -> str:
    return os.environ.get("RAZORPAY_KEY_ID", "").strip()


def _secret() -> str:
    return os.environ.get("RAZORPAY_KEY_SECRET", "").strip()


def mode() -> str:
    """'test', 'live' or 'off'. A live key is 'off' unless it was explicitly allowed."""
    k = key_id()
    if not (k and _secret()):
        return "off"
    if k.startswith("rzp_test_"):
        return "test"
    return "live" if os.environ.get("RAZORPAY_ALLOW_LIVE", "").lower() == "true" else "off"


def enabled() -> bool:
    return mode() != "off"


def _call(method: str, path: str, json: Optional[dict] = None, attempts: int = 3) -> dict:
    if not enabled():
        raise PaymentError("Payments are not configured on this server.")
    last: Optional[Exception] = None
    for attempt in range(1, attempts + 1):
        try:
            r = httpx.request(method, f"{BASE}{path}", auth=(key_id(), _secret()), json=json, timeout=TIMEOUT_S)
            if r.status_code >= 500:
                raise httpx.HTTPStatusError("server error", request=None, response=r)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            if e.response is None or e.response.status_code < 500:
                raise PaymentError("Razorpay refused the request.") from e        # a 4xx fails the same way again
            last = e
        except httpx.RequestError as e:
            last = e
        if attempt < attempts:
            _SLEEP(random.uniform(0, min(0.5 * (2 ** (attempt - 1)), 3.0)))
    raise PaymentError("Could not reach Razorpay. Please try again.") from last


def create_order(amount_rupees: float, receipt: str, notes: Optional[dict] = None) -> dict:
    """A real Razorpay order. Razorpay wants paise as an integer; payment_capture=1 captures on authorisation."""
    return _call("POST", "/orders", {"amount": int(round(amount_rupees * 100)), "currency": "INR", "receipt": receipt[:40],
                                      "payment_capture": 1, "notes": notes or {}})


def fetch_payment(payment_id: str) -> dict:
    return _call("GET", f"/payments/{payment_id}")


def capture_payment(payment_id: str, amount_paise: int) -> dict:
    """Idempotent: an order created with payment_capture=1 is already captured, so check first instead of capturing blindly."""
    p = fetch_payment(payment_id)
    if p.get("status") != "authorized":
        return p                                           # captured: done. Anything else: the caller refuses it
    return _call("POST", f"/payments/{payment_id}/capture", {"amount": amount_paise, "currency": "INR"})


def verify_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """The HMAC Razorpay Checkout returns on success: proof the payment happened and was not spoofed by the browser."""
    if not (order_id and payment_id and signature and enabled()):
        return False
    expected = hmac.new(_secret().encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
