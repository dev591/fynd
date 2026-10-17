/**
 * TypeScript contracts for FYND API
 * Mirrors all Pydantic models from the backend
 */

// ============ Request Types ============

export interface RFQCreate {
  item: string;
  quantity_needed: number;
  need_by_days: number;
}

export interface QuoteCreate {
  price: number;
  lead_days: number;
  packing_json?: string;
  notes?: string;
}

export interface TargetCreate {
  target_type: string;
  target_value: number;
}

export interface SupplierProfileCreate {
  email: string;
  company: string;
  state: string;
  business_type: string;
  categories: string[];
  regions: string[];
  default_lead_days: number;
  gst_inclusive_default: boolean;
}

export interface ProductCreate {
  name: string;
  category: string;
}

export interface MessageCreate {
  rfq_id: string;
  content: string;
  sender_type: "buyer" | "supplier";
  supplier_id?: string;
  token?: string;
}

// ============ Response Types ============

export interface RFQRead {
  id: string;
  buyer_id: string;
  item: string;
  quantity_needed: number;
  need_by_days: number;
  created_at: number;
  decided_quote_id?: string;
}

export interface RFQInviteRead {
  rfq_id: string;
  supplier_id: string;
  token: string;
}

export interface QuoteRead {
  id: string;
  rfq_id: string;
  supplier_id: string;
  version: number;
  price: number;
  lead_days: number;
  packing_json?: string;
  notes?: string;
  submitted_at: number;
  rejected: boolean;
}

export interface TargetRead {
  id: string;
  rfq_id: string;
  target_type: string;
  target_value: number;
  created_at: number;
}

export interface SupplierProfileRead {
  id: string;
  email: string;
  company: string;
  state: string;
  business_type: string;
  categories: string[];
  regions: string[];
  default_lead_days: number;
  gst_inclusive_default: boolean;
  verification_json?: string;
  created_at: number;
}

export interface ProductRead {
  id: string;
  supplier_id: string;
  name: string;
  category: string;
  photo_path?: string;
  created_at: number;
}

export interface MessageRead {
  id: string;
  rfq_id: string;
  supplier_id?: string;
  sender_type: "buyer" | "supplier";
  content: string;
  created_at: number;
}

export interface RFQSupplierView {
  supplier: SupplierProfileRead | null;
  latest_quote: QuoteRead | null;
}

// ============ API Helper Types ============

export interface ApiError {
  detail: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}
