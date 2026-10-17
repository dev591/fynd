import asyncio, json, os
from typing import List, Optional
from fastapi import FastAPI, HTTPException, status
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
)
from .validators import cross_check_tax, mask_pan
from .engine import evaluate, run_case_checks, negotiation
from .rfq_store import store

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
async def run(body: RunIn):
    ctx = Ctx(body.query, body.tenant, body.meta)
    r = await pipeline.run(ctx)
    return {"request_id": ctx.request_id, **r.__dict__}


@app.get("/stats")
def stats():
    return pipeline.summary()


@app.get("/trace/stream")
async def trace_stream():
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
def save_profile(profile: Profile):
    # Mask PAN before saving to prevent raw leak
    if profile.pan_masked is None and profile.gstin:
        profile.pan_masked = mask_pan(profile.gstin[2:12])
    store.profiles[profile.id] = profile
    return profile


@app.get("/api/profile/{profile_id}", response_model=Profile)
def get_profile(profile_id: str):
    p = store.profiles.get(profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found.")
    return p


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
def create_rfq(payload: RFQCreate):
    rfq = store.create_rfq(payload)
    return {
        "id": rfq.id,
        "token": rfq.token,
        "supplier_url": f"/supplier/quote?token={rfq.token}",
        "supplier_tokens": rfq.supplier_tokens,
        "matched": len(rfq.supplier_tokens),
        "supplier_urls": {
            sid: f"/supplier/quote?token={tok}"
            for sid, tok in rfq.supplier_tokens.items()
        },
        "rfq": rfq,
    }


@app.get("/api/suppliers")
def list_suppliers():
    return store.list_suppliers()


@app.get("/api/supplier/{supplier_id}/notifications", response_model=List[NotificationOut])
def list_notifications(supplier_id: str):
    return store.list_notifications(supplier_id)


@app.post("/api/supplier/{supplier_id}/notifications/{notification_id}/read", response_model=NotificationOut)
def read_notification(supplier_id: str, notification_id: str):
    n = store.mark_notification_viewed(supplier_id, notification_id)
    if not n:
        raise HTTPException(status_code=404, detail="Notification not found.")
    return n


@app.get("/api/rfqs", response_model=List[RFQ])
def list_rfqs():
    return list(store.rfqs.values())


@app.get("/api/rfqs/{rfq_id}")
def get_rfq_details(rfq_id: str):
    rfq = store.get_rfq(rfq_id)
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found.")

    quotes_by_supplier = store.quotes.get(rfq_id, {})
    targets_by_supplier = store.targets.get(rfq_id, {})

    # Evaluate latest quotes using Crossover engine
    engine_quotes = store.get_latest_quotes_as_engine_input(rfq_id)
    evaluation = None
    if engine_quotes:
        need = Need(item=rfq.item, qty=rfq.qty, need_in_days=rfq.need_in_days)
        evaluation = evaluate(engine_quotes, need, mode=rfq.priority_mode)

    return {
        "rfq": rfq,
        "quotes": quotes_by_supplier,
        "targets": targets_by_supplier,
        "evaluation": evaluation,
        "activity": store.activity(rfq_id),
    }


@app.post("/api/rfqs/{rfq_id}/targets", response_model=NegotiationTarget)
def send_target_to_supplier(rfq_id: str, payload: NegotiationTargetIn):
    try:
        return store.send_target(
            rfq_id=rfq_id,
            supplier_id=payload.supplier_id,
            cut_needed=payload.cut_needed,
            target_freight=payload.target_freight,
            target_per_unit=payload.target_per_unit,
            concession_type=payload.concession_type,
            message=payload.message,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/rfqs/{rfq_id}/decision")
def record_decision(rfq_id: str, payload: DecisionIn):
    try:
        return store.save_decision(
            rfq_id=rfq_id,
            winner_id=payload.winner_id,
            reason=payload.reason,
            approver=payload.approver,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/recommendations")
def list_recommendations():
    return store.decisions


# --- 5. Supplier Sealed Bids (Token Routes) ---
@app.get("/api/rfq-by-token/{token}")
def get_rfq_by_token(token: str):
    data = store.get_rfq_by_token(token)
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
            origin=payload.origin,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/rfq-by-token/{token}/draft", response_model=DraftQuote)
def get_draft_quote(token: str):
    draft = store.draft_for_token(token)
    if not draft:
        raise HTTPException(status_code=404, detail="No catalog match for this request.")
    return draft


@app.post("/api/rfq-by-token/{token}/quoting", status_code=204)
def mark_quoting(token: str):
    if token not in store.token_to_rfq_id:
        raise HTTPException(status_code=404, detail="This link isn't valid or has expired.")
    store.touch_token(token, "quoting")
    return None


@app.get("/api/rfqs/{rfq_id}/activity", response_model=Activity)
def rfq_activity(rfq_id: str):
    if not store.get_rfq(rfq_id):
        raise HTTPException(status_code=404, detail="RFQ not found.")
    return store.activity(rfq_id)


@app.get("/api/rfq-by-token/{token}/quotes/mine")
def get_my_quotes(token: str):
    return store.get_supplier_quotes_and_target(token)


# --- 6. Supplier Profile & Products ---
@app.get("/api/supplier/profile/{supplier_id}", response_model=SupplierProfileOut)
def get_supplier_profile(supplier_id: str):
    p = store.get_supplier_profile(supplier_id)
    if not p:
        raise HTTPException(status_code=404, detail="Supplier profile not found.")
    return p


@app.put("/api/supplier/profile/{supplier_id}", response_model=SupplierProfileOut)
def update_supplier_profile(supplier_id: str, payload: SupplierProfileIn):
    return store.upsert_supplier_profile(supplier_id, payload)


@app.get("/api/supplier/products/{supplier_id}", response_model=List[SupplierProduct])
def list_supplier_products(supplier_id: str):
    return store.get_supplier_products(supplier_id)


@app.post("/api/supplier/products/{supplier_id}", response_model=SupplierProduct, status_code=201)
def add_supplier_product(supplier_id: str, payload: SupplierProductIn):
    return store.add_supplier_product(supplier_id, payload)


@app.put("/api/supplier/products/{supplier_id}/{product_id}", response_model=SupplierProduct)
def update_supplier_product(supplier_id: str, product_id: str, payload: SupplierProductIn):
    p = store.update_supplier_product(supplier_id, product_id, payload)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found.")
    return p


@app.delete("/api/supplier/products/{supplier_id}/{product_id}", status_code=204)
def delete_supplier_product(supplier_id: str, product_id: str):
    ok = store.delete_supplier_product(supplier_id, product_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Product not found.")
    return None


# --- 7. Buyer-side supplier profile (click-through) ---
@app.get("/api/rfqs/{rfq_id}/suppliers/{supplier_id}")
def get_supplier_profile_for_buyer(rfq_id: str, supplier_id: str):
    data = store.get_supplier_profile_for_buyer(rfq_id, supplier_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Supplier not found on this request.")
    return data


# --- 8. Chat (buyer + supplier token routes) ---
@app.get("/api/rfqs/{rfq_id}/threads/{supplier_id}/messages", response_model=List[ChatMessage])
def get_chat_messages(rfq_id: str, supplier_id: str):
    return store.get_chat_messages(rfq_id, supplier_id)


@app.post("/api/rfqs/{rfq_id}/threads/{supplier_id}/messages", response_model=ChatMessage, status_code=201)
def post_chat_message(rfq_id: str, supplier_id: str, payload: ChatMessageIn):
    if rfq_id not in store.rfqs:
        raise HTTPException(status_code=404, detail="RFQ not found.")
    return store.add_chat_message(rfq_id, supplier_id, payload.sender, payload.sender_name, payload.text)


@app.get("/api/rfq-by-token/{token}/messages", response_model=List[ChatMessage])
def get_chat_by_token(token: str):
    return store.get_chat_by_token(token)


@app.post("/api/rfq-by-token/{token}/messages", response_model=ChatMessage, status_code=201)
def post_chat_by_token(token: str, payload: ChatMessageIn):
    msg = store.add_chat_by_token(token, payload.sender, payload.sender_name, payload.text)
    if msg is None:
        raise HTTPException(status_code=404, detail="Invalid or expired link.")
    return msg
