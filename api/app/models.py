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
    # One account can hold both roles. Normalised by the server; the wizard's single `role` still seeds it.
    roles: list[Literal["buyer", "seller"]] = Field(default_factory=list)


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
    # Per mode: extra rupees and days saved against the cheapest pick, plus a plain sentence. Engine numbers only.
    tradeoffs: dict[str, dict] = Field(default_factory=dict)


# RFQ Lifecycle Models
class RFQCreate(BaseModel):
    item: str
    qty: int
    need_in_days: int
    buyer_company: str
    buyer_name: str
    buyer_city: str = ""      # filled from the buyer's profile when blank; never invented
    buyer_state: str = ""
    note: str | None = None
    priority_mode: PriorityMode = "cheapest"
    source: RequestSource = "form"
    gst_claimable: bool | None = None         # None = use the buyer's profile policy, else claimable
    window: Literal["15m", "today", "24h", "3d"] | None = None    # how long sellers have to quote; None = from priority


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
    owner_id: str | None = None   # the signed-in buyer who created it
    gst_claimable: bool = True    # compare ex-GST when true, GST-inclusive when false
    window_key: str = "24h"       # 15m | today | 24h | 3d
    window_label: str = ""
    window_ends_at: str | None = None
    window_closed: bool = False   # new sellers can no longer start a quote; quoted sellers can still revise
    min_quotes: int = 3           # how many quotes count as "enough"
    demo_timing: bool = False     # true when DEMO_WINDOW_MINUTES shortened the window for a demo
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
    tax_rate: float | None = Field(default=None, ge=0, le=100)     # GST rate in percent, only if the seller states it
    price_includes_tax: bool | None = None                          # whether the pack price already includes GST


class QuoteVersion(BaseModel):
    version: int
    supplier_id: str
    supplier_name: str
    pack_price: float
    pack_size: int | None = None              # None only for imported rows that did not say; the engine blocks those
    freight: float
    lead_days: int
    moq: int | None = None
    max_qty: int | None = None
    notes: str | None = None
    origin: QuoteOrigin = "manual"
    tax_rate: float | None = None
    price_includes_tax: bool | None = None
    compare_price: float | None = None        # the pack price the engine compared, on the buyer's GST basis
    tax_basis: Literal["stated", "assumed_exclusive"] = "assumed_exclusive"
    landed_cost: float | None = None          # None when the pack size is unknown: no honest total exists
    units: int = 0
    packs: int = 0
    submitted_at: str
    item: str | None = None                   # only set when an imported row names a different item than the request
    imported: bool = False                    # brought in by the buyer from a file; the seller has no portal


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
    # Private until a buyer reveals this seller. Never returned by a buyer-facing view before then.
    contact_name: str | None = None
    phone: str | None = None
    email: str | None = None
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
    status: Literal["new", "viewed", "quoting", "declined"] = "new"
    unlocked_at: str | None = None    # set when the buyer reveals this seller
    reminder: str | None = None       # a nudge shown until the seller opens the request
    reminded: list[str] = Field(default_factory=list)    # which nudges were sent: "halfway", "final"


class NotificationOut(BaseModel):
    id: str
    rfq_id: str
    supplier_id: str
    status: Literal["new", "viewed", "quoting", "declined"]
    created_at: str
    item: str
    qty: int
    need_in_days: int
    buyer_descriptor: str                   # e.g. "Manufacturer, Telangana"; never a name, company or city
    note: str | None = None
    priority_mode: PriorityMode = "cheapest"
    unlocked: bool = False                  # true once this buyer has revealed this seller
    buyer_contact: dict | None = None       # only present when unlocked
    rfq_status: str
    token: str
    quote_url: str
    reminder: str | None = None
    closes_at: str | None = None
    window_closed: bool = False
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
    declined: int = 0


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
    buyer_city: str = ""      # filled from the buyer's profile when blank; never invented
    buyer_state: str = ""
    note: str | None = None
    intake_id: str | None = None
    gst_claimable: bool | None = None
    window: Literal["15m", "today", "24h", "3d"] | None = None


class AutopilotSettings(BaseModel):
    """Seller autopilot. Off by default. It only ever opens a quote; it never answers a buyer's target."""
    enabled: bool = False


class RoleIn(BaseModel):
    role: Literal["buyer", "seller"]


class ExceptionIn(BaseModel):
    """A person's written reason for breaking a gate (late or short supplier), and who approved it."""
    alias: str
    reason: str
    approver: str

    @field_validator("reason", "approver")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("a reason and a named approver are both required")
        return v.strip()


class DeclineIn(BaseModel):
    reason: str | None = Field(default=None, max_length=300)    # stays with the seller; never shown to the buyer


class ImportIn(BaseModel):
    format: Literal["csv", "json"]
    data: str = Field(max_length=200_000)


class BuyerNotice(BaseModel):
    """The buyer's bell: the first quote, enough quotes, and the window closing with the best option."""
    id: str
    rfq_id: str
    kind: Literal["first_quote", "enough_quotes", "window_closed"]
    message: str
    created_at: str
    read: bool = False
