import asyncio, json, os, uuid
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from .env import load_env

load_env()  # reads api/.env before anything reads os.environ
from typing import List, Literal, Optional
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .core import Ctx, Pipeline
from .trace import bus
from .layers.exact_cache import ExactCache
from .layers.rules import Rules
from .layers.semantic_cache import SemanticCache
from .layers.llm import LLMCascade

from .models import (
    RFQEditIn,
    Profile,
    Quote,
    Need,
    ExceptionRecord,
    CompareResult,
    RFQ,
    RFQCreate,
    QuoteSubmitIn,
    QuoteVersion,
    NegotiationTargetIn,
    NegotiationTarget,
    DecisionIn,
    SupplierProfileIn,
    SupplierProfileOut,
    SupplierProductIn,
    SupplierProduct,
    ChatMessageIn,
    ChatMessage,
    NotificationOut,
    DraftQuote,
    Activity,
    IntakeIn,
    ConfirmIn,
    AutopilotSettings,
    RoleIn,
    ExceptionIn,
    DeclineIn,
    ImportIn,
    DeliveryIn,
    QuoteTextIn,
)
from .validators import cross_check_tax, mask_pan
from .intake import draft_from_text
from .quote_text import draft_from_message
from . import ai, ask_desk, fine_print, razorpay_client as rz, assistant, delhivery, demo_roster
from .summary import build_summary, savings_total
from .engine import evaluate, run_case_checks, negotiation
from .rfq_store import store
from . import persist
from starlette.concurrency import run_in_threadpool
from .auth import AuthUser, get_current_user, optional_user
from . import views
from . import importer
from fastapi.responses import JSONResponse


def require_role(role: str):
    """Dependency factory. The server decides from the account's stored roles; the browser's toggle is cosmetic."""
    def dependency(user: AuthUser = Depends(get_current_user)) -> AuthUser:
        if role not in store.roles_for(user.id):
            raise HTTPException(status_code=403, detail={"code": "role_required", "role": role,
                                                         "message": f"This needs the {role} role on your account."})
        return user
    return dependency


buyer_only = require_role("buyer")
seller_only = require_role("seller")


def _rfq_for(user: AuthUser, rfq_id: str) -> RFQ:
    """The request, only if this user owns it. 404 otherwise, never 403."""
    rfq = store.get_rfq(rfq_id)
    if not rfq or rfq.owner_id != user.id:
        raise HTTPException(status_code=404, detail="RFQ not found.")
    return rfq


def _buyer_location(user: AuthUser, city: str, state: str) -> tuple[str, str]:
    """City and state default to the buyer's saved profile, and to nothing at all if there is none."""
    prof = store.profiles.get(user.id)
    return (city or (prof.city if prof else ""), state or (prof.state if prof else ""))


def _gst_policy(user: AuthUser, chosen: Optional[bool]) -> bool:
    """An explicit choice on the request wins; otherwise the buyer's saved policy; otherwise claimable."""
    if chosen is not None:
        return chosen
    prof = store.profiles.get(user.id)
    return prof.buyer.gst_claimable if prof and prof.buyer else True


def _demo_sellers_allowed() -> bool:
    """Off unless ALLOW_DEMO_SELLERS=true: then any seller account may also act as the synthetic demo sellers (a single-
    laptop demo). Off, every account sees only its own seller."""
    return os.environ.get("ALLOW_DEMO_SELLERS", "false").lower() == "true"


def _seller_for(user: AuthUser, supplier_id: str) -> str:
    """A seller id this user may act as: their own, or a synthetic demo seller while demo sellers are allowed."""
    owner = store.supplier_owner.get(supplier_id)
    if owner == user.id:
        return supplier_id
    if owner is None and supplier_id in store.supplier_profiles and _demo_sellers_allowed():
        return supplier_id
    raise HTTPException(status_code=404, detail="Seller not found.")

# Pipeline configuration
REGISTRY = {"exact": ExactCache, "rules": Rules, "semantic": SemanticCache, "llm": LLMCascade}


def build() -> Pipeline:
    order = os.getenv("PIPELINE", "exact,rules,semantic,llm").split(",")
    return Pipeline([REGISTRY[n.strip()]() for n in order])


pipeline = build()

PERSIST_STATE = persist.init(store)     # 'loaded' | 'seeded' | 'off'

async def _window_clock():
    """Every 30 seconds: close windows, remind sellers, tell buyers. store.tick() reads the store's clock, so
    tests drive it directly instead of waiting."""
    while True:
        await asyncio.sleep(30)
        try:
            await run_in_threadpool(store.tick)
            if persist.enabled():
                await run_in_threadpool(persist.save, store)
        except Exception:
            pass                           # a failed tick must never stop the clock


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(_window_clock())
    yield
    task.cancel()


app = FastAPI(title="Crossover Decision Engine & RFQ API", version="2.0.0", lifespan=lifespan)

# Browsers may call this API from the dev server, and from a phone on the same private network. Anywhere
# else must be added on purpose with CORS_ORIGINS=https://one.example,https://two.example
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()],
    allow_origin_regex=r"^http://(192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+):\d+$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def save_state_after_api_calls(request: Request, call_next):
    """Write-through: after any API call, save whatever changed. Cheap when nothing did."""
    response = await call_next(request)
    if persist.enabled() and request.url.path.startswith("/api"):
        try:
            await run_in_threadpool(persist.save, store)
        except Exception:
            pass          # a failed save must never fail the request; the next call retries
    return response


# --- 1. Pipeline & Trace Endpoints ---
class RunIn(BaseModel):
    query: str
    tenant: str = "default"
    meta: dict = {}


@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "crossover-api",
        "layers": [l.name for l in pipeline.layers],
    }


@app.post("/run")
async def run(body: RunIn, user: AuthUser = Depends(get_current_user)):
    ctx = Ctx(body.query, body.tenant, body.meta)
    r = await pipeline.run(ctx)
    return {"request_id": ctx.request_id, **r.__dict__}


@app.get("/stats")
def stats(user: AuthUser = Depends(get_current_user)):
    return pipeline.summary()


@app.get("/trace/stream")
async def trace_stream(user: AuthUser = Depends(get_current_user)):
    q = bus.subscribe()

    async def gen():
        try:
            for ev in list(bus.history)[-50:]:
                yield f"data: {json.dumps(ev.dict())}\n\n"
            while True:
                try:
                    ev = await asyncio.wait_for(q.get(), 15)
                    yield f"data: {json.dumps(ev.dict())}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            bus.unsubscribe(q)

    return StreamingResponse(gen(), media_type="text/event-stream")


# --- 2. Profile & Tax Validation Endpoints ---
class TaxValidationIn(BaseModel):
    gstin: str
    pan: str
    state: str


@app.post("/api/validate/tax")
def validate_tax(body: TaxValidationIn):
    return cross_check_tax(body.gstin, body.pan, body.state)


@app.post("/api/profile", response_model=Profile)
def save_profile(profile: Profile, user: AuthUser = Depends(get_current_user)):
    """Saves the signed-in user's own profile. The id and email come from the verified login, not the request."""
    profile.id = user.id
    if user.email:
        profile.email = user.email
    if profile.pan_masked is None and profile.gstin:
        profile.pan_masked = mask_pan(profile.gstin[2:12])    # never keep a raw PAN
    store.register_profile(user.id, profile)
    return store.profiles[user.id]


@app.get("/api/me")
def me(user: AuthUser = Depends(get_current_user)):
    return {
        "user": user,
        "profile": store.profiles.get(user.id),
        "roles": store.roles_for(user.id),
        "supplier_id": store.supplier_id_for_user(user.id),
    }


@app.post("/api/me/roles")
def add_my_role(payload: RoleIn, user: AuthUser = Depends(get_current_user)):
    """Add the buyer or seller role to this account. Needs a saved profile (a seller record is built from it)."""
    roles = store.add_role(user.id, payload.role)
    if roles is None:
        raise HTTPException(status_code=409, detail="Finish your profile first, then add a role.")
    return {"roles": roles, "supplier_id": store.supplier_id_for_user(user.id)}


# --- Buyer intake (draft only: nothing here saves a request) ---
_intake_cache: dict[str, dict] = {}


@app.get("/api/intake/status")
def intake_status():
    return {"ai_enabled": ai.ai_enabled(), "voice_enabled": ai.voice_enabled()}


@app.post("/api/ai/request-draft")
@app.post("/api/intake/draft")
def intake_draft(payload: IntakeIn, user: AuthUser = Depends(buyer_only)):
    key = payload.text.strip().lower()
    if key in _intake_cache:
        result = dict(_intake_cache[key])
    else:
        result = draft_from_text(payload.text, store.catalog_names())
        if not result["fallback"]:
            _intake_cache[key] = dict(result)  # cap calls: the same sentence is never sent twice
    result["request_id"] = "intk_" + os.urandom(4).hex()
    store.log_ai("intake_draft", result["request_id"], {"text": payload.text}, result)
    return result


@app.post("/api/ai/transcribe")
@app.post("/api/intake/transcribe")
async def intake_transcribe(request: Request, user: AuthUser = Depends(buyer_only)):
    """Raw audio bytes in the body (no multipart dependency). Returns the transcript, or fallback=true."""
    audio = await request.body()
    text = ai.transcribe(audio, request.headers.get("content-type", "audio/webm"))
    rid = "intk_" + os.urandom(4).hex()
    store.log_ai("transcribe", rid, {"bytes": len(audio)}, {"text": text})
    return {"text": text, "fallback": text is None, "request_id": rid}


# --- 3. Crossover Math Engine & Case Checks ---
class CompareIn(BaseModel):
    quotes: List[Quote]
    need: Need
    exceptions: Optional[dict[str, ExceptionRecord]] = None
    mode: str = "cheapest"


@app.post("/api/compare", response_model=CompareResult)
def compare_quotes(payload: CompareIn):
    return evaluate(payload.quotes, payload.need, payload.exceptions, payload.mode)


@app.get("/api/case-checks")
def get_case_checks():
    checks = run_case_checks()
    score = sum(c["points"] for c in checks if c["pass"])
    return {
        "score": score,
        "total_possible": 25,
        "all_passed": score == 25,
        "checks": checks,
    }


# --- 4. RFQ Lifecycle (Buyer Side) ---
@app.post("/api/rfqs")
def create_rfq(payload: RFQCreate, user: AuthUser = Depends(buyer_only)):
    payload.buyer_city, payload.buyer_state = _buyer_location(user, payload.buyer_city, payload.buyer_state)
    payload.gst_claimable = _gst_policy(user, payload.gst_claimable)
    return _rfq_response(store.create_rfq(payload, owner_id=user.id))


@app.post("/api/rfqs/confirm")
def confirm_rfq(payload: ConfirmIn, user: AuthUser = Depends(buyer_only)):
    """Creates the request from the confirm card. The only way an intake draft becomes a request."""
    city, state = _buyer_location(user, payload.buyer_city, payload.buyer_state)
    rfq = store.create_rfq(RFQCreate(
        item=payload.item.strip(), qty=payload.qty, need_in_days=payload.need_in_days,
        buyer_company=payload.buyer_company, buyer_name=payload.buyer_name,
        buyer_city=city, buyer_state=state,
        note=payload.note, priority_mode=payload.priority_mode, source=payload.source,
        gst_claimable=_gst_policy(user, payload.gst_claimable), window=payload.window,
        budget=payload.budget, order_id=payload.order_id,
    ), owner_id=user.id)
    if payload.intake_id:
        store.link_ai_log(payload.intake_id, rfq.id)
    return _rfq_response(rfq)


@app.get("/api/rfqs/{rfq_id}/summary")
def rfq_summary(rfq_id: str, user: AuthUser = Depends(buyer_only)):
    _rfq_for(user, rfq_id)
    s = build_summary(store, rfq_id, audience="buyer")
    if not s:
        raise HTTPException(status_code=404, detail="RFQ not found.")
    return s


@app.post("/api/rfqs/{rfq_id}/share")
def share_rfq(rfq_id: str, user: AuthUser = Depends(buyer_only)):
    """Explicit click only. The link is read-only, unguessable, and shows every quote price."""
    rfq = _rfq_for(user, rfq_id)
    if not rfq.decision:
        raise HTTPException(status_code=409, detail="Save the decision before sharing the one-pager.")
    tok = store.create_share(rfq_id)
    return {"token": tok, "url": f"/share/{tok}"}


@app.get("/api/share/{token}")
def shared_summary(token: str):
    rid = store.shares.get(token)
    s = build_summary(store, rid, audience="public") if rid else None     # a shared link never carries identities
    if not s:
        raise HTTPException(status_code=404, detail="This link isn't valid.")
    return s


@app.get("/api/savings")
def savings(user: AuthUser = Depends(buyer_only)):
    return savings_total(store, owner_id=user.id)


@app.get("/api/rfqs/{rfq_id}/ai-log")
def rfq_ai_log(rfq_id: str, user: AuthUser = Depends(buyer_only)):
    _rfq_for(user, rfq_id)
    # The buyer's own intake only. Seller-side AI entries describe the seller and stay private.
    return [e for e in store.ai_log_for(rfq_id) if e["kind"] in ("intake_draft", "transcribe", "quote_draft")]


def _rfq_response(rfq: RFQ) -> dict:
    """What a buyer gets back on creating a request. Invite tokens stay on the server."""
    return {"id": rfq.id, "matched": len(rfq.supplier_tokens), "rfq": views.public_rfq(store, rfq)}


@app.get("/api/suppliers")
def list_suppliers(user: AuthUser = Depends(seller_only)):
    """The sellers this user may act as: their own, plus the synthetic demo sellers while those are allowed."""
    return [x for x in store.list_suppliers()
            if x["supplier_id"] == store.supplier_id_for_user(user.id)
            or (store.supplier_owner.get(x["supplier_id"]) is None and _demo_sellers_allowed())]


@app.get("/api/supplier/{supplier_id}/notifications", response_model=List[NotificationOut])
def list_notifications(supplier_id: str, user: AuthUser = Depends(seller_only)):
    _seller_for(user, supplier_id)
    return store.list_notifications(supplier_id)


@app.get("/api/supplier/{supplier_id}/autopilot", response_model=AutopilotSettings)
def get_autopilot(supplier_id: str, user: AuthUser = Depends(seller_only)):
    _seller_for(user, supplier_id)
    return store.get_autopilot(supplier_id)


@app.put("/api/supplier/{supplier_id}/autopilot", response_model=AutopilotSettings)
def put_autopilot(supplier_id: str, payload: AutopilotSettings, user: AuthUser = Depends(seller_only)):
    _seller_for(user, supplier_id)
    return store.set_autopilot(supplier_id, payload.enabled)


@app.post("/api/supplier/{supplier_id}/notifications/{notification_id}/read", response_model=NotificationOut)
def read_notification(supplier_id: str, notification_id: str, user: AuthUser = Depends(seller_only)):
    _seller_for(user, supplier_id)
    n = store.mark_notification_viewed(supplier_id, notification_id)
    if not n:
        raise HTTPException(status_code=404, detail="Notification not found.")
    return n


@app.post("/api/supplier/transcribe")
async def seller_transcribe(request: Request, user: AuthUser = Depends(seller_only)):
    """Seller-side speech-to-text. Same ElevenLabs pipeline as buyer intake. Returns text or fallback=true."""
    audio = await request.body()
    text = ai.transcribe(audio, request.headers.get("content-type", "audio/webm"))
    rid = "stxr_" + os.urandom(4).hex()
    store.log_ai("seller_transcribe", rid, {"bytes": len(audio)}, {"text": text})
    return {"text": text, "fallback": text is None, "request_id": rid}


@app.post("/api/quote-voice/draft")
def quote_voice_draft(payload: QuoteTextIn, user: AuthUser = Depends(seller_only)):
    """Parse a seller's spoken or typed quote sentence into draft quote fields.
    Every number is cross-checked against the source text; invented values are dropped, never guessed.
    Returns the same row shape as the message-import draft so the quote form can apply it directly."""
    result = draft_from_message(payload.text.strip())
    rid = "qvdr_" + os.urandom(4).hex()
    store.log_ai("quote_voice_draft", rid, {"text": payload.text}, result)
    return result


@app.get("/api/rfqs")
def list_rfqs(user: AuthUser = Depends(buyer_only)):
    """Only this buyer's requests."""
    return [views.public_rfq(store, r) for r in store.rfqs.values() if r.owner_id == user.id]


@app.get("/api/rfqs/{rfq_id}")
def get_rfq_details(rfq_id: str, user: AuthUser = Depends(buyer_only)):
    """Quotes under aliases ("Seller 1"). Identities appear only for sellers this buyer has revealed."""
    return views.buyer_details(store, _rfq_for(user, rfq_id), user.id)


def _seller_by_alias(rfq_id: str, alias: str) -> str:
    sid = store.supplier_for_alias(rfq_id, alias)
    if not sid:
        raise HTTPException(status_code=404, detail="No such seller on this request.")
    return sid


def _networked_seller(rfq_id: str, alias: str) -> str:
    """Like _seller_by_alias, but refuses suppliers the buyer imported: they have no portal to receive a message."""
    sid = _seller_by_alias(rfq_id, alias)
    if store.is_known(sid):
        raise HTTPException(status_code=409, detail="This quote was imported by you, so there is no seller portal. "
                                                    "Negotiate with them directly.")
    return sid


@app.post("/api/rfqs/{rfq_id}/targets", response_model=NegotiationTarget)
def send_target_to_supplier(rfq_id: str, payload: NegotiationTargetIn, user: AuthUser = Depends(buyer_only)):
    _rfq_for(user, rfq_id)
    sid = _networked_seller(rfq_id, payload.supplier_id)        # the buyer speaks in aliases
    try:
        target = store.send_target(
            rfq_id=rfq_id, supplier_id=sid, cut_needed=payload.cut_needed,
            target_freight=payload.target_freight, target_per_unit=payload.target_per_unit,
            concession_type=payload.concession_type, message=payload.message, sent_by=payload.sent_by,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return target.model_copy(update={"supplier_id": payload.supplier_id})


@app.post("/api/rfqs/{rfq_id}/quotes/{alias}/reveal")
def reveal_seller(rfq_id: str, alias: str, user: AuthUser = Depends(buyer_only)):
    """Unlock one seller. Idempotent. Uses a free reveal (or a paid plan); 402 when none are left."""
    _rfq_for(user, rfq_id)
    sid = _seller_by_alias(rfq_id, alias)
    if sid not in store.quotes.get(rfq_id, {}):
        raise HTTPException(status_code=404, detail="No such seller on this request.")
    kind = store.reveal(rfq_id, sid, user.id)
    if kind is None:
        return JSONResponse(status_code=402, content={
            "code": "reveals_exhausted", "message": "You have used your free reveals.",
            **views.plan_info(store, user.id)})
    return {"alias": alias, "kind": kind, "seller": views.identity_of(store, sid, rfq_id), "plan": views.plan_info(store, user.id)}


@app.post("/api/rfqs/{rfq_id}/exceptions")
def record_exception(rfq_id: str, payload: ExceptionIn, user: AuthUser = Depends(buyer_only)):
    """Break a gate on purpose (a late or short seller) with a written reason and a named approver."""
    rfq = _rfq_for(user, rfq_id)
    sid = _seller_by_alias(rfq_id, payload.alias)
    if rfq.status != "Open":
        raise HTTPException(status_code=409, detail="This request is already decided.")
    store.set_exception(rfq_id, sid, payload.reason, payload.approver)
    return {"exceptions": {a: r.model_dump() for a, r in store.exceptions_by_alias(rfq_id).items()}}


@app.delete("/api/rfqs/{rfq_id}/exceptions/{alias}")
def withdraw_exception(rfq_id: str, alias: str, user: AuthUser = Depends(buyer_only)):
    rfq = _rfq_for(user, rfq_id)
    if rfq.status != "Open":
        raise HTTPException(status_code=409, detail="This request is already decided.")
    store.clear_exception(rfq_id, _seller_by_alias(rfq_id, alias))
    return {"exceptions": {a: r.model_dump() for a, r in store.exceptions_by_alias(rfq_id).items()}}


@app.post("/api/rfqs/{rfq_id}/import-quotes")
def import_quotes(rfq_id: str, payload: ImportIn, user: AuthUser = Depends(buyer_only)):
    """Bring in quotes the buyer already has (CSV or JSON). Bad rows are reported by row number; good rows load."""
    rfq = _rfq_for(user, rfq_id)
    if rfq.status != "Open":
        raise HTTPException(status_code=409, detail="This request is already decided.")
    try:
        rows = importer.parse_csv(payload.data) if payload.format == "csv" else importer.parse_json(payload.data)
        good, errors = importer.validate_rows(rows, rfq.item)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    loaded = [store.import_quote(rfq_id, r) for r in good]
    return {"imported": len(loaded), "errors": errors, "skipped_rows": len({e["row"] for e in errors}),
            "suppliers": sorted({store.alias_for(rfq_id, q.supplier_id) for q in loaded}, key=str)}


@app.post("/api/ai/quote-draft")
def quote_draft(payload: QuoteTextIn, user: AuthUser = Depends(buyer_only)):
    """Read a pasted supplier message into quote rows. A draft only: nothing is saved until the buyer imports it."""
    if payload.rfq_id:
        _rfq_for(user, payload.rfq_id)
    result = draft_from_message(payload.text)
    result["request_id"] = "qd_" + os.urandom(4).hex()
    if result["fallback"]:
        result["message"] = "Couldn't read that automatically. Use the CSV or JSON import, or the file template."
    store.log_ai("quote_draft", result["request_id"], {"chars": len(payload.text)}, result)
    if payload.rfq_id:
        store.link_ai_log(result["request_id"], payload.rfq_id)
    return result


@app.get("/api/import-template")
def import_template():
    """A file the importer accepts as-is, so nobody guesses the columns."""
    rows = importer.parse_csv(importer.TEMPLATE_CSV)
    return {"csv": importer.TEMPLATE_CSV, "json": json.dumps({"quotes": rows}, indent=2),
            "required_columns": list(importer.REQUIRED)}


@app.post("/api/rfqs/{rfq_id}/delivery")
def record_delivery(rfq_id: str, payload: DeliveryIn, user: AuthUser = Depends(buyer_only)):
    """After the order: did it match the quote, did it arrive on time. Replaces any earlier record."""
    rfq = _rfq_for(user, rfq_id)
    if not rfq.decision:
        raise HTTPException(status_code=409, detail="Place the order before recording its delivery.")
    return {"delivery": store.record_delivery(rfq_id, payload.matches_quote, payload.on_time, payload.note, payload.media)}


@app.get("/api/rfqs/{rfq_id}/delivery/media")
def delivery_media(rfq_id: str, user: AuthUser = Depends(buyer_only)):
    _rfq_for(user, rfq_id)
    m = store.media.get(rfq_id)
    if not m:
        raise HTTPException(status_code=404, detail="No file was attached.")
    return m


@app.get("/api/me/notices")
def my_notices(user: AuthUser = Depends(buyer_only)):
    """The buyer's bell, newest first."""
    # Newest first; the position breaks ties between notices created in the same instant.
    items = [n for _, n in sorted(enumerate(store.buyer_notices.get(user.id, [])),
                                  key=lambda p: (p[1].created_at, p[0]), reverse=True)]
    return {"notices": [n.model_dump() for n in items], "unread": sum(1 for n in items if not n.read)}


@app.post("/api/me/notices/read-all")
def read_all_notices(user: AuthUser = Depends(buyer_only)):
    for n in store.buyer_notices.get(user.id, []):
        n.read = True
    return {"unread": 0}


@app.post("/api/me/notices/{notice_id}/read")
def read_notice(notice_id: str, user: AuthUser = Depends(buyer_only)):
    bell = store.buyer_notices.get(user.id, [])
    n = next((x for x in bell if x.id == notice_id), None)
    if not n:
        raise HTTPException(status_code=404, detail="Notice not found.")
    n.read = True
    return {"unread": sum(1 for x in bell if not x.read)}


@app.get("/api/me/plan")
def my_plan(user: AuthUser = Depends(buyer_only)):
    return views.plan_info(store, user.id)


@app.post("/api/dev/mock-upgrade")
def mock_upgrade(user: AuthUser = Depends(buyer_only)):
    """DEV ONLY. No payment happens; this flips the account to unlimited reveals so the paywall can be demoed."""
    store.plans[user.id] = "pro"
    return {**views.plan_info(store, user.id), "note": "Mock upgrade for the demo. No payment was taken and none is stored."}


@app.get("/api/items/{item}/last-order")
def last_order(item: str, qty: Optional[int] = None, need_in_days: int = 5, user: AuthUser = Depends(buyer_only)):
    """Last winner price for this item against what the same quantity costs today. Numbers only, no sellers named."""
    last = store.last_order(user.id, item)
    q = qty or (last["qty"] if last else 100)
    today = store.todays_best(item, q, need_in_days)
    diff = round(last["landed"] - today["landed"]) if last and today and last["qty"] == q else None
    return {"item": item, "qty": q, "last": last, "today": today, "difference": diff,
            "note": "Today's best comes from sellers' current catalog rows. History marked synthetic is demo data, not a result."}


@app.post("/api/demo/sample-request")
def sample_request(user: AuthUser = Depends(buyer_only)):
    """A personal sample request with synthetic quotes already in. Used by the empty state."""
    p = store.profiles.get(user.id)
    rfq = store.create_sample_rfq(user.id, p.company if p else "My company", p.full_name if p else "Buyer",
                                  p.city if p else "", p.state if p else "")
    return _rfq_response(rfq)


@app.get("/api/rfqs/{rfq_id}/split-options")
def split_options(rfq_id: str, user: AuthUser = Depends(buyer_only)):
    """The best two-seller split for this request, with aliases only. `plan` is null when one seller already wins alone."""
    _rfq_for(user, rfq_id)
    return {"plan": store.split_options(rfq_id)}


@app.patch("/api/rfqs/{rfq_id}")
def edit_request(rfq_id: str, payload: RFQEditIn, user: AuthUser = Depends(buyer_only)):
    """The owner changes an open request. Sellers are told to check their quotes; everything is logged."""
    rfq = _rfq_for(user, rfq_id)
    if rfq.status != "Open" or rfq.decision:
        raise HTTPException(status_code=409, detail={"code": "not_open", "message": "A decided request cannot be edited."})
    store.update_rfq(rfq_id, payload.qty, payload.need_in_days, payload.note, payload.priority_mode)
    return _rfq_response(rfq)


@app.get("/api/rfqs/{rfq_id}/log")
def request_log(rfq_id: str, user: AuthUser = Depends(buyer_only)):
    """What happened on this request, oldest first. Sellers appear by alias until revealed."""
    return {"events": views.request_log(store, _rfq_for(user, rfq_id), "buyer")}


@app.get("/api/orders")
def my_orders(user: AuthUser = Depends(buyer_only)):
    """Order history: every request this buyer decided, with the seller who receives the order."""
    return {"orders": views.buyer_orders(store, user.id)}


@app.get("/api/supplier/{supplier_id}/orders")
def orders_received(supplier_id: str, user: AuthUser = Depends(seller_only)):
    """Orders this seller won, with the buyer's contact and the amount."""
    _seller_for(user, supplier_id)
    return {"orders": views.seller_orders(store, supplier_id)}


@app.get("/api/rfqs/{rfq_id}/fine-print")
def request_fine_print(rfq_id: str, user: AuthUser = Depends(buyer_only)):
    """Terms hidden in each quote's notes, by alias. Warnings only; they never change a price or a winner."""
    return {"flags": fine_print.for_request(store, _rfq_for(user, rfq_id))}


# ─── Payments (Razorpay, test mode) ───

PRODUCTS = [
    {"id": "reveal_pack_10", "name": "Reveal pack", "amount_rupees": 499, "reveals": 10, "per_reveal": 49.9,
     "blurb": "10 reveals, about ₹50 each. A reveal unlocks one seller's name and contact so you can deal with them directly."},
    {"id": "pro_30d", "name": "Pro, 30 days", "amount_rupees": 1499, "days": 30,
     "blurb": "Unlimited reveals for 30 days. Cheaper than buying reveals one by one from the 31st."},
]


class PaymentOrderIn(BaseModel):
    product: Literal["reveal_pack_10", "pro_30d", "order_advance"]
    rfq_id: Optional[str] = None


class PaymentVerifyIn(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class PayMethodIn(BaseModel):
    method: Literal["cod"]


@app.get("/api/payments/config")
def payments_config():
    """Whether payments are on, the mode (test/live/off), the public key id and what is for sale. Never the secret."""
    on = rz.enabled()
    return {"enabled": on, "mode": rz.mode(), "key_id": rz.key_id() if on else None, "products": PRODUCTS,
            "note": "Test mode: use a Razorpay test card or UPI. No real money moves." if rz.mode() == "test" else None}


@app.post("/api/payments/order")
def create_payment_order(payload: PaymentOrderIn, user: AuthUser = Depends(buyer_only)):
    if not rz.enabled():
        raise HTTPException(status_code=503, detail="Payments are not switched on for this server.")
    rfq_id = None
    if payload.product == "order_advance":
        rfq = _rfq_for(user, payload.rfq_id or "")
        pay = (rfq.decision or {}).get("payment")
        if not rfq.decision or not pay:
            raise HTTPException(status_code=409, detail="Place the order first.")
        if pay.get("status") == "advance_paid":
            raise HTTPException(status_code=409, detail="The advance for this order is already paid.")
        if not pay.get("advance") or pay["advance"] < 1:
            raise HTTPException(status_code=409, detail="This order is too small for an advance. Pay on delivery.")
        amount, rfq_id, label = float(pay["advance"]), rfq.id, f"50% advance, {rfq.item}"
    else:
        prod = next(p for p in PRODUCTS if p["id"] == payload.product)
        amount, label = float(prod["amount_rupees"]), prod["name"]
    try:
        order = rz.create_order(amount, f"{payload.product[:12]}-{uuid.uuid4().hex[:8]}", {"buyer": user.id, "product": payload.product, "rfq": rfq_id or ""})
    except rz.PaymentError:
        raise HTTPException(status_code=502, detail="Could not reach Razorpay. Please try again.")
    store.payments[order["id"]] = {"id": order["id"], "buyer_id": user.id, "product": payload.product, "rfq_id": rfq_id,
                                   "amount_paise": order["amount"], "status": "created", "created_at": datetime.now().isoformat()}
    return {"order_id": order["id"], "amount_paise": order["amount"], "currency": "INR", "key_id": rz.key_id(),
            "name": "Crossover", "description": label}


@app.post("/api/payments/verify")
def verify_payment(payload: PaymentVerifyIn, user: AuthUser = Depends(buyer_only)):
    """Check the signature, confirm Razorpay really captured the money, then apply what was bought. Safe to repeat."""
    rec = store.payments.get(payload.razorpay_order_id)
    if not rec or rec["buyer_id"] != user.id:
        raise HTTPException(status_code=404, detail="Payment not found.")
    if rec["status"] == "paid":
        return {"status": "paid", "product": rec["product"], "plan": views.plan_info(store, user.id)}
    if not rz.verify_signature(payload.razorpay_order_id, payload.razorpay_payment_id, payload.razorpay_signature):
        raise HTTPException(status_code=400, detail={"code": "bad_signature", "message": "The payment could not be verified, so nothing was applied."})
    try:
        got = rz.capture_payment(payload.razorpay_payment_id, rec["amount_paise"])
    except rz.PaymentError:
        raise HTTPException(status_code=502, detail="Could not confirm the payment with Razorpay. Nothing was lost: try again in a moment.")
    if got.get("status") != "captured" or got.get("order_id") != rec["id"] or got.get("amount") != rec["amount_paise"]:
        raise HTTPException(status_code=402, detail={"code": "not_captured", "message": "Razorpay did not capture this payment, so nothing was applied."})
    rec.update(status="paid", payment_id=payload.razorpay_payment_id, paid_at=datetime.now().isoformat())
    if rec["product"] == "reveal_pack_10":
        store.credits[user.id] = store.credits.get(user.id, 0) + 10
    elif rec["product"] == "pro_30d":
        cur = store.pro_until.get(user.id)
        base = max(datetime.now(), datetime.fromisoformat(cur)) if cur else datetime.now()
        store.pro_until[user.id] = (base + timedelta(days=30)).isoformat()
    else:
        rfq = store.rfqs[rec["rfq_id"]]
        pay = store.set_payment(rfq.id, "split_50", "advance_paid", payment_id=payload.razorpay_payment_id,
                                razorpay_order_id=rec["id"], paid_at=rec["paid_at"])
        store._notice(rfq, "payment_received", f"Advance of ₹{pay['advance']:,.0f} received (Razorpay test mode). ₹{pay['balance']:,.0f} is due on delivery.")
    return {"status": "paid", "product": rec["product"], "plan": views.plan_info(store, user.id)}


@app.get("/api/rfqs/{rfq_id}/payment")
def order_payment(rfq_id: str, user: AuthUser = Depends(buyer_only)):
    rfq = _rfq_for(user, rfq_id)
    if not rfq.decision:
        raise HTTPException(status_code=409, detail="Place the order first.")
    return {**rfq.decision["payment"], "payment_note": rfq.decision.get("payment_note"), "item": rfq.item, "qty": rfq.qty,
            "razorpay": {"enabled": rz.enabled(), "mode": rz.mode()}}


@app.post("/api/rfqs/{rfq_id}/payment")
def choose_cash_on_delivery(rfq_id: str, payload: PayMethodIn, user: AuthUser = Depends(buyer_only)):
    rfq = _rfq_for(user, rfq_id)
    if not rfq.decision:
        raise HTTPException(status_code=409, detail="Place the order first.")
    if rfq.decision["payment"].get("status") == "advance_paid":
        raise HTTPException(status_code=409, detail="An advance is already paid for this order.")
    return store.set_payment(rfq_id, "cod", "pay_on_delivery")


@app.post("/api/rfqs/{rfq_id}/decision")
def record_decision(rfq_id: str, payload: DecisionIn, user: AuthUser = Depends(buyer_only)):
    """Order handoff. The chosen seller must have been revealed first, so the buyer can actually contact them."""
    _rfq_for(user, rfq_id)
    plan = None
    if payload.split:
        plan = store.split_options(rfq_id)
        if not plan:
            raise HTTPException(status_code=409, detail={"code": "no_split", "message": "No split order is available for this request."})
        for part in plan["parts"]:
            if not store.is_revealed(rfq_id, _seller_by_alias(rfq_id, part["quote_id"])):
                raise HTTPException(status_code=409, detail={"code": "reveal_required",
                                    "message": f"Reveal {part['quote_id']} before saving the split order."})
        payload.winner_id = plan["parts"][0]["quote_id"]
    else:
        sid = _seller_by_alias(rfq_id, payload.winner_id)
        if not store.is_revealed(rfq_id, sid):
            raise HTTPException(status_code=409, detail={"code": "reveal_required",
                                "message": "Reveal this seller before saving the order."})
    try:
        return store.save_decision(rfq_id=rfq_id, winner_id=payload.winner_id, reason=payload.reason, approver=payload.approver, split=plan)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/recommendations")
def list_recommendations(user: AuthUser = Depends(buyer_only)):
    return {rid: d for rid, d in store.decisions.items() if store.rfqs[rid].owner_id == user.id}


# --- 5. Supplier Sealed Bids (Token Routes) ---
def token_guard(token: str, user: Optional[AuthUser] = Depends(optional_user)) -> str:
    """A quote link works only for the seller it was sent to. A real seller account must be signed in as itself;
    a synthetic demo seller's link works only while demo sellers are allowed."""
    sid = store.token_to_supplier_id.get(token)
    if not sid:
        raise HTTPException(status_code=404, detail="This link isn't valid or has expired.")
    owner = store.supplier_owner.get(sid)
    if owner is not None and (user is None or user.id != owner):
        raise HTTPException(status_code=403, detail={"code": "not_your_request",
                            "message": "Sign in as the seller this request was sent to."})
    if owner is None and not _demo_sellers_allowed() and sid in store.supplier_profiles and store.supplier_profiles[sid].synthetic:
        raise HTTPException(status_code=403, detail={"code": "not_your_request", "message": "This demo seller's link is switched off."})
    return sid
@app.get("/api/rfq-by-token/{token}")
def get_rfq_by_token(token: str, _seller: str = Depends(token_guard)):
    data = views.seller_request(store, token)
    if not data:
        raise HTTPException(status_code=404, detail="This link isn't valid or has expired.")
    return data


@app.get("/api/rfq-by-token/{token}/log")
def seller_request_log(token: str, _seller: str = Depends(token_guard)):
    rfq = store.rfqs.get(store.token_to_rfq_id.get(token, ""))
    return {"events": views.request_log(store, rfq, "seller", store.token_to_supplier_id.get(token)) if rfq else []}


@app.post("/api/rfq-by-token/{token}/quotes", response_model=QuoteVersion)
def submit_supplier_quote(token: str, payload: QuoteSubmitIn, _seller: str = Depends(token_guard)):
    try:
        return store.submit_quote(
            token=token,
            supplier_name=payload.supplier_name,
            pack_price=payload.pack_price,
            pack_size=payload.pack_size,
            freight=payload.freight,
            lead_days=payload.lead_days,
            moq=payload.moq,
            notes=payload.notes,
            max_qty=payload.max_qty,
            tax_rate=payload.tax_rate, price_includes_tax=payload.price_includes_tax,
            shipping=payload.shipping, shipping_basis=payload.shipping_basis,
            price_breaks=payload.price_breaks, free_freight_above=payload.free_freight_above,
            per_unit_freight=payload.per_unit_freight,
        )   # origin is decided by the server, never taken from the client
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/rfq-by-token/{token}/draft", response_model=DraftQuote)
def get_draft_quote(token: str, _seller: str = Depends(token_guard)):
    draft = store.draft_for_token(token)
    if not draft:
        raise HTTPException(status_code=404, detail="No catalog match for this request.")
    return draft


@app.get("/api/rfq-by-token/{token}/assist")
def seller_assist(token: str, _seller: str = Depends(token_guard)):
    """Catalog draft plus wording. Numbers come from the catalog; AI text is dropped if any number is unsupported."""
    draft = store.draft_for_token(token)
    rfq = store.get_rfq(store.token_to_rfq_id.get(token, ""))
    if not draft or not rfq:
        raise HTTPException(status_code=404, detail="No catalog match for this request.")
    message = assistant.reply_for(rfq, draft)
    store.assists[token] = {"draft": draft, "source": message["source"], "text": message["text"]}
    rid = "asst_" + os.urandom(4).hex()
    store.log_ai("seller_assist", rid, {"token_supplier": store.token_to_supplier_id.get(token),
                                        "facts": assistant.facts_for(rfq, draft)}, message)
    store.link_ai_log(rid, rfq.id)
    return {"draft": draft, "message": message}


class ItemMatchIn(BaseModel):
    product_id: str


@app.post("/api/rfq-by-token/{token}/item-match")
def seller_item_match(token: str, payload: ItemMatchIn, _seller: str = Depends(token_guard)):
    rfq = store.get_rfq(store.token_to_rfq_id.get(token, ""))
    sid = store.token_to_supplier_id.get(token)
    prod = next((p for p in store.supplier_products.get(sid, []) if p.id == payload.product_id), None) if sid else None
    if not rfq or not prod:
        raise HTTPException(status_code=404, detail="Request or catalog item not found.")
    out = assistant.item_match(rfq.item, prod)
    rid = "match_" + os.urandom(4).hex()
    store.log_ai("item_match", rid, {"request": rfq.item, "catalog": prod.name}, out)
    store.link_ai_log(rid, rfq.id)
    return out


@app.post("/api/rfq-by-token/{token}/decline", status_code=204)
def decline_request(token: str, payload: DeclineIn, _seller: str = Depends(token_guard)):
    """The seller can't supply. That is an answer, so the buyer's activity strip counts it."""
    rfq = store.get_rfq(store.token_to_rfq_id.get(token, ""))
    if not rfq:
        raise HTTPException(status_code=404, detail="This link isn't valid or has expired.")
    if rfq.status != "Open":
        raise HTTPException(status_code=409, detail="This request is already decided.")
    store.decline(token)
    return None


@app.post("/api/rfq-by-token/{token}/quoting", status_code=204)
def mark_quoting(token: str, _seller: str = Depends(token_guard)):
    if token not in store.token_to_rfq_id:
        raise HTTPException(status_code=404, detail="This link isn't valid or has expired.")
    store.touch_token(token, "quoting")
    return None


@app.get("/api/rfqs/{rfq_id}/activity", response_model=Activity)
def rfq_activity(rfq_id: str, user: AuthUser = Depends(buyer_only)):
    _rfq_for(user, rfq_id)
    return store.activity(rfq_id)


@app.get("/api/rfq-by-token/{token}/quotes/mine")
def get_my_quotes(token: str, _seller: str = Depends(token_guard)):
    return views.seller_my_quotes(store, token)


# --- 6. Supplier Profile & Products ---
@app.get("/api/supplier/profile/{supplier_id}", response_model=SupplierProfileOut)
def get_supplier_profile(supplier_id: str, user: AuthUser = Depends(seller_only)):
    _seller_for(user, supplier_id)
    p = store.get_supplier_profile(supplier_id)
    if not p:
        raise HTTPException(status_code=404, detail="Supplier profile not found.")
    return p


@app.put("/api/supplier/profile/{supplier_id}", response_model=SupplierProfileOut)
def update_supplier_profile(supplier_id: str, payload: SupplierProfileIn, user: AuthUser = Depends(seller_only)):
    _seller_for(user, supplier_id)
    return store.upsert_supplier_profile(supplier_id, payload)


@app.get("/api/supplier/products/{supplier_id}", response_model=List[SupplierProduct])
def list_supplier_products(supplier_id: str, user: AuthUser = Depends(seller_only)):
    _seller_for(user, supplier_id)
    return store.get_supplier_products(supplier_id)


@app.post("/api/supplier/products/{supplier_id}", response_model=SupplierProduct, status_code=201)
def add_supplier_product(supplier_id: str, payload: SupplierProductIn, user: AuthUser = Depends(seller_only)):
    _seller_for(user, supplier_id)
    return store.add_supplier_product(supplier_id, payload)


@app.put("/api/supplier/products/{supplier_id}/{product_id}", response_model=SupplierProduct)
def update_supplier_product(supplier_id: str, product_id: str, payload: SupplierProductIn, user: AuthUser = Depends(seller_only)):
    _seller_for(user, supplier_id)
    p = store.update_supplier_product(supplier_id, product_id, payload)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found.")
    return p


@app.delete("/api/supplier/products/{supplier_id}/{product_id}", status_code=204)
def delete_supplier_product(supplier_id: str, product_id: str, user: AuthUser = Depends(seller_only)):
    _seller_for(user, supplier_id)
    ok = store.delete_supplier_product(supplier_id, product_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Product not found.")
    return None


# --- 7. Buyer-side supplier profile (click-through) ---
@app.get("/api/rfqs/{rfq_id}/suppliers/{alias}")
def get_supplier_profile_for_buyer(rfq_id: str, alias: str, user: AuthUser = Depends(buyer_only)):
    """Before reveal: alias, state and what was checked. After reveal: the seller."""
    data = views.supplier_for_buyer(store, _rfq_for(user, rfq_id), alias)
    if data is None:
        raise HTTPException(status_code=404, detail="Supplier not found on this request.")
    return data


# --- 8. Chat (buyer + supplier token routes) ---
@app.get("/api/rfqs/{rfq_id}/threads/{alias}/messages", response_model=List[ChatMessage])
def get_chat_messages(rfq_id: str, alias: str, user: AuthUser = Depends(buyer_only)):
    rfq = _rfq_for(user, rfq_id)
    sid = _seller_by_alias(rfq_id, alias)
    msgs = views.chat_for_buyer(store, rfq, sid)
    # Free chat opens only after the buyer reveals this seller; engine targets the buyer sent still show.
    return msgs if store.is_revealed(rfq_id, sid) else [x for x in msgs if x.get("target")]


@app.post("/api/rfqs/{rfq_id}/threads/{alias}/messages", response_model=ChatMessage, status_code=201)
def post_chat_message(rfq_id: str, alias: str, payload: ChatMessageIn, user: AuthUser = Depends(buyer_only)):
    _rfq_for(user, rfq_id)
    sid = _networked_seller(rfq_id, alias)
    if not store.is_revealed(rfq_id, sid):
        raise HTTPException(status_code=403, detail={"code": "reveal_required", "message": "Reveal this seller to chat."})
    # The signed-in buyer is always the buyer here; the request body cannot pick the sender.
    return store.add_chat_message(rfq_id, sid, "buyer", payload.sender_name, payload.text)


@app.get("/api/rfq-by-token/{token}/messages", response_model=List[ChatMessage])
def get_chat_by_token(token: str, _seller: str = Depends(token_guard)):
    rfq_id, sid = store.token_to_rfq_id.get(token), store.token_to_supplier_id.get(token)
    rfq = store.rfqs.get(rfq_id) if rfq_id else None
    if not (rfq and sid):
        return []
    msgs = views.chat_for_seller(store, rfq, sid)
    # Free chat is locked until the buyer reveals this seller; the buyer's targets still show.
    return msgs if store.is_revealed(rfq_id, sid) else [x for x in msgs if x.get("target")]


@app.post("/api/rfq-by-token/{token}/messages", response_model=ChatMessage, status_code=201)
def post_chat_by_token(token: str, payload: ChatMessageIn, _seller: str = Depends(token_guard)):
    # A supplier link can only ever speak as the supplier, whatever the body says.
    rfq_id = store.token_to_rfq_id.get(token)
    if rfq_id and not store.is_revealed(rfq_id, _seller):
        raise HTTPException(status_code=403, detail={"code": "reveal_required", "message": "Chat opens when the buyer reveals you."})
    msg = store.add_chat_by_token(token, "supplier", payload.sender_name, payload.text)
    if msg is None:
        raise HTTPException(status_code=404, detail="Invalid or expired link.")
    return msg


# ─── Logistics (Delhivery): suggestions for a seller's freight and lead time, never applied automatically ───

class FreightIn(BaseModel):
    source_pin: str
    consignee_pin: str
    weight_kg: float
    length_cm: float = 10
    width_cm: float = 10
    height_cm: float = 10
    box_count: int = 1
    inv_amount: float = 0


@app.get("/api/logistics/status")
def logistics_status(user: AuthUser = Depends(get_current_user)):
    return {"enabled": delhivery.enabled()}


@app.get("/api/logistics/pincode/{pin}")
def logistics_pincode(pin: str, weight_kg: float = 1, user: AuthUser = Depends(get_current_user)):
    if not delhivery.valid_pin(pin):
        raise HTTPException(status_code=422, detail="Enter a 6-digit pincode.")
    raw = delhivery.pincode_service(pin, weight_kg)
    return {"enabled": delhivery.enabled(), "available": raw is not None, "raw": raw}


@app.post("/api/logistics/freight")
def logistics_freight(payload: FreightIn, user: AuthUser = Depends(get_current_user)):
    if not (delhivery.valid_pin(payload.source_pin) and delhivery.valid_pin(payload.consignee_pin)):
        raise HTTPException(status_code=422, detail="Enter two 6-digit pincodes.")
    if payload.weight_kg <= 0:
        raise HTTPException(status_code=422, detail="Weight must be above zero.")
    raw = delhivery.freight_estimate(
        payload.source_pin, payload.consignee_pin, round(payload.weight_kg * 1000), length_cm=payload.length_cm,
        width_cm=payload.width_cm, height_cm=payload.height_cm, box_count=payload.box_count, inv_amount=payload.inv_amount)
    amount = delhivery.find_number(raw, "total_amount", "total_charge", "total", "freight_charge", "freight", "amount") if raw is not None else None
    return {"enabled": delhivery.enabled(), "suggested_freight": amount, "source": "Delhivery estimate" if amount is not None else None, "raw": raw}


@app.get("/api/logistics/tat")
def logistics_tat(origin_pin: str, destination_pin: str, user: AuthUser = Depends(get_current_user)):
    if not (delhivery.valid_pin(origin_pin) and delhivery.valid_pin(destination_pin)):
        raise HTTPException(status_code=422, detail="Enter two 6-digit pincodes.")
    raw = delhivery.tat_estimate(origin_pin, destination_pin)
    days = delhivery.find_number(raw, "tat", "tat_days", "days", "estimated_days", "delivery_days") if raw is not None else None
    return {"enabled": delhivery.enabled(), "suggested_lead_days": days, "source": "Delhivery estimate" if days is not None else None, "raw": raw}


@app.post("/api/logistics/estimate")
def logistics_estimate(payload: FreightIn, user: AuthUser = Depends(get_current_user)):
    """Freight and delivery days for the seller's shipping choice. Live Delhivery numbers when available, else the
    labelled demo rate card. Only ever a suggestion: the seller applies it by hand and can edit it."""
    if not (delhivery.valid_pin(payload.source_pin) and delhivery.valid_pin(payload.consignee_pin)):
        raise HTTPException(status_code=422, detail="Enter two 6-digit pincodes.")
    if payload.weight_kg <= 0:
        raise HTTPException(status_code=422, detail="Weight must be above zero.")
    out = delhivery.estimate(payload.source_pin, payload.consignee_pin, payload.weight_kg, length_cm=payload.length_cm,
                             width_cm=payload.width_cm, height_cm=payload.height_cm, box_count=payload.box_count,
                             inv_amount=payload.inv_amount)
    return out


class ShippingEstimateIn(BaseModel):
    weight_kg: float


@app.post("/api/rfq-by-token/{token}/shipping-estimate")
def shipping_estimate(token: str, payload: ShippingEstimateIn, _seller: str = Depends(token_guard)):
    """Freight and delivery days for this quote link, from the two pincodes saved at sign-up. The pincodes stay on the
    server; the seller only sees the result, which they apply by hand."""
    if payload.weight_kg <= 0:
        raise HTTPException(status_code=422, detail="Weight must be above zero.")
    pins = store.shipping_pins(token)
    if not pins:
        raise HTTPException(status_code=409, detail="No estimate for this request: a pincode is missing. Enter freight and lead time yourself.")
    out = delhivery.estimate(pins[0], pins[1], payload.weight_kg)
    if not out:
        raise HTTPException(status_code=409, detail="No estimate available. Enter freight and lead time yourself.")
    return out


@app.get("/api/demo/logins")
def demo_logins():
    """One-click demo seller logins for the sign-in page. Off unless DEMO_LOGINS=on and DEMO_SELLER_PASSWORD is set,
    because it hands out a shared password: use it for a local demo, never on a public deployment."""
    if not demo_roster.logins_enabled():
        return {"enabled": False, "sellers": []}
    return {"enabled": True, "password": os.environ["DEMO_SELLER_PASSWORD"], "sellers": demo_roster.public_listing()}




class AskIn(BaseModel):
    question: str


@app.post("/api/rfqs/{rfq_id}/ask")
def ask_the_desk(rfq_id: str, payload: AskIn, user: AuthUser = Depends(buyer_only)):
    """A what-if question about this request's quotes. The engine recomputes; nothing is saved or changed."""
    rfq = _rfq_for(user, rfq_id)
    return ask_desk.run(store, rfq, payload.question[:300])


@app.get("/api/rfqs/{rfq_id}/suggestions")
def desk_suggestions(rfq_id: str, user: AuthUser = Depends(buyer_only)):
    """What the buyer could do for a better outcome, worked out by the engine. Nothing is changed."""
    return {"suggestions": ask_desk.suggestions(store, _rfq_for(user, rfq_id))}


# ─── Serve the built website from the same address (one public URL, https from the host, no CORS) ───
from pathlib import Path
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

_DIST = Path(os.environ.get("WEB_DIST") or Path(__file__).resolve().parents[2] / "app" / "dist")
if (_DIST / "index.html").is_file():
    if (_DIST / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def web(path: str):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found.")
        target = (_DIST / path).resolve()
        if path and target.is_file() and _DIST.resolve() in target.parents:
            return FileResponse(target)
        return FileResponse(_DIST / "index.html")        # the app's own routes (/app, /supplier, /share/...)
