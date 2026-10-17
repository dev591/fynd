from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field, field_validator


class Role(str, Enum):
    BUYER = "buyer"
    SUPPLIER = "supplier"


class BusinessType(str, Enum):
    MANUFACTURER = "manufacturer"
    TRADER = "trader"
    DISTRIBUTOR = "distributor"
    OTHER = "other"


class Verification(BaseModel):
    email: bool = False
    tax_ids_consistent: bool = False
    registry: Literal["none", "demo", "live"] = "none"


class BuyerSetup(BaseModel):
    gst_claimable: bool = True
    spend_band: str = "₹20L to 1Cr"
    need_by_buffer_days: int = 5


class SupplierSetup(BaseModel):
    default_lead_days: int = 3
    gst_inclusive_default: bool = False
    regions: list[str] = Field(default_factory=lambda: ["Maharashtra"])


class Profile(BaseModel):
    id: str
    role: Role
    full_name: str
    email: str
    phone: str
    company: str
    business_type: BusinessType
    state: str
    city: str
    categories: list[str] = Field(default_factory=list)
    gstin: str | None = None
    pan_masked: str | None = None
    verification: Verification = Field(default_factory=Verification)
    buyer: BuyerSetup | None = None
    supplier: SupplierSetup | None = None


# Crossover Engine Models
class Quote(BaseModel):
    id: str
    supplier: str
    item: str
    pack_price: float
    pack_size: int | None = None
    freight: float = 0.0
    lead_days: int
    moq: int | None = None
    max_qty: int | None = None  # stock / capacity cap; None = unlimited
    raw: str = ""
    channel: str = "Portal"


class Need(BaseModel):
    item: str
    qty: int
    need_in_days: int


class ExceptionRecord(BaseModel):
    reason: str
    approver: str


class OrderCalc(BaseModel):
    packs: int
    units: int
    overbuy: int
    landed: float


class EvaluatedRow(BaseModel):
    quote_id: str
    supplier: str
    status: Literal["eligible", "exception", "blocked"]
    reason: str | None = None
    approved: bool = False
    packs: int = 0
    units: int = 0
    overbuy: int = 0
    landed: float | None = None
    lead_days: int
    pack_price: float
    pack_size: int | None = None
    freight: float
    fill_qty: int | None = None  # units the seller can actually cover when below the need


PriorityMode = Literal["cheapest", "fastest", "balanced"]
QuoteOrigin = Literal["manual", "ai_draft_edited", "ai_draft_sent", "auto"]
RequestSource = Literal["form", "chat", "voice"]


class CompareResult(BaseModel):
    rows: list[EvaluatedRow]
    pool: list[EvaluatedRow]
    winner: EvaluatedRow | None
    tie: bool
    cheaper_excluded: list[EvaluatedRow]
    mode: PriorityMode = "cheapest"
    # Winner under every mode, so the trade-off is visible.
    winners: dict[str, EvaluatedRow | None] = Field(default_factory=dict)


# RFQ Lifecycle Models
class RFQCreate(BaseModel):
    item: str
    qty: int
    need_in_days: int
    buyer_company: str
    buyer_name: str
    buyer_city: str = "Pune"
    buyer_state: str = "Maharashtra"
    note: str | None = None
    priority_mode: PriorityMode = "cheapest"
    source: RequestSource = "form"


class RFQ(BaseModel):
    id: str
    token: str  # primary token (backward compat)
    item: str
    qty: int
    need_in_days: int
    buyer_company: str
    buyer_name: str
    buyer_city: str
    buyer_state: str
    note: str | None = None
    created_at: str
    status: Literal["Open", "Decided", "Closed"] = "Open"
    decision: dict | None = None
    priority_mode: PriorityMode = "cheapest"
    source: RequestSource = "form"
    owner_id: str | None = None   # the signed-in buyer who created it; None only for the shared demo request
    supplier_tokens: dict[str, str] = Field(default_factory=dict)  # supplier_id -> token


class QuoteSubmitIn(BaseModel):
    supplier_name: str = "Supplier"
    pack_price: float
    pack_size: int
    freight: float
    lead_days: int
    moq: int | None = None
    max_qty: int | None = None
    notes: str | None = None
    origin: QuoteOrigin = "manual"


class QuoteVersion(BaseModel):
    version: int
    supplier_id: str
    supplier_name: str
    pack_price: float
    pack_size: int
    freight: float
    lead_days: int
    moq: int | None = None
    max_qty: int | None = None
    notes: str | None = None
    origin: QuoteOrigin = "manual"
    landed_cost: float
    units: int
    packs: int
    submitted_at: str


class NegotiationTargetIn(BaseModel):
    supplier_id: str
    cut_needed: float
    target_freight: float | None = None
    target_per_unit: float | None = None
    concession_type: Literal["freight", "unit_price"] = "freight"
    message: str | None = None
    sent_by: str = Field(min_length=1)  # a named person sends every target; the system never does

    @field_validator("sent_by")
    @classmethod
    def _named(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("sent_by must name the person sending the target")
        return v.strip()


class NegotiationTarget(BaseModel):
    id: str
    supplier_id: str
    message: str
    cut_needed: float
    target_freight: float | None = None
    target_per_unit: float | None = None
    concession_type: str
    sent_at: str
    sent_by: str = ""
    status: Literal["pending", "accepted", "declined"] = "pending"


class DecisionIn(BaseModel):
    winner_id: str
    reason: str
    approver: str


# ─── Supplier Profile & Products ───────────────────────────────────────────

class PriceBreak(BaseModel):
    min_qty: int
    pack_price: float


class SupplierProductIn(BaseModel):
    name: str
    category: str = "general"
    pack_price: float
    pack_size: int
    moq: int = 1
    usual_lead_days: int = 3
    capacity_cap: int | None = None
    unit: str = "pc"
    stock: int | None = None  # snapshot, not reserved; None = not tracked
    freight: float = 0.0
    price_breaks: list[PriceBreak] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)  # alternative names used for matching


class SupplierProduct(BaseModel):
    id: str
    name: str
    category: str = "general"
    pack_price: float
    pack_size: int
    moq: int = 1
    usual_lead_days: int = 3
    capacity_cap: int | None = None
    unit: str = "pc"
    stock: int | None = None  # snapshot, not reserved; None = not tracked
    freight: float = 0.0
    price_breaks: list[PriceBreak] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)


class SupplierProfileIn(BaseModel):
    business_name: str
    location_city: str
    location_state: str
    categories: list[str] = Field(default_factory=list)
    description: str | None = None


class SupplierProfileOut(BaseModel):
    supplier_id: str
    business_name: str
    location_city: str
    location_state: str
    categories: list[str] = Field(default_factory=list)
    description: str | None = None
    verification_tier: Literal["email", "tax_ids", "registry", "none"] = "none"
    synthetic: bool = True  # all demo sellers are synthetic and labelled so
    products: list[SupplierProduct] = Field(default_factory=list)


# ─── Chat ──────────────────────────────────────────────────────────────────

class ChatMessageIn(BaseModel):
    sender: Literal["buyer", "supplier"]
    sender_name: str
    text: str


class ChatMessage(BaseModel):
    id: str
    sender: Literal["buyer", "supplier"]
    sender_name: str
    text: str
    timestamp: str
    target: NegotiationTarget | None = None


# ─── Supplier invite ───────────────────────────────────────────────────────

class SupplierInviteIn(BaseModel):
    supplier_id: str  # for seeded data; auto-generated if blank
    supplier_name: str | None = None


# ─── Matching, notifications, seller inbox ─────────────────────────────────

class Verdict(BaseModel):
    can_fulfil: Literal["yes", "partly", "no"]
    reasons: list[str] = Field(default_factory=list)


class Notification(BaseModel):
    id: str
    rfq_id: str
    supplier_id: str
    product_id: str
    token: str
    created_at: str
    status: Literal["new", "viewed", "quoting"] = "new"


class NotificationOut(BaseModel):
    id: str
    rfq_id: str
    supplier_id: str
    status: Literal["new", "viewed", "quoting"]
    created_at: str
    item: str
    qty: int
    need_in_days: int
    buyer_company: str
    buyer_city: str
    buyer_state: str
    note: str | None = None
    priority_mode: PriorityMode = "cheapest"
    rfq_status: str
    token: str
    quote_url: str
    product: SupplierProduct
    verdict: Verdict
    has_quoted: bool = False


class DraftQuote(BaseModel):
    """A quote prefilled from the seller's own catalog row. Every number is copied by code."""
    product_id: str
    product_name: str
    pack_price: float
    pack_size: int
    freight: float
    lead_days: int
    moq: int
    max_qty: int | None = None
    price_break_applied: int | None = None  # min_qty of the break used, if any
    verdict: Verdict


class Activity(BaseModel):
    """Funnel of seller reactions for one request. Each stage includes the later ones."""
    notified: int = 0
    viewed: int = 0
    quoting: int = 0
    quoted: int = 0


# ─── Buyer intake ──────────────────────────────────────────────────────────

class IntakeIn(BaseModel):
    text: str = Field(max_length=1000)


class ConfirmIn(BaseModel):
    """The confirm card, after a person has checked every field."""
    item: str = Field(min_length=1)
    qty: int = Field(gt=0)
    need_in_days: int = Field(gt=0)
    priority_mode: PriorityMode = "cheapest"
    source: RequestSource = "form"
    buyer_company: str
    buyer_name: str
    buyer_city: str = "Pune"
    buyer_state: str = "Maharashtra"
    note: str | None = None
    intake_id: str | None = None


class AutopilotSettings(BaseModel):
    """Seller autopilot. Off by default. It only ever opens a quote; it never answers a buyer's target."""
    enabled: bool = False
