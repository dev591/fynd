"""The Supabase backend for the write-through store: same save/load as SQLite, over Supabase's REST API."""
import json

import pytest

from app import persist
from tests.test_persist import _busy_store


class Resp:
    def __init__(self, status=200, data=None):
        self.status_code, self._d = status, data

    def json(self):
        return self._d

    def raise_for_status(self):
        if self.status_code >= 400:
            raise persist.httpx.HTTPStatusError("err", request=None, response=None)


class FakeSupabase:
    """An in-memory crossover_state table behind fake PostgREST calls."""
    def __init__(self):
        self.rows, self.calls, self.down = {}, [], False

    def request(self, method, url, headers=None, params=None, json=None, timeout=None, **_):
        self.calls.append((method, url, headers, params, json))
        if self.down:
            raise persist.httpx.ConnectError("down")
        if method == "GET":
            return Resp(200, [{"name": n, "value": v} for n, v in self.rows.items()])
        if method == "POST":
            for r in json:
                self.rows[r["name"]] = r["value"]
            return Resp(201)
        if method == "DELETE":
            self.rows.clear()
            return Resp(204)
        return Resp(405)


@pytest.fixture
def sb(monkeypatch):
    fake = FakeSupabase()
    monkeypatch.setenv("PERSIST", "on")
    monkeypatch.setenv("PERSIST_BACKEND", "supabase")
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-secret")
    monkeypatch.setattr(persist.httpx, "request", fake.request)
    monkeypatch.setattr(persist, "_RETRY_SLEEP", 0)
    persist._last.clear()
    persist._offline = False
    persist._status.update(last_error=None, last_ok=None, saves=0)
    yield fake
    persist._offline = False


def test_backend_is_sqlite_unless_supabase_is_asked_for_explicitly(monkeypatch):
    monkeypatch.delenv("PERSIST_BACKEND", raising=False)
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "k")
    assert persist.backend() == "sqlite"                 # a laptop with keys in .env never writes into the live table
    monkeypatch.setenv("PERSIST_BACKEND", "supabase")
    assert persist.backend() == "supabase"
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY")
    assert persist.backend() == "sqlite"                 # asked for, but without the key it cannot work


def test_everything_survives_a_restart_through_supabase(sb):
    s, rfq = _busy_store()
    assert persist.save(s) > 0
    post = [c for c in sb.calls if c[0] == "POST"][-1]
    assert post[1] == "https://proj.supabase.co/rest/v1/crossover_state"
    assert post[2]["apikey"] == "service-secret" and post[2]["Authorization"] == "Bearer service-secret"
    assert "merge-duplicates" in post[2]["Prefer"] and post[3] == {"on_conflict": "name"}

    from app.rfq_store import RFQStore
    fresh = RFQStore()
    persist._last.clear()
    assert persist.load(fresh) is True
    assert fresh.rfqs[rfq.id].decision["winner_id"] == "Seller 1"
    assert [q.freight for q in fresh.quotes[rfq.id]["A"]] == [200, 150]
    assert fresh.plans["buyer-1"] == "pro" and fresh.profiles["buyer-1"].company == "FanWorks"


def test_only_changed_collections_are_sent(sb):
    s, _ = _busy_store()
    persist.save(s)
    before = len(sb.calls)
    assert persist.save(s) == 0 and len(sb.calls) == before          # nothing changed, no network call
    s.plans["buyer-1"] = "free"
    assert persist.save(s) == 1
    assert [r["name"] for r in sb.calls[-1][4]] == ["plans"]


def test_empty_table_means_first_run_and_the_seed_is_saved(sb):
    from app.rfq_store import RFQStore
    assert persist.init(RFQStore()) == "seeded"
    assert "rfqs" in sb.rows and "supplier_products" in sb.rows


def test_supabase_unreachable_at_start_never_overwrites_saved_data(sb):
    s, rfq = _busy_store()
    persist.save(s)
    saved = dict(sb.rows)
    sb.down = True
    from app.rfq_store import RFQStore
    fresh = RFQStore()
    persist._last.clear()
    assert persist.init(fresh) == "offline"
    sb.down = False
    fresh.plans["someone"] = "pro"
    assert persist.save(fresh) == 0                                   # saving stays off for this process
    assert sb.rows == saved


def test_a_failed_save_is_reported_and_retried_on_the_next_call(sb, capsys):
    s, _ = _busy_store()
    sb.down = True
    assert persist.save(s) == 0
    assert "could not save" in capsys.readouterr().err.lower()
    sb.down = False
    assert persist.save(s) > 0                                        # nothing was marked saved, so it all goes now


def test_reset_clears_the_supabase_table(sb):
    s, _ = _busy_store()
    persist.save(s)
    persist.clear()
    assert sb.rows == {} and any(c[0] == "DELETE" for c in sb.calls)


def test_a_failed_save_records_why_in_words_without_any_key(sb):
    class Bad(Resp):
        def __init__(self):
            super().__init__(401, {"message": "Invalid API key"})
            self.text = '{"message":"Invalid API key"}'

        def raise_for_status(self):
            raise persist.httpx.HTTPStatusError("err", request=None, response=self)

    s, _ = _busy_store()
    sb.request = lambda *a, **k: Bad()
    persist.httpx.request = sb.request
    persist.save(s)
    st = persist.status()
    assert "401" in st["last_error"] and "Invalid API key" in st["last_error"] and "service-secret" not in st["last_error"]
    assert st["saves"] == 0 and st["last_ok"] is None


def test_a_good_save_is_counted_and_clears_the_error(sb):
    s, _ = _busy_store()
    persist._status.update(last_error="old problem")
    assert persist.save(s) > 0
    st = persist.status()
    assert st["last_error"] is None and st["saves"] >= 1 and st["last_ok"]


def test_an_unreachable_start_records_the_reason(sb):
    sb.down = True
    from app.rfq_store import RFQStore
    assert persist.init(RFQStore()) == "offline"
    assert persist.status()["last_error"]


def test_a_server_that_started_before_the_table_existed_starts_saving_once_it_does(sb, monkeypatch):
    from app.rfq_store import RFQStore
    persist._RETRY_EVERY_S = 0
    sb.down = True                                              # the table was missing / unreachable at start
    s = RFQStore()
    assert persist.init(s) == "offline"
    s.plans["someone"] = "pro"                                  # work done while offline
    assert persist.save(s) == 0 and sb.rows == {}
    sb.down = False                                             # the table now exists and is empty
    assert persist.retry_if_offline(s) is True
    assert "plans" in sb.rows and persist.save(s) == 0          # everything was written, nothing left over
    s.plans["later"] = "pro"
    assert persist.save(s) == 1


def test_it_does_not_overwrite_saved_data_from_an_earlier_run_when_it_comes_back(sb):
    from app.rfq_store import RFQStore
    persist._RETRY_EVERY_S = 0
    old, _ = _busy_store()
    persist.save(old)
    saved = dict(sb.rows)
    persist._offline = True
    fresh = RFQStore()
    assert persist.retry_if_offline(fresh) is False             # the table holds earlier data: leave it alone
    assert persist.save(fresh) == 0 and sb.rows == saved
    assert "restart" in persist.status()["last_error"].lower()


def test_retries_are_rate_limited(sb):
    from app.rfq_store import RFQStore
    persist._RETRY_EVERY_S = 3600
    persist._offline = True
    persist._last_retry = 0.0
    sb.down = True
    persist.retry_if_offline(RFQStore())
    n = len(sb.calls)
    persist.retry_if_offline(RFQStore())
    assert len(sb.calls) == n
    persist._RETRY_EVERY_S = 30
