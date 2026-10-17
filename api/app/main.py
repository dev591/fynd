import asyncio, json, os
from .env import load_env

load_env()  # reads api/.env before anything reads os.environ
from typing import List, Optional
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
)
from .validators import cross_check_tax, mask_pan
from .intake import draft_from_text
from . import ai, assistant
from .summary import build_summary, savings_total
from .engine import evaluate, run_case_checks, negotiation
from .rfq_store import store
from .auth import AuthUser, get_current_user
from . import views
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


def _demo_sellers_allowed() -> bool:
    return os.environ.get("ALLOW_DEMO_SELLERS", "true").lower() != "false"


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
app = FastAPI(title="Crossover Decision Engine & RFQ API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    return _rfq_response(store.create_rfq(payload, owner_id=user.id))


@app.post("/api/rfqs/confirm")
def confirm_rfq(payload: ConfirmIn, user: AuthUser = Depends(buyer_only)):
    """Creates the request from the confirm card. The only way an intake draft becomes a request."""
    rfq = store.create_rfq(RFQCreate(
        item=payload.item.strip(), qty=payload.qty, need_in_days=payload.need_in_days,
        buyer_company=payload.buyer_company, buyer_name=payload.buyer_name,
        buyer_city=payload.buyer_city, buyer_state=payload.buyer_state,
        note=payload.note, priority_mode=payload.priority_mode, source=payload.source,
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
    return [e for e in store.ai_log_for(rfq_id) if e["kind"] in ("intake_draft", "transcribe")]


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


@app.post("/api/rfqs/{rfq_id}/targets", response_model=NegotiationTarget)
def send_target_to_supplier(rfq_id: str, payload: NegotiationTargetIn, user: AuthUser = Depends(buyer_only)):
    _rfq_for(user, rfq_id)
    sid = _seller_by_alias(rfq_id, payload.supplier_id)         # the buyer speaks in aliases
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
    return {"alias": alias, "kind": kind, "seller": views.identity_of(store, sid), "plan": views.plan_info(store, user.id)}


@app.get("/api/me/plan")
def my_plan(user: AuthUser = Depends(buyer_only)):
    return views.plan_info(store, user.id)


@app.post("/api/dev/mock-upgrade")
def mock_upgrade(user: AuthUser = Depends(buyer_only)):
    """DEV ONLY. No payment happens; this flips the account to unlimited reveals so the paywall can be demoed."""
    store.plans[user.id] = "pro"
    return {**views.plan_info(store, user.id), "note": "Mock upgrade for the demo. No payment was taken and none is stored."}


@app.post("/api/demo/sample-request")
def sample_request(user: AuthUser = Depends(buyer_only)):
    """A personal sample request with synthetic quotes already in. Used by the empty state."""
    p = store.profiles.get(user.id)
    rfq = store.create_sample_rfq(user.id, p.company if p else "My company", p.full_name if p else "Buyer",
                                  p.city if p else "Pune", p.state if p else "Maharashtra")
    return _rfq_response(rfq)


@app.post("/api/rfqs/{rfq_id}/decision")
def record_decision(rfq_id: str, payload: DecisionIn, user: AuthUser = Depends(buyer_only)):
    """Order handoff. The chosen seller must have been revealed first, so the buyer can actually contact them."""
    _rfq_for(user, rfq_id)
    sid = _seller_by_alias(rfq_id, payload.winner_id)
    if not store.is_revealed(rfq_id, sid):
        raise HTTPException(status_code=409, detail={"code": "reveal_required",
                            "message": "Reveal this seller before saving the order."})
    try:
        return store.save_decision(rfq_id=rfq_id, winner_id=payload.winner_id, reason=payload.reason, approver=payload.approver)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/recommendations")
def list_recommendations(user: AuthUser = Depends(buyer_only)):
    return {rid: d for rid, d in store.decisions.items() if store.rfqs[rid].owner_id == user.id}


# --- 5. Supplier Sealed Bids (Token Routes) ---
@app.get("/api/rfq-by-token/{token}")
def get_rfq_by_token(token: str):
    data = views.seller_request(store, token)
    if not data:
        raise HTTPException(status_code=404, detail="This link isn't valid or has expired.")
    return data


@app.post("/api/rfq-by-token/{token}/quotes", response_model=QuoteVersion)
def submit_supplier_quote(token: str, payload: QuoteSubmitIn):
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
        )   # origin is decided by the server, never taken from the client
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/rfq-by-token/{token}/draft", response_model=DraftQuote)
def get_draft_quote(token: str):
    draft = store.draft_for_token(token)
    if not draft:
        raise HTTPException(status_code=404, detail="No catalog match for this request.")
    return draft


@app.get("/api/rfq-by-token/{token}/assist")
def seller_assist(token: str):
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
def seller_item_match(token: str, payload: ItemMatchIn):
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


@app.post("/api/rfq-by-token/{token}/quoting", status_code=204)
def mark_quoting(token: str):
    if token not in store.token_to_rfq_id:
        raise HTTPException(status_code=404, detail="This link isn't valid or has expired.")
    store.touch_token(token, "quoting")
    return None


@app.get("/api/rfqs/{rfq_id}/activity", response_model=Activity)
def rfq_activity(rfq_id: str, user: AuthUser = Depends(buyer_only)):
    _rfq_for(user, rfq_id)
    return store.activity(rfq_id)


@app.get("/api/rfq-by-token/{token}/quotes/mine")
def get_my_quotes(token: str):
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
    return views.chat_for_buyer(store, rfq, _seller_by_alias(rfq_id, alias))


@app.post("/api/rfqs/{rfq_id}/threads/{alias}/messages", response_model=ChatMessage, status_code=201)
def post_chat_message(rfq_id: str, alias: str, payload: ChatMessageIn, user: AuthUser = Depends(buyer_only)):
    _rfq_for(user, rfq_id)
    sid = _seller_by_alias(rfq_id, alias)
    # The signed-in buyer is always the buyer here; the request body cannot pick the sender.
    return store.add_chat_message(rfq_id, sid, "buyer", payload.sender_name, payload.text)


@app.get("/api/rfq-by-token/{token}/messages", response_model=List[ChatMessage])
def get_chat_by_token(token: str):
    rfq_id, sid = store.token_to_rfq_id.get(token), store.token_to_supplier_id.get(token)
    rfq = store.rfqs.get(rfq_id) if rfq_id else None
    return views.chat_for_seller(store, rfq, sid) if rfq and sid else []


@app.post("/api/rfq-by-token/{token}/messages", response_model=ChatMessage, status_code=201)
def post_chat_by_token(token: str, payload: ChatMessageIn):
    # A supplier link can only ever speak as the supplier, whatever the body says.
    msg = store.add_chat_by_token(token, "supplier", payload.sender_name, payload.text)
    if msg is None:
        raise HTTPException(status_code=404, detail="Invalid or expired link.")
    return msg
