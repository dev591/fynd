import json
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from app import ai, intake
from app.intake import build_draft, numbers_in_text, resolve_need_days
from app.main import app, store
from app.matching import verdict_for
from app.models import RFQ, SupplierProduct

client = TestClient(app)
GOLD = json.loads((Path(__file__).parent / "golden" / "intake_cases.json").read_text())
TODAY = date.fromisoformat(GOLD["today"])
SELLER = json.loads((Path(__file__).parent / "golden" / "seller_cases.json").read_text())["cases"]


def _check(case, draft_out):
    d, e = draft_out["draft"], case["expect"]
    assert d["item"] == e["item"], case["tag"]
    assert d["qty"] == e["qty"], case["tag"]
    assert d["need_in_days"] == e["need_in_days"], case["tag"]
    assert d["priority_mode"] == e["priority_mode"], case["tag"]
    assert any("One item per request" in w for w in draft_out["warnings"]) == e["has_other_items_warning"], case["tag"]


def test_golden_buyer_sentences_with_faithful_model_output():
    assert len(GOLD["cases"]) == 15
    names = store.catalog_names()
    for c in GOLD["cases"]:
        _check(c, build_draft(c["text"], c["raw"], names, TODAY))


def test_zero_invented_values_when_model_makes_things_up():
    """Poison every model output with values the buyer never said. None may survive."""
    names = store.catalog_names()
    invented = 0
    for c in GOLD["cases"]:
        raw = dict(c["raw"])
        raw.update(item="gold bars", quantity=7919, need_in_days=31, need_by_phrase="by diwali", note="rush job")
        d = build_draft(c["text"], raw, names, TODAY)["draft"]
        invented += (d["item"] == "gold bars") + (d["qty"] == 7919) + (d["need_in_days"] == 31) + (d["note"] == "rush job")
    assert invented == 0


def test_missing_fields_are_reported_not_guessed():
    out = build_draft("I want 100 M10 bolts", GOLD["cases"][6]["raw"], store.catalog_names(), TODAY)
    assert out["missing"] == ["need_in_days"]
    none = build_draft("hello how are you", GOLD["cases"][13]["raw"], store.catalog_names(), TODAY)
    assert set(none["missing"]) == {"item", "qty", "need_in_days"}


def test_numbers_in_text_and_deadline_resolution():
    assert {100, 1000, 2000, 50, 12} <= numbers_in_text("100 and 1,000 and 2 hazaar and fifty and a dozen")
    assert 7919 not in numbers_in_text("I need 100 bolts")
    assert resolve_need_days("Friday", TODAY) == 6          # 2026-10-17 is a Saturday
    assert resolve_need_days("tomorrow", TODAY) == 1
    assert resolve_need_days("kal", TODAY) == 1
    assert resolve_need_days("next week", TODAY) == 7
    assert resolve_need_days("2026-10-20", TODAY) == 3
    assert resolve_need_days("sometime soon", TODAY) is None


def test_golden_seller_verdicts():
    assert len(SELLER) == 8
    for c in SELLER:
        rfq = RFQ(id="r", token="t", item="x", qty=c["qty"], need_in_days=c["need"], buyer_company="c",
                  buyer_name="b", buyer_city="p", buyer_state="m", created_at="now")
        p = SupplierProduct(id="p", name="x", pack_price=1, pack_size=1, stock=c["stock"],
                            usual_lead_days=c["lead"], moq=c["moq"])
        assert verdict_for(rfq, p).can_fulfil == c["expect"], c["tag"]


def test_draft_endpoint_without_key_falls_back_to_manual(monkeypatch):
    for k in ("OPENAI_API_KEY", "MODEL_INTAKE"):
        monkeypatch.delenv(k, raising=False)
    res = client.post("/api/intake/draft", json={"text": "I need 100 M10 bolts in 5 days"})
    assert res.status_code == 200
    body = res.json()
    assert body["fallback"] is True and body["draft"]["qty"] is None
    assert set(body["missing"]) == {"item", "qty", "need_in_days"}
    # nothing was saved by drafting
    assert not any(r.item == "M10 bolts" for r in store.rfqs.values())


def test_draft_endpoint_with_model_then_confirm_creates_request(monkeypatch):
    c = GOLD["cases"][0]
    monkeypatch.setattr(intake, "structured_call", lambda *a, **k: c["raw"])
    before = len(store.rfqs)
    draft = client.post("/api/intake/draft", json={"text": c["text"]}).json()
    assert draft["fallback"] is False and draft["draft"]["item"] == "M10 bolt"
    assert len(store.rfqs) == before                      # draft endpoints never create requests
    d = draft["draft"]
    created = client.post("/api/rfqs/confirm", json={
        "item": d["item"], "qty": d["qty"], "need_in_days": d["need_in_days"], "priority_mode": "balanced",
        "source": "voice", "buyer_company": "Co", "buyer_name": "Buyer", "intake_id": draft["request_id"],
    }).json()
    assert created["rfq"]["source"] == "voice" and created["rfq"]["priority_mode"] == "balanced"
    assert created["matched"] >= 3                        # snapped to the catalog spelling, so sellers match
    log = client.get(f"/api/rfqs/{created['id']}/ai-log").json()
    assert log and log[0]["kind"] == "intake_draft" and log[0]["input"]["text"] == c["text"]


def test_confirm_rejects_invalid_fields():
    bad = {"item": "M10 bolt", "qty": 0, "need_in_days": 5, "buyer_company": "c", "buyer_name": "b"}
    assert client.post("/api/rfqs/confirm", json=bad).status_code == 422
    assert client.post("/api/rfqs/confirm", json={**bad, "qty": 5, "need_in_days": 0}).status_code == 422


def test_refusal_and_bad_payloads_return_none():
    refusal = {"output": [{"content": [{"type": "refusal", "refusal": "no"}]}]}
    assert ai.parse_structured(refusal) is None
    ok = {"output": [{"content": [{"type": "output_text", "text": "{\"item\": \"x\"}"}]}]}
    assert ai.parse_structured(ok) == {"item": "x"}
    assert ai.parse_structured({"output": [{"content": [{"type": "output_text", "text": "not json"}]}]}) is None


def test_transcribe_without_key_falls_back():
    res = client.post("/api/intake/transcribe", content=b"\x00\x01", headers={"content-type": "audio/webm"})
    assert res.status_code == 200 and res.json()["fallback"] is True


def test_openai_request_shape_and_env_model(monkeypatch):
    seen = {}

    class FakeResp:
        def raise_for_status(self): pass
        def json(self):
            return {"output": [{"content": [{"type": "output_text", "text": "{\"item\": \"M10 bolt\"}"}]}]}

    def fake_post(url, json=None, timeout=None, headers=None, **kw):
        seen.update(url=url, body=json, timeout=timeout, headers=headers)
        return FakeResp()

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("MODEL_INTAKE", "model-from-env")
    monkeypatch.setattr(ai.httpx, "post", fake_post)
    out = ai.structured_call("sys", "usr", "purchase_request", intake.SCHEMA)
    assert out == {"item": "M10 bolt"}
    assert seen["url"].endswith("/responses") and seen["body"]["model"] == "model-from-env"
    fmt = seen["body"]["text"]["format"]
    assert fmt["type"] == "json_schema" and fmt["strict"] is True
    assert seen["headers"]["Authorization"] == "Bearer sk-test"
    assert seen["timeout"] <= 8.0
    # strict mode needs every property required and no extras
    assert set(intake.SCHEMA["required"]) == set(intake.SCHEMA["properties"])
    assert intake.SCHEMA["additionalProperties"] is False


def test_timeout_or_error_returns_none_not_exception(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("MODEL_INTAKE", "m")
    def boom(*a, **k): raise ai.httpx.TimeoutException("slow")
    monkeypatch.setattr(ai.httpx, "post", boom)
    assert ai.structured_call("s", "u", "n", intake.SCHEMA) is None


def test_elevenlabs_transcription_request_shape(monkeypatch):
    seen = {}

    class FakeResp:
        def raise_for_status(self): pass
        def json(self): return {"text": " 100 M10 bolt chahiye ", "language_code": "hin"}

    def fake_post(url, timeout=None, headers=None, data=None, files=None, **kw):
        seen.update(url=url, headers=headers, data=data, files=files)
        return FakeResp()

    monkeypatch.setenv("ELEVENLABS_API_KEY", "xi-test")
    monkeypatch.setenv("ELEVENLABS_STT_MODEL", "scribe_v2")
    monkeypatch.setattr(ai.httpx, "post", fake_post)
    assert ai.transcribe(b"\x00\x01", "audio/webm;codecs=opus") == "100 M10 bolt chahiye"
    assert seen["url"] == "https://api.elevenlabs.io/v1/speech-to-text"
    assert seen["headers"] == {"xi-api-key": "xi-test"}
    assert seen["data"] == {"model_id": "scribe_v2"}
    assert seen["files"]["file"][2] == "audio/webm;codecs=opus"


def test_voice_needs_both_keys(monkeypatch):
    for k in ("OPENAI_API_KEY", "MODEL_INTAKE", "ELEVENLABS_API_KEY", "ELEVENLABS_STT_MODEL"):
        monkeypatch.delenv(k, raising=False)
    assert ai.voice_enabled() is False
    monkeypatch.setenv("ELEVENLABS_API_KEY", "x"); monkeypatch.setenv("ELEVENLABS_STT_MODEL", "scribe_v2")
    assert ai.voice_enabled() is False                     # transcript could not be read without the text model
    monkeypatch.setenv("OPENAI_API_KEY", "y"); monkeypatch.setenv("MODEL_INTAKE", "m")
    assert ai.voice_enabled() is True


def test_env_file_loader(tmp_path, monkeypatch):
    from app.env import load_env
    f = tmp_path / ".env"
    f.write_text('# comment\nOPENAI_API_KEY=\nMODEL_INTAKE="from-file"\nELEVENLABS_STT_MODEL=scribe_v2\nKEEP=file\n')
    for k in ("OPENAI_API_KEY", "MODEL_INTAKE", "ELEVENLABS_STT_MODEL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("KEEP", "shell")
    load_env(f)
    import os
    assert "OPENAI_API_KEY" not in os.environ                # blank placeholder is ignored
    assert os.environ["MODEL_INTAKE"] == "from-file"         # quotes stripped
    assert os.environ["KEEP"] == "shell"                     # real environment wins
    for k in ("MODEL_INTAKE", "ELEVENLABS_STT_MODEL"):
        monkeypatch.delenv(k, raising=False)


def test_item_snap_ignores_word_order_and_plurals():
    names = store.catalog_names()
    assert intake.snap_item("copper wire 1.5mm", names) == ("1.5mm copper wire", True)
    assert intake.snap_item("M10 bolts", names)[1] is True
    assert intake.snap_item("titanium widgets", names) == ("titanium widgets", False)


def test_quantity_phrase_is_read_in_code_when_model_leaves_quantity_empty():
    names = store.catalog_names()
    raw = {**GOLD["cases"][0]["raw"], "quantity": None, "quantity_phrase": "2 hazaar"}
    assert build_draft("Looking for 2 hazaar M10 bolts in 5 days", raw, names, TODAY)["draft"]["qty"] == 2000
    raw = {**raw, "quantity_phrase": "a dozen"}
    assert build_draft("need a dozen M10 bolts in 5 days", raw, names, TODAY)["draft"]["qty"] == 12
    # vague or unsupported phrases never become a number
    raw = {**raw, "quantity_phrase": "a lot"}
    assert build_draft("need a lot of M10 bolts in 5 days", raw, names, TODAY)["draft"]["qty"] is None
    raw = {**raw, "quantity_phrase": "5000 pieces"}
    assert build_draft("need M10 bolts in 5 days", raw, names, TODAY)["draft"]["qty"] is None


def test_brief_endpoint_names_and_env_names_work_alongside_the_old_ones(monkeypatch):
    from app import ai
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setenv("MODEL_INTAKE", "old-name")
    assert ai.intake_model() == "old-name"
    monkeypatch.setenv("MODEL_FAST", "new-name")
    assert ai.intake_model() == "new-name"
    for path in ("/api/ai/request-draft", "/api/intake/draft"):
        r = client.post(path, json={"text": "I need 100 M10 bolts in 5 days"})
        assert r.status_code == 200 and "draft" in r.json()
    for path in ("/api/ai/transcribe", "/api/intake/transcribe"):
        assert client.post(path, content=b"\x00\x01", headers={"content-type": "audio/webm"}).status_code == 200


def test_env_loader_ignores_inline_comments_so_a_copied_example_file_stays_blank(tmp_path, monkeypatch):
    import os
    from app.env import load_env
    f = tmp_path / ".env"
    f.write_text('BLANK=            # https://<project>.supabase.co\n'
                 'ONLY_COMMENT=# nothing here\n'
                 'KEEP=real-value   # and a note\n'
                 'QUOTED="two words"  # note\n'
                 'HASH_INSIDE=pa#ss\n'
                 'SPACED = padded \n')
    for k in ("BLANK", "ONLY_COMMENT", "KEEP", "QUOTED", "HASH_INSIDE", "SPACED"):
        monkeypatch.delenv(k, raising=False)
    load_env(f)
    assert "BLANK" not in os.environ and "ONLY_COMMENT" not in os.environ          # a comment is never a value
    assert os.environ["KEEP"] == "real-value" and os.environ["QUOTED"] == "two words"
    assert os.environ["HASH_INSIDE"] == "pa#ss" and os.environ["SPACED"] == "padded"
    for k in ("KEEP", "QUOTED", "HASH_INSIDE", "SPACED"):
        monkeypatch.delenv(k, raising=False)


def test_the_shipped_example_env_loads_as_all_blank_or_safe_defaults(monkeypatch):
    import os
    from pathlib import Path
    from app.env import load_env
    keys = [l.split("=")[0].strip() for l in (Path(__file__).parent.parent / ".env.example").read_text().splitlines()
            if "=" in l and not l.strip().startswith("#")]
    for k in keys:
        monkeypatch.delenv(k, raising=False)
    load_env(Path(__file__).parent.parent / ".env.example")
    secrets_and_urls = {"SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_JWT_SECRET", "OPENAI_API_KEY", "MODEL_FAST",
                        "ELEVENLABS_API_KEY", "DEMO_WINDOW_MINUTES", "CROSSOVER_DB", "CORS_ORIGINS"}
    assert not [k for k in secrets_and_urls if os.environ.get(k)], "an unfilled example must not set secrets or URLs"
    assert os.environ["FREE_REVEALS"] == "3" and os.environ["PERSIST"] == "on"
    for k in keys:
        monkeypatch.delenv(k, raising=False)
