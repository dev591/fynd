"""Pydantic models for API request/response validation."""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

# ============ Quote Models ============

class QuoteCreate(BaseModel):
    price: float = Field(..., gt=0)
    lead_days: int = Field(..., ge=0)
    packing_json: Optional[str] = None
    notes: Optional[str] = None

class QuoteRead(BaseModel):
    id: str
    rfq_id: str
    supplier_id: str
    version: int
    price: float
    lead_days: int
    packing_json: Optional[str]
    notes: Optional[str]
    submitted_at: int
    rejected: bool

# ============ Supplier Profile Models ============

class SupplierProfileCreate(BaseModel):
    email: str
    company: str
    state: str
    business_type: str
    categories: List[str] = Field(..., min_length=1)
    regions: List[str] = Field(..., min_length=1)
    default_lead_days: int = Field(..., ge=0)
    gst_inclusive_default: bool

class SupplierProfileRead(BaseModel):
    id: str
    email: str
    company: str
    state: str
    business_type: str
    categories: List[str]
    regions: List[str]
    default_lead_days: int
    gst_inclusive_default: bool
    verification_json: Optional[str]
    created_at: int

# ============ Product Models ============

class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1)

class ProductRead(BaseModel):
    id: str
    supplier_id: str
    name: str
    category: str
    photo_path: Optional[str]
    created_at: int

# ============ RFQ Models ============

class RFQCreate(BaseModel):
    item: str = Field(..., min_length=1)
    quantity_needed: int = Field(..., gt=0)
    need_by_days: int = Field(..., ge=0)

class RFQRead(BaseModel):
    id: str
    buyer_id: str
    item: str
    quantity_needed: int
    need_by_days: int
    created_at: int
    decided_quote_id: Optional[str]

# ============ RFQ Invite / Token Response ============

class RFQInviteRead(BaseModel):
    rfq_id: str
    supplier_id: str
    token: str

class RFQByTokenRead(BaseModel):
    rfq_id: str
    supplier_id: str
    item: str
    quantity_needed: int
    need_by_days: int

# ============ Target Models ============

class TargetCreate(BaseModel):
    target_type: str
    target_value: float

class TargetRead(BaseModel):
    id: str
    rfq_id: str
    target_type: str
    target_value: float
    created_at: int

# ============ Message Models ============

class MessageCreate(BaseModel):
    rfq_id: str
    content: str = Field(..., min_length=1)
    sender_type: str = Field(..., pattern='^(buyer|supplier)$')
    supplier_id: Optional[str] = None
    token: Optional[str] = None

class MessageRead(BaseModel):
    id: str
    rfq_id: str
    supplier_id: Optional[str]
    sender_type: str
    content: str
    created_at: int

# ============ RFQ Supplier View Models ============

class RFQSupplierView(BaseModel):
    supplier: Optional[SupplierProfileRead]
    latest_quote: Optional[QuoteRead]
