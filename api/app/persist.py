"""SQLite (WAL) write-through for the in-memory store.

The store keeps working on plain Python objects, so the engine, views and tests are untouched. After an API call,
every collection that changed is written in one transaction; on start the saved state is loaded, or the seed data
stays if there is none. One table, one row per collection, JSON values validated back into the same models.
Turn it off with PERSIST=off. Delete the file (python -m app.reset) to start from the seed again.
"""
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import TypeAdapter

from .models import (
    AutopilotSettings, ChatMessage, ExceptionRecord, NegotiationTarget, Notification, Profile, QuoteVersion, RFQ,
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
    "known_suppliers": Dict[str, Dict[str, str]],
    "exceptions": Dict[str, Dict[str, ExceptionRecord]],
    "reveal_log": List[dict],
    "plans": Dict[str, str],
    "history": List[dict],
    "supplier_owner": Dict[str, str],
    "autopilot": Dict[str, AutopilotSettings],
    "shares": Dict[str, str],
    "ai_log": List[dict],
}
_ADAPTERS = {name: TypeAdapter(tp) for name, tp in FIELDS.items()}
_lock = threading.Lock()
_last: Dict[str, str] = {}      # what is already on disk, per collection, so unchanged ones are not rewritten


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
    path = path or db_path()
    with _lock:
        fresh = {n: _ADAPTERS[n].dump_json(getattr(store, n)).decode() for n in FIELDS}
        changed = {n: v for n, v in fresh.items() if _last.get((str(path), n)) != v}
        if not changed:
            return 0
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
            _last[(str(path), n)] = v
        return len(changed)


def load(store, path: Optional[Path] = None) -> bool:
    """Replace the store's state with what is saved. False if nothing usable is saved (the seed stays)."""
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
    """At start-up: 'loaded' from disk, 'seeded' (first run, now saved), or 'off'."""
    if not enabled():
        return "off"
    if load(store):
        return "loaded"
    save(store)
    return "seeded"
