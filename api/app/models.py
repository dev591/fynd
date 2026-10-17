from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field


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


class CompareResult(BaseModel):
    rows: list[EvaluatedRow]
    pool: list[EvaluatedRow]
    winner: EvaluatedRow | None
    tie: bool
    cheaper_excluded: list[EvaluatedRow]


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


class NegotiationTarget(BaseModel):
    id: str
    supplier_id: str
    message: str
    cut_needed: float
    target_freight: float | None = None
    target_per_unit: float | None = None
    concession_type: str
    sent_at: str
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
