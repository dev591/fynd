/**
 * Crossover API Client — all calls hit the real backend. No localStorage fallback.
 * Backend: same origin in production, port 8000 in dev.
 */

// Production: the API serves this site, so calls go to the same address. Dev: the API on port 8000 of whichever host
// opened the page, so a second laptop on the network works too. VITE_API_URL overrides both.
const BASE_URL = import.meta.env.VITE_API_URL ?? (import.meta.env.PROD ? "" : `http://${window.location.hostname}:8000`);

import { getAccessToken, signOut } from "../lib/auth";

async function authHeader(): Promise<Record<string, string>> {
  const token = await getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(await authHeader()), ...(options?.headers as Record<string, string> | undefined) },
  });
  if (!res.ok) {
    // A rejected token means the session is over: clear it so the page sends you back to sign in.
    if (res.status === 401) await signOut();
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ─── Health ────────────────────────────────────────────────────────────────

export async function healthCheck(): Promise<{ ok: boolean; service: string }> {
  return apiFetch("/health");
}

// ─── Profile and identity ──────────────────────────────────────────────────

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

export interface MeResponse {
  user: { id: string; email: string | null };
  profile: ApiProfile | null;
  /** Roles on this account. The server checks these on every call; the header toggle is only a shortcut. */
  roles: Array<"buyer" | "seller">;
  /** The seller record this user owns, if they hold the seller role. */
  supplier_id: string | null;
}

export type AppRole = "buyer" | "seller";

export async function addRole(role: AppRole): Promise<{ roles: AppRole[]; supplier_id: string | null }> {
  return apiFetch("/api/me/roles", { method: "POST", body: JSON.stringify({ role }) });
}

export async function getMe(): Promise<MeResponse> {
  return apiFetch("/api/me");
}

/** Saves the signed-in user's own profile. The server takes id and email from the login, not from this. */
export async function saveProfile(profile: ApiProfile): Promise<ApiProfile> {
  return apiFetch("/api/profile", { method: "POST", body: JSON.stringify(profile) });
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
  /** Compare ex-GST when true, GST-inclusive when false. Blank = your saved policy. */
  gst_claimable?: boolean;
  /** How long sellers have to quote. Blank = from your priority. */
  window?: WindowKey;
  /** The most you want to spend on this item, delivered, in rupees. Sellers never see it. */
  budget?: number;
  /** Items asked together share one order id, so they can be viewed as one order. */
  order_id?: string;
}

export type PriorityMode = "cheapest" | "fastest" | "balanced";

export interface PriceBreakDTO {
  min_qty: number;
  pack_price: number;
}

export interface QuoteVersionDTO {
  version: number;
  supplier_id: string;
  supplier_name: string;
  pack_price: number;
  pack_size: number | null;
  freight: number;
  lead_days: number;
  moq?: number;
  max_qty?: number;
  notes?: string;
  origin?: "manual" | "ai_draft_edited" | "ai_draft_sent" | "auto";
  /** Brought in by the buyer from a file. Such suppliers have no portal. */
  imported?: boolean;
  item?: string | null;
  tax_rate?: number | null;
  price_includes_tax?: boolean | null;
  /** The pack price actually compared, on the buyer's GST basis. */
  compare_price?: number | null;
  tax_basis?: "stated" | "assumed_exclusive";
  shipping?: "own" | "delhivery" | null;
  shipping_basis?: "delhivery" | "rate_card" | null;
  price_breaks?: PriceBreakDTO[];
  compare_breaks?: PriceBreakDTO[];
  free_freight_above?: number | null;
  compare_free_freight_above?: number | null;
  per_unit_freight?: number | null;
  compare_per_unit_freight?: number | null;
  landed_cost: number | null;
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
  sent_by?: string;
  status: "pending" | "accepted" | "declined";
}

export interface RFQDTO {
  id: string;
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
  /** How many sellers stock this item and were notified. Who they are stays hidden. */
  matched_count: number;
  quote_count: number;
  gst_claimable?: boolean;
  window_key?: WindowKey;
  window_label?: string;
  /** ISO time the quote window closes. After that, new sellers cannot start a quote; quoted ones can still revise. */
  window_ends_at?: string | null;
  window_closed?: boolean;
  /** True when DEMO_WINDOW_MINUTES shortened the window for a demo. */
  demo_timing?: boolean;
  min_quotes?: number;
  budget?: number | null;
  order_id?: string | null;
}

export type WindowKey = "15m" | "today" | "24h" | "3d";

/** What a revealed seller looks like. Present only for sellers this buyer has unlocked. */
export interface SellerIdentity {
  business_name: string;
  contact_name: string | null;
  phone: string | null;
  email: string | null;
  city: string;
  state: string;
  categories: string[];
  description: string | null;
  synthetic: boolean;
  verification_tier: string;
  verification_text: string;
}

export interface SellerBadge {
  verification_tier: string;
  /** Says exactly what was checked, and no more. */
  verification_text: string;
  /** State only. The city stays hidden until reveal. */
  region: string;
  synthetic: boolean;
}

export interface PlanInfo {
  plan: "free" | "pro";
  free_limit: number;
  /** Null on the paid plan (unlimited). */
  reveals_left: number | null;
}

export interface RFQDetailsDTO {
  rfq: RFQDTO;
  /** Keyed by alias ("Seller 1"). */
  quotes: Record<string, QuoteVersionDTO[]>;
  targets: Record<string, NegotiationTargetDTO>;
  evaluation: CompareResult | null;
  activity?: ActivityDTO;
  revealed: Record<string, SellerIdentity>;
  /** Gates a person broke on purpose: alias -> written reason and named approver. */
  exceptions: Record<string, { reason: string; approver: string }>;
  badges: Record<string, SellerBadge>;
  plan: PlanInfo;
}

export interface ActivityDTO {
  notified: number;
  viewed: number;
  quoting: number;
  quoted: number;
  declined: number;
}

export interface RFQCreateResponse {
  id: string;
  matched: number;
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
      method: "POST", headers: { "Content-Type": blob.type || "audio/webm", ...(await authHeader()) }, body: blob,
    });
    if (!res.ok) return null;
    const out = await res.json();
    return out.text ?? null;
  } catch {
    return null;
  }
}

/** Seller-side STT: same ElevenLabs pipeline, separate endpoint that requires the seller role. */
export async function transcribeSellerAudio(blob: Blob): Promise<string | null> {
  try {
    const res = await fetch(`${BASE_URL}/api/supplier/transcribe`, {
      method: "POST", headers: { "Content-Type": blob.type || "audio/webm", ...(await authHeader()) }, body: blob,
    });
    if (!res.ok) return null;
    const out = await res.json();
    return out.text ?? null;
  } catch {
    return null;
  }
}

export interface VoiceQuoteDraftRow {
  pack_price: number | null;
  pack_size: number | null;
  freight: number | null;
  lead_days: number | null;
  moq: number | null;
  max_qty: number | null;
  tax_rate: number | null;
  price_includes_tax: boolean | null;
  notes: string | null;
}

export interface VoiceQuoteDraftResult {
  rows: VoiceQuoteDraftRow[];
  warnings: string[];
  fallback: boolean;
}

/**
 * Parse a seller's spoken sentence into quote fields.
 * Every number is cross-checked against the source text; invented values are dropped.
 * Returns the first row (single quote sentence) or null on failure.
 */
export async function draftQuoteFromVoice(text: string): Promise<VoiceQuoteDraftResult | null> {
  try {
    return await apiFetch("/api/quote-voice/draft", { method: "POST", body: JSON.stringify({ text }) });
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
  window?: WindowKey;
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

// ─── Decision one-pager, savings, share ───────────────────────────────────

export interface SummaryRowDTO {
  quote_id: string;
  supplier: string;
  status: "eligible" | "exception" | "blocked";
  reason: string | null;
  approved: boolean;
  landed: number | null;
  lead_days: number;
  packs: number;
  units: number;
  overbuy: number;
  freight: number;
  fill_qty: number | null;
  pack_price: number;
  pack_size: number | null;
  /** Derived: extra units bought because of pack rounding or the minimum order, at their unit price. */
  cash_tied_up: number | null;
  /** Derived: landed cost over the units you actually need. */
  cost_per_usable_unit: number | null;
}

export interface EvidenceFact {
  label: string;
  value: string;
  tag: "observed" | "assumed" | "derived";
  source: string;
}

export interface SummaryDTO {
  rfq: {
    id: string; item: string; qty: number; need_in_days: number; buyer_company?: string; buyer_name?: string;
    priority_mode: PriorityMode; source: string; status: string; created_at: string;
  };
  decided: boolean;
  decision: { winner_id: string; reason: string; approver: string; decided_at: string; payment_note?: string } | null;
  pick: SummaryRowDTO | null;
  engine_winner: SummaryRowDTO | null;
  overrode_engine: boolean;
  winners_by_mode: Record<string, SummaryRowDTO | null>;
  rows: SummaryRowDTO[];
  cheaper_excluded: SummaryRowDTO[];
  reasons: string[];
  delivery: DeliveryDTO | null;
  evidence: EvidenceFact[];
  tradeoffs: Record<string, { extra_cost: number | null; days_saved: number | null; line: string | null }>;
  exceptions: Record<string, { reason: string; approver: string }>;
  explainer: { text: string; source: "ai" | "engine"; discarded_reason: string | null } | null;
  ai_opinion?: AiOpinionDTO | null;
  split?: SplitPlanDTO | null;
  savings: {
    spreadsheet_pick: string; spreadsheet_landed: number; crossover_pick: string;
    crossover_landed: number; difference: number; label: string;
  } | null;
  fingerprint: string;
  ai_calls: Array<{ request_id: string; kind: string; at: string }>;
  /** Suppliers whose current quote was sent by autopilot with no one reviewing it. */
  auto_quotes: string[];
  /** Sellers this buyer has unlocked. Always empty on a shared link. */
  revealed: Record<string, SellerIdentity>;
  synthetic_note: string;
}

export interface SplitPartDTO {
  quote_id: string;
  qty: number;
  packs: number;
  units: number;
  landed: number;
  lead_days: number;
}

export interface SplitPlanDTO {
  parts: SplitPartDTO[];
  total_landed: number;
  lead_days: number;
  units: number;
  overbuy: number;
  best_single: { quote_id: string; landed: number } | null;
  saving: number | null;
  reason: "cheaper_than_best_single" | "no_single_supplier_can_fill";
}

/** The best two-seller split, or null when one seller already wins alone. Aliases only. */
export async function getSplitOptions(rfqId: string): Promise<SplitPlanDTO | null> {
  return (await apiFetch<{ plan: SplitPlanDTO | null }>(`/api/rfqs/${rfqId}/split-options`)).plan;
}

/** Order the server's own split. Quantities are never sent: the server uses its plan, and both sellers must be revealed. */
export async function lockSplitDecision(rfqId: string, primaryAlias: string, reason: string, approver: string): Promise<Record<string, unknown>> {
  return apiFetch(`/api/rfqs/${rfqId}/decision`, {
    method: "POST",
    body: JSON.stringify({ winner_id: primaryAlias, reason, approver, split: true }),
  });
}

export interface AskDeskDTO {
  understood: boolean;
  scenario: { qty: number | null; need_in_days: number | null; priority: PriorityMode | null; exclude: string[] };
  baseline: { winner: string; landed: number; lead_days: number } | null;
  result: { winner: string | null; landed: number | null; lead_days: number | null;
            rows: { quote_id: string; landed: number | null; lead_days: number; status: string; reason: string | null }[] } | null;
  changed: boolean;
  sentence: string;
}

/** A what-if question about this request's quotes. The engine recomputes; nothing is saved. */
export async function askTheDesk(rfqId: string, question: string): Promise<AskDeskDTO> {
  return apiFetch(`/api/rfqs/${rfqId}/ask`, { method: "POST", body: JSON.stringify({ question }) });
}

export interface DeskSuggestionDTO {
  kind: "deadline" | "quantity" | "split" | "negotiate" | "priority";
  headline: string;
  /** The what-if to run when the buyer clicks it. Null for ideas handled elsewhere on the page. */
  question: string | null;
  saving: number | null;
}

/** What the buyer could do for a better outcome, worked out by the engine. */
export async function getDeskSuggestions(rfqId: string): Promise<DeskSuggestionDTO[]> {
  return (await apiFetch<{ suggestions: DeskSuggestionDTO[] }>(`/api/rfqs/${rfqId}/suggestions`)).suggestions;
}

export interface FinePrintFlagDTO { kind: string; phrase: string; label: string }

/** Terms hidden in each quote's notes, by alias. Warnings only; they never change a price or a winner. */
export async function getFinePrint(rfqId: string): Promise<Record<string, FinePrintFlagDTO[]>> {
  return (await apiFetch<{ flags: Record<string, FinePrintFlagDTO[]> }>(`/api/rfqs/${rfqId}/fine-print`)).flags;
}

export interface LogEventDTO { id: string; at: string; kind: string; text: string }

/** What happened on a request, oldest first. Sellers appear by alias until revealed. */
export async function getRequestLog(rfqId: string): Promise<LogEventDTO[]> {
  return (await apiFetch<{ events: LogEventDTO[] }>(`/api/rfqs/${rfqId}/log`)).events;
}

/** The seller's own side of a request's history, from their quote link. */
export async function getSellerRequestLog(token: string): Promise<LogEventDTO[]> {
  return (await apiFetch<{ events: LogEventDTO[] }>(`/api/rfq-by-token/${token}/log`)).events;
}

export interface RequestEdit { qty?: number; need_in_days?: number; note?: string; priority_mode?: PriorityMode }

/** Change an open request. Sellers are told to check their quotes. */
export async function editRequest(rfqId: string, edit: RequestEdit): Promise<RFQDTO> {
  return apiFetch(`/api/rfqs/${rfqId}`, { method: "PATCH", body: JSON.stringify(edit) });
}

export interface BuyerOrderDTO {
  rfq_id: string; item: string; qty: number; decided_at: string | null; total_landed: number | null;
  approver: string | null; reason: string | null; split: boolean; status: string;
  receivers: { alias: string; units: number; total: number | null; business_name?: string | null; contact_name?: string | null;
               phone?: string | null; email?: string | null; city?: string | null; state?: string | null }[];
}

/** Order history: every decided request with the seller who receives the order. */
export async function getOrders(): Promise<BuyerOrderDTO[]> {
  return (await apiFetch<{ orders: BuyerOrderDTO[] }>("/api/orders")).orders;
}

export interface SellerOrderDTO {
  rfq_id: string; item: string; qty: number; total: number | null; decided_at: string | null; status: string; split: boolean;
  payment: string | null; buyer: { name?: string; company?: string; phone?: string | null; email?: string | null; city?: string | null };
}

/** Orders this seller won, with the buyer's contact. */
export async function getSellerOrders(supplierId: string): Promise<SellerOrderDTO[]> {
  return (await apiFetch<{ orders: SellerOrderDTO[] }>(`/api/supplier/${supplierId}/orders`)).orders;
}

export interface AiOpinionDTO {
  pick: string;
  agrees: boolean;
  engine_pick: string;
  reason: string;
  source: "ai";
  label: string;
}

/** The AI's reading of the current quotes. Null with no AI key, nothing to weigh, or text that failed the checks. */
export interface DemoLoginsDTO {
  enabled: boolean;
  password?: string;
  sellers: { email: string; company: string; city: string; items: string[] }[];
}

/** Ten demo seller accounts for one-click sign-in. Disabled (empty) unless the server turns it on for a local demo. */
export async function getDemoLogins(): Promise<DemoLoginsDTO> {
  return apiFetch("/api/demo/logins");
}

export async function getAiOpinion(rfqId: string): Promise<AiOpinionDTO | null> {
  const s = await apiFetch<SummaryDTO>(`/api/rfqs/${rfqId}/summary`);
  return s.ai_opinion ?? null;
}

export async function getSummary(rfqId: string): Promise<SummaryDTO> {
  return apiFetch(`/api/rfqs/${rfqId}/summary`);
}

export async function getSharedSummary(token: string): Promise<SummaryDTO> {
  return apiFetch(`/api/share/${token}`);
}

export async function createShareLink(rfqId: string): Promise<{ token: string; url: string }> {
  return apiFetch(`/api/rfqs/${rfqId}/share`, { method: "POST" });
}

export async function getSavings(): Promise<{ total: number; decided_count: number; label: string }> {
  return apiFetch("/api/savings");
}

// ─── Negotiation Targets ──────────────────────────────────────────────────

export interface TargetPayload {
  supplier_id: string;
  cut_needed: number;
  target_freight?: number;
  target_per_unit?: number;
  concession_type: "freight" | "unit_price";
  message?: string;
  /** The person sending it. Targets are never sent by the system. */
  sent_by: string;
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

export interface BuyerContact {
  name: string;
  company: string;
  phone: string | null;
  email: string | null;
  city: string;
}

export interface SupplierRFQView {
  id: string;
  item: string;
  qty: number;
  need_in_days: number;
  /** Kind of business and state, like "Manufacturer, Telangana". Never a name, company or city. */
  buyer_descriptor: string;
  priority_mode?: PriorityMode;
  unlocked: boolean;
  closes_at?: string | null;
  window_closed?: boolean;
  /** Present only after the buyer has unlocked this seller. */
  buyer_contact?: BuyerContact;
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
  origin?: "manual" | "ai_draft_edited" | "ai_draft_sent" | "auto";
  tax_rate?: number;
  price_includes_tax?: boolean;
  shipping?: "own" | "delhivery";
  shipping_basis?: "delhivery" | "rate_card";
  price_breaks?: PriceBreakDTO[];
  free_freight_above?: number;
  per_unit_freight?: number;
}

export interface ShippingEstimate {
  freight: number;
  lead_days: number;
  zone: string | null;
  basis: "delhivery" | "rate_card";
  label: string;
}

/** Freight and delivery days for a seller's shipping choice. A suggestion only; the seller applies and may edit it. */
export async function estimateShipping(token: string, weightKg: number): Promise<ShippingEstimate> {
  return apiFetch(`/api/rfq-by-token/${token}/shipping-estimate`, { method: "POST", body: JSON.stringify({ weight_kg: weightKg }) });
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
  price_breaks?: PriceBreakDTO[];
  free_freight_above?: number | null;
  per_unit_freight?: number | null;
  tax_rate?: number | null;
  price_includes_tax?: boolean | null;
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

export interface AssistDTO {
  draft: DraftQuoteDTO;
  message: {
    text: string;
    /** "ai" only if every number in the text matched your data; otherwise the plain template. */
    source: "ai" | "template";
    discarded_reason: string | null;
  };
}

export async function getAssist(token: string): Promise<AssistDTO | null> {
  try {
    return await apiFetch(`/api/rfq-by-token/${token}/assist`);
  } catch {
    return null;
  }
}

export interface ItemMatchDTO {
  verdict: "same" | "different" | "unsure";
  reason: string;
  source: "rules" | "ai" | "none";
}

/** Warn only. Any failure means no check is shown. */
export async function checkItemMatch(token: string, productId: string): Promise<ItemMatchDTO | null> {
  try {
    return await apiFetch(`/api/rfq-by-token/${token}/item-match`, { method: "POST", body: JSON.stringify({ product_id: productId }) });
  } catch {
    return null;
  }
}

/** "Can't supply" is an answer: the buyer's activity strip counts it. The reason stays with you. */
export async function declineRequest(token: string, reason?: string): Promise<void> {
  await apiFetch(`/api/rfq-by-token/${token}/decline`, { method: "POST", body: JSON.stringify({ reason: reason || null }) });
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
  free_freight_above?: number | null;
  per_unit_freight?: number | null;
  tax_rate?: number | null;
  price_includes_tax?: boolean | null;
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
  status: "new" | "viewed" | "quoting" | "declined";
  created_at: string;
  item: string;
  qty: number;
  need_in_days: number;
  buyer_descriptor: string;
  unlocked: boolean;
  buyer_contact?: BuyerContact | null;
  note?: string | null;
  priority_mode: PriorityMode;
  reminder?: string | null;
  closes_at?: string | null;
  window_closed?: boolean;
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

export async function getAutopilot(supplierId: string): Promise<{ enabled: boolean }> {
  return apiFetch(`/api/supplier/${supplierId}/autopilot`);
}

export async function setAutopilot(supplierId: string, enabled: boolean): Promise<{ enabled: boolean }> {
  return apiFetch(`/api/supplier/${supplierId}/autopilot`, { method: "PUT", body: JSON.stringify({ enabled }) });
}

// ─── Buyer-side supplier profile (click-through) ──────────────────────────

/** The click-through panel. Before a reveal: alias, state and what was checked. After: the seller. */
export interface SellerPanelDTO {
  supplier_id: string;
  business_name: string;
  location_city: string;
  location_state: string;
  categories: string[];
  description: string | null;
  products: SupplierProductDTO[];
  revealed: boolean;
  verification_tier: string;
  verification_text: string;
  synthetic: boolean;
  contact?: { contact_name: string | null; phone: string | null; email: string | null };
}

export async function getSupplierProfileForBuyer(rfqId: string, alias: string): Promise<SellerPanelDTO> {
  return apiFetch(`/api/rfqs/${rfqId}/suppliers/${encodeURIComponent(alias)}`);
}

// ─── Reveal, plan, sample request ──────────────────────────────────────────

export interface RevealResult {
  alias: string;
  /** free = used one of your free reveals; paid = on the paid plan; repeat = a seller you had already unlocked. */
  kind: "free" | "paid" | "repeat" | "already";
  seller: SellerIdentity;
  plan: PlanInfo;
}

export class RevealsExhausted extends Error {
  plan: PlanInfo;
  constructor(plan: PlanInfo) {
    super("You have used your free reveals.");
    this.plan = plan;
  }
}

export async function revealSeller(rfqId: string, alias: string): Promise<RevealResult> {
  const res = await fetch(`${BASE_URL}/api/rfqs/${rfqId}/quotes/${encodeURIComponent(alias)}/reveal`, {
    method: "POST", headers: { "Content-Type": "application/json", ...(await authHeader()) },
  });
  if (res.status === 402) throw new RevealsExhausted(await res.json());
  if (res.status === 401) await signOut();
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
  return res.json();
}

export async function recordException(rfqId: string, alias: string, reason: string, approver: string) {
  return apiFetch<{ exceptions: Record<string, { reason: string; approver: string }> }>(
    `/api/rfqs/${rfqId}/exceptions`, { method: "POST", body: JSON.stringify({ alias, reason, approver }) });
}

export async function withdrawException(rfqId: string, alias: string) {
  return apiFetch<{ exceptions: Record<string, { reason: string; approver: string }> }>(
    `/api/rfqs/${rfqId}/exceptions/${encodeURIComponent(alias)}`, { method: "DELETE" });
}

export interface ImportResult {
  imported: number;
  skipped_rows: number;
  errors: Array<{ row: number; field: string; message: string }>;
  suppliers: string[];
}

/** Bad rows come back by row number; good rows are already loaded. A rejected file throws with the reason. */
export async function importQuotes(rfqId: string, format: "csv" | "json", data: string): Promise<ImportResult> {
  return apiFetch(`/api/rfqs/${rfqId}/import-quotes`, { method: "POST", body: JSON.stringify({ format, data }) });
}

export interface QuoteDraftRow {
  supplier: string | null;
  item: string | null;
  pack_size: number | null;
  pack_price: number | null;
  freight: number | null;
  lead_days: number | null;
  moq: number | null;
  max_qty: number | null;
  tax_rate: number | null;
  price_includes_tax: boolean | null;
  notes: string | null;
}

/** Reads a pasted supplier message into rows for the buyer to check. Saves nothing. Any failure resolves to a fallback. */
export async function draftQuotesFromMessage(text: string, rfqId?: string): Promise<{
  rows: QuoteDraftRow[]; warnings: string[]; fallback: boolean; message?: string; request_id: string;
}> {
  try {
    return await apiFetch("/api/ai/quote-draft", { method: "POST", body: JSON.stringify({ text, rfq_id: rfqId }) });
  } catch {
    return { rows: [], warnings: [], fallback: true, message: "Couldn't read that automatically. Use the CSV or JSON import.", request_id: "" };
  }
}

export async function getImportTemplate(): Promise<{ csv: string; json: string; required_columns: string[] }> {
  return apiFetch("/api/import-template");
}

export interface BuyerNoticeDTO {
  id: string;
  rfq_id: string;
  kind: "first_quote" | "enough_quotes" | "window_closed";
  message: string;
  created_at: string;
  read: boolean;
}

export async function getNotices(): Promise<{ notices: BuyerNoticeDTO[]; unread: number }> {
  return apiFetch("/api/me/notices");
}

export async function readNotice(id: string): Promise<{ unread: number }> {
  return apiFetch(`/api/me/notices/${id}/read`, { method: "POST" });
}

export async function readAllNotices(): Promise<{ unread: number }> {
  return apiFetch("/api/me/notices/read-all", { method: "POST" });
}

export interface DeliveryDTO {
  matches_quote: boolean;
  on_time: boolean;
  note?: string | null;
  recorded_at: string;
  media?: { name: string; mime: string; bytes: number } | null;
  disclaimer?: string;
}

export async function recordDelivery(rfqId: string, d: {
  matches_quote: boolean; on_time: boolean; note?: string; media?: { name: string; mime: string; data: string };
}): Promise<{ delivery: DeliveryDTO }> {
  return apiFetch(`/api/rfqs/${rfqId}/delivery`, { method: "POST", body: JSON.stringify(d) });
}

export async function getPlan(): Promise<PlanInfo> {
  return apiFetch("/api/me/plan");
}

/** DEV ONLY: flips the account to unlimited reveals. No payment happens. */
export async function mockUpgrade(): Promise<PlanInfo & { note: string }> {
  return apiFetch("/api/dev/mock-upgrade", { method: "POST" });
}

export interface LastOrderDTO {
  item: string;
  qty: number;
  last: { source: "your_last_order" | "synthetic_history"; label: string; date: string; qty: number; landed: number; lead_days: number } | null;
  today: { landed: number; lead_days: number; sellers_checked: number } | null;
  /** Last landed cost minus today's best for the same quantity. Null when they cannot be compared. */
  difference: number | null;
  note: string;
}

export async function getLastOrder(item: string, qty?: number, needInDays?: number): Promise<LastOrderDTO> {
  const q = new URLSearchParams();
  if (qty) q.set("qty", String(qty));
  if (needInDays) q.set("need_in_days", String(needInDays));
  return apiFetch(`/api/items/${encodeURIComponent(item)}/last-order?${q}`);
}

export async function createSampleRequest(): Promise<RFQCreateResponse> {
  return apiFetch("/api/demo/sample-request", { method: "POST" });
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
  return apiFetch(`/api/rfqs/${rfqId}/threads/${encodeURIComponent(supplierId)}/messages`);
}

export async function postChatMessage(rfqId: string, supplierId: string, payload: {
  sender: "buyer" | "supplier";
  sender_name: string;
  text: string;
}): Promise<ChatMessageDTO> {
  return apiFetch(`/api/rfqs/${rfqId}/threads/${encodeURIComponent(supplierId)}/messages`, { method: "POST", body: JSON.stringify(payload) });
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
