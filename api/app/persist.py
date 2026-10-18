"""Write-through for the in-memory store: SQLite (WAL) on a laptop, or a Supabase table in production.

The store keeps working on plain Python objects, so the engine, views and tests are untouched. After an API call,
every collection that changed is written in one transaction; on start the saved state is loaded, or the seed data
stays if there is none. One table, one row per collection, JSON values validated back into the same models.
Turn it off with PERSIST=off. `python -m app.reset` starts from the seed again.

Supabase is used only when PERSIST_BACKEND=supabase and SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY are set (on the server),
so a laptop with keys in its .env never writes into the live table. It talks to Supabase's REST API with httpx, no new
package. If Supabase cannot be reached at start, saving stays off for that process so the saved data is never overwritten
by the seed.
"""
import os
import sqlite3
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from pydantic import TypeAdapter

from .models import (
    AutopilotSettings, BuyerNotice, ChatMessage, Event, ExceptionRecord, NegotiationTarget, Notification, Profile, QuoteVersion, RFQ,
    SupplierProduct, SupplierProfileOut,
)

# attribute on RFQStore -> its type. Anything not listed (like short-lived AI drafts) is not saved.
FIELDS: Dict[str, Any] = {
    "rfqs": Dict[str, RFQ],
    "token_to_rfq_id": Dict[str, str],
    "token_to_supplier_id": Dict[str, str],
    "token_to_supplier_name": Dict[str, str],
    "quotes": Dict[str, Dict[str, List[QuoteVersion]]],
    "targets": Dict[str, Dict[str, NegotiationTarget]],
    "profiles": Dict[str, Profile],
    "decisions": Dict[str, dict],
    "supplier_profiles": Dict[str, SupplierProfileOut],
    "supplier_products": Dict[str, List[SupplierProduct]],
    "chats": Dict[str, Dict[str, List[ChatMessage]]],
    "notifications": Dict[str, List[Notification]],
    "aliases": Dict[str, Dict[str, str]],
    "revealed": Dict[str, Dict[str, dict]],
    "media": Dict[str, dict],
    "buyer_notices": Dict[str, List[BuyerNotice]],
    "known_suppliers": Dict[str, Dict[str, str]],
    "exceptions": Dict[str, Dict[str, ExceptionRecord]],
    "reveal_log": List[dict],
    "plans": Dict[str, str],
    "history": List[dict],
    "supplier_owner": Dict[str, str],
    "autopilot": Dict[str, AutopilotSettings],
    "shares": Dict[str, str],
    "ai_log": List[dict],
    "events": Dict[str, List[Event]],
}
_ADAPTERS = {name: TypeAdapter(tp) for name, tp in FIELDS.items()}
_lock = threading.Lock()
_last: Dict[str, str] = {}      # what is already on disk, per collection, so unchanged ones are not rewritten


_offline = False                # Supabase was unreachable at start: never save, so the saved data cannot be clobbered
_RETRY_SLEEP = 1.0


class Unreachable(Exception):
    pass


def backend() -> str:
    if os.environ.get("PERSIST_BACKEND", "").lower() == "supabase" and _sb_url() and _sb_key():
        return "supabase"
    return "sqlite"


def _sb_url() -> str:
    return os.environ.get("SUPABASE_URL", "").rstrip("/")


def _sb_key() -> str:
    return os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def _sb_endpoint() -> str:
    return f"{_sb_url()}/rest/v1/{os.environ.get('CROSSOVER_STATE_TABLE', 'crossover_state')}"


def _sb_headers(prefer: Optional[str] = None) -> dict:
    h = {"apikey": _sb_key(), "Authorization": f"Bearer {_sb_key()}", "Content-Type": "application/json"}
    if prefer:
        h["Prefer"] = prefer
    return h


def _sb_read() -> Dict[str, str]:
    last: Optional[Exception] = None
    for attempt in range(3):
        try:
            r = httpx.request("GET", _sb_endpoint(), headers=_sb_headers(), params={"select": "name,value"}, timeout=15)
            r.raise_for_status()
            return {row["name"]: row["value"] for row in r.json()}
        except Exception as e:                                   # network, auth, missing table
            last = e
            if attempt < 2:
                time.sleep(_RETRY_SLEEP)
    raise Unreachable(str(last))


def _sb_write(changed: Dict[str, str]) -> None:
    rows = [{"name": n, "value": v, "saved_at": time.time()} for n, v in changed.items()]
    r = httpx.request("POST", _sb_endpoint(), headers=_sb_headers("resolution=merge-duplicates,return=minimal"),
                      params={"on_conflict": "name"}, json=rows, timeout=15)
    r.raise_for_status()


def _target(path: Optional[Path]) -> str:
    return "supabase" if backend() == "supabase" else str(path or db_path())


def enabled() -> bool:
    return os.environ.get("PERSIST", "on").lower() != "off"


def db_path() -> Path:
    return Path(os.environ.get("CROSSOVER_DB") or Path(__file__).resolve().parent.parent / "data" / "app.db")


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("CREATE TABLE IF NOT EXISTS state (name TEXT PRIMARY KEY, value TEXT NOT NULL, saved_at REAL NOT NULL)")
    return conn


def save(store, path: Optional[Path] = None) -> int:
    """Write every changed collection. Returns how many were written."""
    if _offline:
        return 0
    target = _target(path)
    path = path or db_path()
    with _lock:
        fresh = {n: _ADAPTERS[n].dump_json(getattr(store, n)).decode() for n in FIELDS}
        changed = {n: v for n, v in fresh.items() if _last.get((target, n)) != v}
        if not changed:
            return 0
        if target == "supabase":
            try:
                _sb_write(changed)
            except Exception as e:
                print(f"Crossover: could not save to Supabase ({type(e).__name__}); the next API call retries.", file=sys.stderr)
                return 0
            for n, v in changed.items():
                _last[(target, n)] = v
            return len(changed)
        conn = _connect(path)
        try:
            with conn:                                     # one transaction
                conn.executemany(
                    "INSERT INTO state(name, value, saved_at) VALUES (?, ?, ?) "
                    "ON CONFLICT(name) DO UPDATE SET value = excluded.value, saved_at = excluded.saved_at",
                    [(n, v, time.time()) for n, v in changed.items()])
        finally:
            conn.close()
        for n, v in changed.items():
            _last[(target, n)] = v
        return len(changed)


def load(store, path: Optional[Path] = None) -> bool:
    """Replace the store's state with what is saved. False if nothing usable is saved (the seed stays).
    With Supabase, an unreachable or unreadable table raises Unreachable instead, so the caller never seeds over it."""
    if backend() == "supabase":
        rows = _sb_read()
        if not rows:
            return False
        try:
            loaded = {n: _ADAPTERS[n].validate_json(rows[n]) for n in FIELDS if n in rows}
        except Exception as e:
            raise Unreachable(f"saved state could not be read: {e}")
        with _lock:
            for n, value in loaded.items():
                setattr(store, n, value)
                _last[("supabase", n)] = rows[n]
        return True
    path = path or db_path()
    if not path.exists():
        return False
    try:
        conn = _connect(path)
        try:
            rows = dict(conn.execute("SELECT name, value FROM state").fetchall())
        finally:
            conn.close()
        if not rows:
            return False
        loaded = {n: _ADAPTERS[n].validate_json(rows[n]) for n in FIELDS if n in rows}
    except Exception:
        # A file we cannot read must not take the app down. Keep it for inspection and start from the seed.
        try:
            path.rename(path.with_suffix(f".bad-{int(time.time())}"))
        except OSError:
            pass
        return False
    with _lock:
        for n, value in loaded.items():
            setattr(store, n, value)
            _last[(str(path), n)] = rows[n]
    return True


def init(store) -> str:
    """At start-up: 'loaded', 'seeded' (first run, now saved), 'off', or 'offline' (Supabase unreachable: not saving)."""
    global _offline
    _offline = False
    if not enabled():
        return "off"
    try:
        if load(store):
            return "loaded"
    except Unreachable as e:
        _offline = True
        print(f"Crossover: Supabase state could not be loaded ({e}). Running on seed data WITHOUT saving, so nothing "
              "saved is overwritten. Fix the connection and restart.", file=sys.stderr)
        return "offline"
    save(store)
    return "seeded"


def clear(path: Optional[Path] = None) -> str:
    """Remove all saved state, so the next start seeds fresh demo data. Returns what was cleared."""
    if backend() == "supabase":
        r = httpx.request("DELETE", _sb_endpoint(), headers=_sb_headers(), params={"name": "not.is.null"}, timeout=15)
        r.raise_for_status()
        _last.clear()
        return "the Supabase table"
    path = path or db_path()
    removed = []
    for suffix in ("", "-wal", "-shm"):
        p = path.parent / (path.name + suffix)
        if p.exists():
            p.unlink()
            removed.append(p.name)
    _last.clear()
    return ", ".join(removed) if removed else "nothing"
