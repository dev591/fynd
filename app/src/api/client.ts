/**
 * Crossover API Client — all calls hit the real backend. No localStorage fallback.
 * Backend: http://localhost:8000
 */

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ─── Health ────────────────────────────────────────────────────────────────

export async function healthCheck(): Promise<{ ok: boolean; service: string }> {
  return apiFetch("/health");
}

// ─── Profile ───────────────────────────────────────────────────────────────

export interface ApiProfile {
  id: string;
  role: "buyer" | "supplier";
  full_name: string;
  email: string;
  phone: string;
  company: string;
  business_type: "manufacturer" | "trader" | "distributor" | "other";
  state: string;
  city: string;
  categories: string[];
  gstin?: string;
  pan_masked?: string;
  verification: {
    email: boolean;
    tax_ids_consistent: boolean;
    registry: "none" | "demo" | "live";
  };
  buyer?: { gst_claimable: boolean; spend_band: string; need_by_buffer_days: number };
  supplier?: { default_lead_days: number; gst_inclusive_default: boolean; regions: string[] };
}

export async function createProfile(profile: Omit<ApiProfile, "id"> & { id?: string }): Promise<ApiProfile> {
  return apiFetch("/api/profile", { method: "POST", body: JSON.stringify(profile) });
}

export async function getProfile(id: string): Promise<ApiProfile> {
  return apiFetch(`/api/profile/${id}`);
}

// ─── Tax Validation ────────────────────────────────────────────────────────

export interface TaxValidationResult {
  gstin_valid: boolean;
  pan_consistent: boolean;
  state_code: string;
  pan_masked: string | null;
  errors: string[];
}

export async function validateTax(gstin: string, pan: string): Promise<TaxValidationResult> {
  return apiFetch("/api/validate/tax", { method: "POST", body: JSON.stringify({ gstin, pan }) });
}

// ─── Compare / Engine ─────────────────────────────────────────────────────

export interface CompareResult {
  rows: Array<{
    quote_id: string;
    supplier: string;
    status: string;
    reason: string | null;
    approved: boolean;
    packs: number;
    units: number;
    overbuy: number;
    landed: number | null;
    lead_days: number;
    pack_price: number;
    pack_size: number | null;
    freight: number;
  }>;
  pool: Array<CompareResult["rows"][number]>;
  winner: CompareResult["rows"][number] | null;
  tie: boolean;
  cheaper_excluded: Array<CompareResult["rows"][number]>;
}

export async function compareQuotes(payload: {
  quotes: Array<{
    id: string;
    supplier: string;
    item: string;
    packPrice: number;
    packSize: number | null;
    freight: number;
    leadDays: number;
    moq?: number;
    channel: string;
  }>;
  need: { item: string; qty: number; needInDays: number; gstClaimable: boolean };
}): Promise<CompareResult> {
  return apiFetch("/api/compare", { method: "POST", body: JSON.stringify(payload) });
}

export interface CaseCheck {
  id: string;
  label: string;
  passed: boolean;
  detail: string;
}

export async function getCaseChecks(): Promise<{ checks: CaseCheck[]; score: number; total: number }> {
  return apiFetch("/api/case-checks");
}

// ─── RFQ Lifecycle (Buyer Side) ────────────────────────────────────────────

export interface RFQCreatePayload {
  item: string;
  qty: number;
  need_in_days: number;
  buyer_company: string;
  buyer_name: string;
  buyer_city: string;
  buyer_state: string;
  note?: string;
  priority_mode?: PriorityMode;
  source?: "form" | "chat" | "voice";
}

export type PriorityMode = "cheapest" | "fastest" | "balanced";

export interface QuoteVersionDTO {
  version: number;
  supplier_id: string;
  supplier_name: string;
  pack_price: number;
  pack_size: number;
  freight: number;
  lead_days: number;
  moq?: number;
  max_qty?: number;
  notes?: string;
  origin?: "manual" | "ai_draft_edited" | "ai_draft_sent";
  landed_cost: number;
  units: number;
  packs: number;
  submitted_at: string;
}

export interface NegotiationTargetDTO {
  id: string;
  supplier_id: string;
  message: string;
  cut_needed: number;
  target_freight?: number;
  target_per_unit?: number;
  concession_type: string;
  sent_at: string;
  status: "pending" | "accepted" | "declined";
}

export interface RFQDTO {
  id: string;
  token: string;
  item: string;
  qty: number;
  need_in_days: number;
  buyer_company: string;
  buyer_name: string;
  buyer_city: string;
  buyer_state: string;
  note?: string;
  created_at: string;
  status: "Open" | "Decided" | "Closed";
  decision?: Record<string, unknown> | null;
  priority_mode?: PriorityMode;
  source?: "form" | "chat" | "voice";
  supplier_tokens: Record<string, string>;
}

export interface RFQDetailsDTO {
  rfq: RFQDTO;
  quotes: Record<string, QuoteVersionDTO[]>;
  targets: Record<string, NegotiationTargetDTO>;
  evaluation: CompareResult | null;
  activity?: ActivityDTO;
}

export interface ActivityDTO {
  notified: number;
  viewed: number;
  quoting: number;
  quoted: number;
}

export interface RFQCreateResponse {
  matched?: number;
  id: string;
  token: string;
  supplier_url: string;
  supplier_tokens: Record<string, string>;
  supplier_urls: Record<string, string>;
  rfq: RFQDTO;
}

export async function createRFQ(payload: RFQCreatePayload): Promise<RFQCreateResponse> {
  return apiFetch("/api/rfqs", { method: "POST", body: JSON.stringify(payload) });
}

export async function getRFQs(): Promise<RFQDTO[]> {
  return apiFetch("/api/rfqs");
}

export async function getRFQDetails(id: string): Promise<RFQDetailsDTO> {
  return apiFetch(`/api/rfqs/${id}`);
}

// ─── Buyer intake (chat / voice -> confirm card) ──────────────────────────

export interface IntakeDraftDTO {
  item: string | null;
  qty: number | null;
  need_in_days: number | null;
  need_by_phrase: string | null;
  priority_mode: PriorityMode | null;
  note: string | null;
  catalog_match: boolean;
}

export interface IntakeResultDTO {
  draft: IntakeDraftDTO;
  missing: string[];
  warnings: string[];
  fallback: boolean;
  request_id: string;
}

export async function getIntakeStatus(): Promise<{ ai_enabled: boolean; voice_enabled: boolean }> {
  try {
    return await apiFetch("/api/intake/status");
  } catch {
    return { ai_enabled: false, voice_enabled: false };
  }
}

/** Draft only: nothing is saved. Any failure resolves to a fallback so the manual form takes over. */
export async function draftIntake(text: string): Promise<IntakeResultDTO> {
  try {
    return await apiFetch("/api/intake/draft", { method: "POST", body: JSON.stringify({ text }) });
  } catch {
    return {
      draft: { item: null, qty: null, need_in_days: null, need_by_phrase: null, priority_mode: null, note: null, catalog_match: false },
      missing: ["item", "qty", "need_in_days"], warnings: [], fallback: true, request_id: "",
    };
  }
}

export async function transcribeAudio(blob: Blob): Promise<string | null> {
  try {
    const res = await fetch(`${BASE_URL}/api/intake/transcribe`, {
      method: "POST", headers: { "Content-Type": blob.type || "audio/webm" }, body: blob,
    });
    if (!res.ok) return null;
    const out = await res.json();
    return out.text ?? null;
  } catch {
    return null;
  }
}

export interface ConfirmPayload {
  item: string;
  qty: number;
  need_in_days: number;
  priority_mode: PriorityMode;
  source: "form" | "chat" | "voice";
  buyer_company: string;
  buyer_name: string;
  buyer_city: string;
  buyer_state: string;
  note?: string;
  intake_id?: string;
}

export async function confirmRFQ(payload: ConfirmPayload): Promise<RFQCreateResponse> {
  return apiFetch("/api/rfqs/confirm", { method: "POST", body: JSON.stringify(payload) });
}

// ─── Negotiation Targets ──────────────────────────────────────────────────

export interface TargetPayload {
  supplier_id: string;
  cut_needed: number;
  target_freight?: number;
  target_per_unit?: number;
  concession_type: "freight" | "unit_price";
  message?: string;
}

export async function sendTarget(rfqId: string, target: TargetPayload): Promise<NegotiationTargetDTO> {
  return apiFetch(`/api/rfqs/${rfqId}/targets`, { method: "POST", body: JSON.stringify(target) });
}

export async function lockDecision(rfqId: string, winnerId: string, reason: string, approver: string): Promise<Record<string, unknown>> {
  return apiFetch(`/api/rfqs/${rfqId}/decision`, {
    method: "POST",
    body: JSON.stringify({ winner_id: winnerId, reason, approver }),
  });
}

// ─── Supplier (token-gated) ───────────────────────────────────────────────

export interface SupplierRFQView {
  id: string;
  item: string;
  qty: number;
  need_in_days: number;
  buyer_company: string;
  buyer_name: string;
  buyer_city: string;
  buyer_state: string;
  note?: string;
  status: string;
  supplier_id?: string | null;
  supplier_name?: string;
}

export interface QuoteSubmitPayload {
  supplier_name?: string;
  pack_price: number;
  pack_size: number;
  freight: number;
  lead_days: number;
  moq?: number;
  max_qty?: number;
  notes?: string;
  origin?: "manual" | "ai_draft_edited" | "ai_draft_sent";
}

export async function getRFQByToken(token: string): Promise<SupplierRFQView> {
  return apiFetch(`/api/rfq-by-token/${token}`);
}

export async function submitQuoteByToken(token: string, payload: QuoteSubmitPayload): Promise<QuoteVersionDTO> {
  return apiFetch(`/api/rfq-by-token/${token}/quotes`, { method: "POST", body: JSON.stringify(payload) });
}

export interface DraftQuoteDTO {
  product_id: string;
  product_name: string;
  pack_price: number;
  pack_size: number;
  freight: number;
  lead_days: number;
  moq: number;
  max_qty?: number | null;
  price_break_applied?: number | null;
  verdict: VerdictDTO;
}

/** Quote prefilled from the seller's own catalog row. Null if the seller has no matching row. */
export async function getDraftQuote(token: string): Promise<DraftQuoteDTO | null> {
  try {
    return await apiFetch(`/api/rfq-by-token/${token}/draft`);
  } catch {
    return null;
  }
}

export async function markQuoting(token: string): Promise<void> {
  await fetch(`${BASE_URL}/api/rfq-by-token/${token}/quoting`, { method: "POST" });
}

export interface MyQuotesResponse {
  quotes: QuoteVersionDTO[];
  target: NegotiationTargetDTO | null;
}

export async function getMyQuotes(token: string): Promise<MyQuotesResponse> {
  return apiFetch(`/api/rfq-by-token/${token}/quotes/mine`);
}

// ─── Supplier Profile & Products ──────────────────────────────────────────

export interface SupplierProfileDTO {
  supplier_id: string;
  business_name: string;
  location_city: string;
  location_state: string;
  categories: string[];
  description?: string | null;
  verification_tier: "email" | "tax_ids" | "registry" | "none";
  products: SupplierProductDTO[];
}

export interface SupplierProductDTO {
  id: string;
  name: string;
  category: string;
  pack_price: number;
  pack_size: number;
  moq: number;
  usual_lead_days: number;
  capacity_cap?: number | null;
  unit: string;
  /** Snapshot, not reserved. */
  stock?: number | null;
  freight?: number;
  price_breaks?: Array<{ min_qty: number; pack_price: number }>;
  aliases?: string[];
}

export async function getSupplierProfile(supplierId: string): Promise<SupplierProfileDTO> {
  return apiFetch(`/api/supplier/profile/${supplierId}`);
}

export async function updateSupplierProfile(supplierId: string, payload: {
  business_name: string;
  location_city: string;
  location_state: string;
  categories: string[];
  description?: string;
}): Promise<SupplierProfileDTO> {
  return apiFetch(`/api/supplier/profile/${supplierId}`, { method: "PUT", body: JSON.stringify(payload) });
}

export async function getSupplierProducts(supplierId: string): Promise<SupplierProductDTO[]> {
  return apiFetch(`/api/supplier/products/${supplierId}`);
}

export async function addSupplierProduct(supplierId: string, payload: Omit<SupplierProductDTO, "id">): Promise<SupplierProductDTO> {
  return apiFetch(`/api/supplier/products/${supplierId}`, { method: "POST", body: JSON.stringify(payload) });
}

export async function updateSupplierProduct(supplierId: string, productId: string, payload: Omit<SupplierProductDTO, "id">): Promise<SupplierProductDTO> {
  return apiFetch(`/api/supplier/products/${supplierId}/${productId}`, { method: "PUT", body: JSON.stringify(payload) });
}

export async function deleteSupplierProduct(supplierId: string, productId: string): Promise<void> {
  await apiFetch(`/api/supplier/products/${supplierId}/${productId}`, { method: "DELETE" });
}

// ─── Sellers, matching, inbox ─────────────────────────────────────────────

export interface SellerSummary {
  supplier_id: string;
  business_name: string;
  location_city: string;
  categories: string[];
  synthetic: boolean;
}

export interface VerdictDTO {
  can_fulfil: "yes" | "partly" | "no";
  reasons: string[];
}

export interface NotificationDTO {
  id: string;
  rfq_id: string;
  supplier_id: string;
  status: "new" | "viewed";
  created_at: string;
  item: string;
  qty: number;
  need_in_days: number;
  buyer_company: string;
  buyer_city: string;
  buyer_state: string;
  note?: string | null;
  priority_mode: PriorityMode;
  rfq_status: string;
  token: string;
  quote_url: string;
  product: SupplierProductDTO;
  verdict: VerdictDTO;
  has_quoted: boolean;
}

export async function getSellers(): Promise<SellerSummary[]> {
  return apiFetch("/api/suppliers");
}

export async function getNotifications(supplierId: string): Promise<NotificationDTO[]> {
  return apiFetch(`/api/supplier/${supplierId}/notifications`);
}

export async function markNotificationViewed(supplierId: string, id: string): Promise<NotificationDTO> {
  return apiFetch(`/api/supplier/${supplierId}/notifications/${id}/read`, { method: "POST" });
}

// ─── Buyer-side supplier profile (click-through) ──────────────────────────

export async function getSupplierProfileForBuyer(rfqId: string, supplierId: string): Promise<SupplierProfileDTO> {
  return apiFetch(`/api/rfqs/${rfqId}/suppliers/${supplierId}`);
}

// ─── Chat ──────────────────────────────────────────────────────────────────

export interface ChatMessageDTO {
  id: string;
  sender: "buyer" | "supplier";
  sender_name: string;
  text: string;
  timestamp: string;
  target?: NegotiationTargetDTO | null;
}

export async function getChatMessages(rfqId: string, supplierId: string): Promise<ChatMessageDTO[]> {
  return apiFetch(`/api/rfqs/${rfqId}/threads/${supplierId}/messages`);
}

export async function postChatMessage(rfqId: string, supplierId: string, payload: {
  sender: "buyer" | "supplier";
  sender_name: string;
  text: string;
}): Promise<ChatMessageDTO> {
  return apiFetch(`/api/rfqs/${rfqId}/threads/${supplierId}/messages`, { method: "POST", body: JSON.stringify(payload) });
}

export async function getChatByToken(token: string): Promise<ChatMessageDTO[]> {
  return apiFetch(`/api/rfq-by-token/${token}/messages`);
}

export async function postChatByToken(token: string, payload: {
  sender: "buyer" | "supplier";
  sender_name: string;
  text: string;
}): Promise<ChatMessageDTO> {
  return apiFetch(`/api/rfq-by-token/${token}/messages`, { method: "POST", body: JSON.stringify(payload) });
}

// ─── Connectivity ───────────────────────────────────────────────────────────

export async function isBackendAvailable(): Promise<boolean> {
  try {
    await healthCheck();
    return true;
  } catch {
    return false;
  }
}
