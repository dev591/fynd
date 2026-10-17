"""Create the ten demo seller accounts in Supabase and fill their profile and catalog through the API.

Run from the api folder with the API running:  python3 scripts/seed_demo_sellers.py
Reads api/.env: SUPABASE_URL, SUPABASE_ANON_KEY, DEMO_SELLER_PASSWORD (you choose it), and optionally
SUPABASE_SERVICE_ROLE_KEY (lets accounts be created already confirmed). Safe to run again: existing accounts and
catalog items are left alone. Passwords and keys are never printed.
"""
import os
import sys

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.env import load_env  # noqa: E402

load_env()
from app.demo_roster import ROSTER, email_of, profile_payload  # noqa: E402

URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
ANON = os.environ.get("SUPABASE_ANON_KEY", "")
SERVICE = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
PASSWORD = os.environ.get("DEMO_SELLER_PASSWORD", "")
API = os.environ.get("API_URL", "http://localhost:8000").rstrip("/")


def ensure_user(email: str) -> None:
    if SERVICE:
        r = httpx.post(f"{URL}/auth/v1/admin/users", timeout=20, headers={"apikey": SERVICE, "Authorization": f"Bearer {SERVICE}"},
                       json={"email": email, "password": PASSWORD, "email_confirm": True})
        if r.status_code not in (200, 201, 422):
            raise SystemExit(f"  could not create {email}: {r.status_code} {r.text[:200]}")
    else:
        r = httpx.post(f"{URL}/auth/v1/signup", timeout=20, headers={"apikey": ANON}, json={"email": email, "password": PASSWORD})
        if r.status_code not in (200, 201, 400, 422):
            raise SystemExit(f"  could not sign up {email}: {r.status_code} {r.text[:200]}")


def token_for(email: str) -> str:
    r = httpx.post(f"{URL}/auth/v1/token?grant_type=password", timeout=20, headers={"apikey": ANON},
                   json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise SystemExit(f"  cannot sign in {email}: {r.status_code} {r.text[:200]}\n"
                         "  If this says the email is not confirmed, turn off 'Confirm email' in Supabase "
                         "(Authentication > Providers > Email) or set SUPABASE_SERVICE_ROLE_KEY, then run again.")
    return r.json()["access_token"]


def main() -> None:
    if not (URL and ANON and PASSWORD):
        raise SystemExit("Set SUPABASE_URL, SUPABASE_ANON_KEY and DEMO_SELLER_PASSWORD in api/.env first.")
    if len(PASSWORD) < 8:
        raise SystemExit("DEMO_SELLER_PASSWORD needs at least 8 characters.")
    for s in ROSTER:
        email = email_of(s)
        print(f"{s['n']}  {s['company']} ({s['city']})")
        ensure_user(email)
        h = {"Authorization": f"Bearer {token_for(email)}"}
        with httpx.Client(base_url=API, headers=h, timeout=20) as c:
            r = c.post("/api/profile", json=profile_payload(s))
            r.raise_for_status()
            c.post("/api/me/roles", json={"role": "seller"}).raise_for_status()
            sid = c.get("/api/me").json().get("supplier_id")
            have = {p["name"] for p in c.get(f"/api/supplier/products/{sid}").json()}
            added = 0
            for p in s["products"]:
                if p["name"] not in have:
                    c.post(f"/api/supplier/products/{sid}", json=p).raise_for_status()
                    added += 1
            print(f"    profile saved, {added} catalog item(s) added")
    print("\nDone. Set DEMO_LOGINS=on in api/.env and restart the API to show the one-click panel on /signin.")


if __name__ == "__main__":
    main()
