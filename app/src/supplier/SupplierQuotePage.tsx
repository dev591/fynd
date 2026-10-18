import { useState, useMemo, useRef } from "react";
import { Ambient } from "../components/Ambient";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArrowLeft, Building2, Clock, History, RotateCcw, MessageSquare,
  Share2, AlertTriangle, CheckCircle2, XCircle,
} from "lucide-react";
import { QuoteForm } from "./components/QuoteForm";
import { StatusChip } from "./components/StatusChip";
import { NegotiationTargetCard } from "./components/NegotiationTargetCard";
import { SupplierChat } from "./components/SupplierChat";
import { Money } from "./components/Money";
import { useApiPoll, useApiOnce } from "../lib/useApi";
import {
  getRFQByToken, getMyQuotes, submitQuoteByToken, estimateShipping,
  getChatByToken, postChatByToken,
  getSupplierProducts, getAssist, checkItemMatch, markQuoting, declineRequest,
  type SupplierRFQView, type QuoteVersionDTO, type NegotiationTargetDTO,
  type ChatMessageDTO, type SupplierProductDTO,
} from "../api/client";
import { computeStatus } from "./types";

export function SupplierQuotePage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") || "";

  // Poll RFQ view every 2s
  const { data: rfq, loading, error } = useApiPoll<SupplierRFQView>(
    () => token ? getRFQByToken(token) : Promise.reject(new Error("No token")),
    2000,
    [token],
  );

  // Poll quotes + target
  const { data: myData, refetch: refetchMine } = useApiPoll<{
    quotes: QuoteVersionDTO[]; target: NegotiationTargetDTO | null;
  }>(
    () => token ? getMyQuotes(token) : Promise.resolve({ quotes: [], target: null }),
    2000,
    [token],
  );

  // Poll chat
  const { data: chatMessages, refetch: refetchChat } = useApiPoll<ChatMessageDTO[]>(
    () => token ? getChatByToken(token) : Promise.resolve([]),
    2000,
    [token],
  );

  // Supplier products (one-time load)
  const { data: products } = useApiPoll<SupplierProductDTO[]>(
    () => rfq?.supplier_id ? getSupplierProducts(rfq.supplier_id) : Promise.resolve([]),
    5000, [rfq?.supplier_id],
  );
  const sellerName = rfq?.supplier_name || "Supplier";

  // Catalog draft: every number copied from the seller's own row, editable before sending
  const { data: assist } = useApiOnce(
    () => token ? getAssist(token) : Promise.resolve(null),
    [token],
  );
  const draft = assist?.draft ?? null;
  const quotingSent = useRef(false);
  const handleFirstEdit = () => {
    if (quotingSent.current || !token) return;
    quotingSent.current = true;
    markQuoting(token).catch(() => { quotingSent.current = false; });
  };

  const [activeTab, setActiveTab] = useState<"quote" | "chat">("quote");
  const [isRevising, setIsRevising] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [declined, setDeclined] = useState(false);
  const [declineBusy, setDeclineBusy] = useState(false);

  const quotes = myData?.quotes || [];
  const target = myData?.target || null;
  const latestQuote: QuoteVersionDTO | null = quotes.length > 0 ? quotes[quotes.length - 1] : null;

  // Compute supplier status from real data
  const status = useMemo(() => {
    if (!rfq) return "received" as const;
    return computeStatus(quotes.length > 0, target?.status || null, rfq.status, false);
  }, [rfq, quotes.length, target]);

  // Form initial values
  const formInitialValues = useMemo(() => {
    if (target && target.status === "pending") {
      return {
        packPrice: latestQuote?.pack_price ?? 10,
        packSize: latestQuote?.pack_size ?? 1,
        freight: target.target_freight ?? (latestQuote?.freight ?? 150),
        leadDays: latestQuote?.lead_days ?? 3,
        moq: latestQuote?.moq ?? 1,
        maxQty: latestQuote?.max_qty,
        notes: `Revised to match buyer counter-offer: ${target.message}`,
        priceBreaks: latestQuote?.price_breaks,
        freeFreightAbove: latestQuote?.free_freight_above ?? undefined,
        perUnitFreight: latestQuote?.per_unit_freight ?? undefined,
      };
    }
    if (latestQuote) {
      return {
        packPrice: latestQuote.pack_price,
        packSize: latestQuote.pack_size ?? undefined,
        freight: latestQuote.freight,
        leadDays: latestQuote.lead_days,
        moq: latestQuote.moq,
        maxQty: latestQuote.max_qty,
        priceBreaks: latestQuote.price_breaks,
        freeFreightAbove: latestQuote.free_freight_above ?? undefined,
        perUnitFreight: latestQuote.per_unit_freight ?? undefined,
        notes: latestQuote.notes,
      };
    }
    if (draft) {
      return {
        packPrice: draft.pack_price,
        packSize: draft.pack_size,
        freight: draft.freight,
        leadDays: draft.lead_days,
        moq: draft.moq,
        maxQty: draft.max_qty ?? undefined,
        taxRate: draft.tax_rate ?? undefined,
        priceIncludesTax: draft.price_includes_tax ?? undefined,
        priceBreaks: draft.price_breaks,
        freeFreightAbove: draft.free_freight_above ?? undefined,
        perUnitFreight: draft.per_unit_freight ?? undefined,
        notes: assist?.message.text,
      };
    }
    return undefined;
  }, [latestQuote, target, draft, assist]);

  const handleQuoteSubmit = async (data: {
    packPrice: number; packSize: number; freight: number; leadDays: number;
    moq?: number; maxQty?: number; taxRate?: number; priceIncludesTax?: boolean; notes?: string;
    shipping?: "own" | "delhivery"; shippingBasis?: "delhivery" | "rate_card"; priceBreaks?: { min_qty: number; pack_price: number }[]; freeFreightAbove?: number; perUnitFreight?: number;
  }) => {
    setSubmitting(true);
    setSubmitError(null);
    try {
      await submitQuoteByToken(token, {
        supplier_name: sellerName,
        pack_price: data.packPrice,
        pack_size: data.packSize,
        freight: data.freight,
        lead_days: data.leadDays,
        moq: data.moq,
        max_qty: data.maxQty,
        notes: data.notes,
        tax_rate: data.taxRate,
        price_includes_tax: data.priceIncludesTax,
        shipping: data.shipping,
        shipping_basis: data.shippingBasis,
        price_breaks: data.priceBreaks,
        free_freight_above: data.freeFreightAbove,
        per_unit_freight: data.perUnitFreight,
      });
      setIsRevising(false);
      refetchMine();
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : "Failed to submit quote");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDecline = async () => {
    setDeclineBusy(true);
    try { await declineRequest(token); setDeclined(true); }
    catch (e) { setSubmitError(e instanceof Error ? e.message : "Could not send your answer."); }
    finally { setDeclineBusy(false); }
  };

  const handleCopyLink = () => {
    navigator.clipboard?.writeText(window.location.href);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2000);
  };

  const handleSendMessage = async (text: string) => {
    try {
      await postChatByToken(token, {
        sender: "supplier",
        sender_name: sellerName,
        text,
      });
      refetchChat();
    } catch (e) {
      console.error("Failed to send message:", e);
    }
  };

  // ─── States ─────────────────────────────────────────────────────────

  if (!token) {
    return (
      <div className="landing grain isolate min-h-screen bg-ink text-bone flex items-center justify-center">
      <Ambient />
        <div className="max-w-md text-center space-y-3">
          <AlertTriangle size={28} className="mx-auto text-warn" />
          <h2 className="display text-lg text-bone">No token provided</h2>
          <p className="text-[13px] text-muted">This link is missing the supplier token. Ask the buyer for a fresh invite link.</p>
          <Link to="/supplier" className="inline-block rounded-full bg-signal px-4 py-2 text-[13px] text-ink">Go to Supplier Portal</Link>
        </div>
      </div>
    );
  }

  if (loading && !rfq) {
    return (
      <div className="landing grain isolate min-h-screen bg-ink text-bone flex items-center justify-center">
      <Ambient />
        <div className="text-center space-y-3">
          <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-line border-t-signal" />
          <p className="text-[13px] text-muted">Loading request…</p>
        </div>
      </div>
    );
  }

  if (error && !rfq) {
    return (
      <div className="landing grain isolate min-h-screen bg-ink text-bone flex items-center justify-center">
      <Ambient />
        <div className="max-w-md rounded-2xl border border-error/40 bg-error/10 p-6 text-center space-y-3">
          <XCircle size={28} className="mx-auto text-error" />
          <h2 className="display text-lg text-bone">This link isn't valid</h2>
          <p className="text-[13px] text-muted">The link may have expired or the request may be closed. Contact the buyer for a new link.</p>
        </div>
      </div>
    );
  }

  if (!rfq) return null;

  const isClosed = rfq.status === "Decided" || rfq.status === "Closed";

  return (
    <div className="landing grain isolate min-h-screen bg-ink text-bone pb-16">
      <Ambient />
      {/* Top Bar */}
      <header className="sticky top-0 z-30 border-b border-line bg-ink/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2.5">
            <Link to="/supplier" className="flex items-center gap-1 text-[13px] text-muted hover:text-bone">
              <ArrowLeft size={14} /><span className="hidden sm:inline">Supplier Portal</span>
            </Link>
            <span className="text-muted/50">·</span>
            <span className="label text-signal">SUPPLIER QUOTE DESK</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleCopyLink}
              className="flex items-center gap-1.5 rounded-full border border-line bg-surface px-2.5 py-1 text-[11px] text-muted hover:text-bone"
            >
              <Share2 size={12} /><span>{copiedLink ? "Copied!" : "Share Link"}</span>
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-6 space-y-6">
        {/* Request Header */}
        <div className="rounded-2xl border border-line bg-surface/90 p-5 shadow-sm backdrop-blur-md">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-2 text-[12px] text-muted">
                <Building2 size={13} className="text-signal" />
                <span className="font-semibold text-bone">{rfq.buyer_descriptor}</span>
              </div>
              <h1 className="display text-2xl text-bone mt-1.5">
                Request: <span className="text-signal">{rfq.item}</span>
              </h1>
            </div>
            <span className={`rounded-full px-3 py-1 text-[12px] font-semibold shrink-0 ${
              isClosed ? "border border-line bg-raised text-muted" : "border border-signal/30 bg-signal/15 text-signal"
            }`}>
              {rfq.status}
            </span>
          </div>

          <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 gap-3 border-t border-line/60 pt-3 text-[13px]">
            <div>
              <span className="label text-muted block">Quantity</span>
              <span className="num text-base font-bold text-bone">{rfq.qty} units</span>
            </div>
            <div>
              <span className="label text-muted block">Delivery</span>
              <span className="num text-base font-bold text-bone">Within {rfq.need_in_days} days</span>
            </div>
            <div className="col-span-2 sm:col-span-1">
              <span className="label text-muted block">Buyer contact</span>
              {rfq.unlocked && rfq.buyer_contact ? (
                <span className="font-medium text-bone">
                  {rfq.buyer_contact.name}, {rfq.buyer_contact.company}
                  {rfq.buyer_contact.phone ? ` · ${rfq.buyer_contact.phone}` : ""}
                  {rfq.buyer_contact.email ? ` · ${rfq.buyer_contact.email}` : ""}
                </span>
              ) : (
                <span className="text-muted">Shared when the buyer unlocks you</span>
              )}
            </div>
          </div>

          {rfq.note && (
            <p className="mt-3 rounded-lg border border-line/60 bg-raised/30 p-2.5 text-[12px] text-muted leading-relaxed">
              <strong>Buyer Note:</strong> "{rfq.note}"
            </p>
          )}
        </div>

        {/* Read-only banner if closed */}
        {isClosed && (
          <div className="rounded-xl border border-line bg-raised/30 p-4 text-center text-[13px] text-muted">
            <CheckCircle2 size={20} className="mx-auto text-muted mb-1" />
            This request is {rfq.status}. No further revisions accepted.
          </div>
        )}

        {/* Tabs */}
        <div className="flex border-b border-line gap-4 text-[13px] font-medium">
          <button
            type="button"
            onClick={() => setActiveTab("quote")}
            className={`pb-2.5 transition-colors border-b-2 flex items-center gap-1.5 ${
              activeTab === "quote" ? "border-signal text-bone font-semibold" : "border-transparent text-muted hover:text-bone"
            }`}
          >
            <span>Quote Submission</span>
            {latestQuote && <span className="rounded bg-raised px-1.5 py-0.2 text-[10px] text-muted">v{latestQuote.version}</span>}
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("chat")}
            className={`pb-2.5 transition-colors border-b-2 flex items-center gap-1.5 ${
              activeTab === "chat" ? "border-signal text-bone font-semibold" : "border-transparent text-muted hover:text-bone"
            }`}
          >
            <MessageSquare size={14} /><span>Negotiation Thread</span>
            {(chatMessages?.length || 0) > 0 && (
              <span className="rounded-full bg-signal text-ink px-1.5 py-0.2 text-[10px] font-bold">
                {chatMessages!.length}
              </span>
            )}
          </button>
        </div>

        {rfq.window_closed && !latestQuote && !isClosed && (
          <div role="status" className="rounded-xl border border-line bg-raised/40 p-4 text-center text-[13px] text-muted">
            The quote window for this request has closed, so new quotes are not being accepted.
          </div>
        )}
        {!isClosed && !latestQuote && !rfq.window_closed && (
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-line bg-surface/60 px-4 py-2.5 text-[13px]">
            {declined ? (
              <span className="text-muted">You told the buyer you can't supply this. You can still send a quote below if that changes.</span>
            ) : (
              <>
                <span className="text-muted">Not something you can supply right now?</span>
                <button type="button" onClick={handleDecline} disabled={declineBusy}
                  className="rounded-full border border-line bg-raised px-3 py-1 text-[12px] font-medium text-bone hover:border-signal/50 disabled:opacity-40">
                  {declineBusy ? "Sending…" : "I can't supply this"}
                </button>
              </>
            )}
          </div>
        )}

        {/* Tab 1: Quote */}
        {activeTab === "quote" && (
          <div className="space-y-6">
            {latestQuote && !isRevising && !isClosed ? (
              <div className="space-y-5">
                {/* Status Card */}
                <div className="rounded-2xl border border-line bg-surface/90 p-5 shadow-sm">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-line/60">
                    <div>
                      <p className="label text-muted">Quote Status</p>
                      <h3 className="display text-xl text-bone mt-0.5">Version {latestQuote.version} Active</h3>
                    </div>
                    <StatusChip status={status} />
                  </div>

                  <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3 text-[13px]">
                    <div>
                      <span className="label text-muted block">Pack Price</span>
                      <Money amount={latestQuote.pack_price} className="text-base font-bold text-bone" />
                      <span className="text-[11px] text-muted block">({latestQuote.pack_size} pc/pack)</span>
                    </div>
                    <div>
                      <span className="label text-muted block">Freight</span>
                      <Money amount={latestQuote.freight} className="text-base font-bold text-bone" />
                    </div>
                    <div>
                      <span className="label text-muted block">Lead Time</span>
                      <span className="num text-base font-bold text-bone">{latestQuote.lead_days} days</span>
                    </div>
                    <div>
                      <span className="label text-muted block">Total Landed</span>
                      <Money amount={latestQuote.landed_cost} className="text-base font-bold text-signal" />
                    </div>
                  </div>

                  {latestQuote.notes && (
                    <div className="mt-3 text-[12px] text-muted"><strong>Terms:</strong> {latestQuote.notes}</div>
                  )}
                  {latestQuote.per_unit_freight != null && (
                    <div className="mt-2 text-[12px] text-muted">Per-unit freight: ₹{latestQuote.per_unit_freight}/unit (added to flat freight)</div>
                  )}

                  <div className="mt-4 flex items-center justify-between border-t border-line/60 pt-3 text-[12px]">
                    <span className="text-muted flex items-center gap-1">
                      <Clock size={12} /> Submitted at {latestQuote.submitted_at}
                    </span>
                    <button
                      type="button"
                      onClick={() => setIsRevising(true)}
                      className="flex items-center gap-1 rounded-full border border-line bg-raised px-3 py-1.5 font-medium text-bone hover:border-signal/50 hover:text-signal transition-colors"
                    >
                      <RotateCcw size={12} /><span>Revise Quote</span>
                    </button>
                  </div>
                </div>

                {/* Negotiation Target Card */}
                {target && target.status === "pending" && (
                  <NegotiationTargetCard target={target} onRevise={() => setIsRevising(true)} />
                )}

                {/* Revision History */}
                {quotes.length > 1 && (
                  <div className="rounded-xl border border-line bg-surface/50 p-4">
                    <span className="label text-muted flex items-center gap-1.5 mb-2">
                      <History size={13} /> Previous Revisions ({quotes.length} total)
                    </span>
                    <div className="space-y-2">
                      {quotes.map(q => (
                        <div key={q.version} className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[12px] border-b border-line/40 py-1.5 last:border-0">
                          <span className="font-semibold text-bone">v{q.version}</span>
                          <span className="text-muted">₹{q.pack_price}/pack · ₹{q.freight} freight</span>
                          <Money amount={q.landed_cost} className="font-mono text-bone" />
                          <span className="text-muted hidden sm:inline">{q.submitted_at}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : isClosed ? (
              <div className="rounded-2xl border border-line bg-surface/90 p-5">
                {latestQuote && (
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-[13px]">
                    <div>
                      <span className="label text-muted block">Pack Price</span>
                      <Money amount={latestQuote.pack_price} className="text-base font-bold text-bone" />
                    </div>
                    <div>
                      <span className="label text-muted block">Freight</span>
                      <Money amount={latestQuote.freight} className="text-base font-bold text-bone" />
                    </div>
                    <div>
                      <span className="label text-muted block">Lead Time</span>
                      <span className="num text-base font-bold text-bone">{latestQuote.lead_days} days</span>
                    </div>
                    <div>
                      <span className="label text-muted block">Total Landed</span>
                      <Money amount={latestQuote.landed_cost} className="text-base font-bold text-signal" />
                    </div>
                  </div>
                )}
              </div>
            ) : rfq.window_closed && !latestQuote ? null : (
              <div className="rounded-2xl border border-line bg-surface/90 p-5 sm:p-6 shadow-sm">
                <div className="flex items-center justify-between mb-4 pb-3 border-b border-line/60">
                  <div>
                    <h2 className="display text-xl text-bone">
                      {isRevising ? `Revise Quote (Version ${quotes.length + 1})` : "Submit Quotation"}
                    </h2>
                    <p className="text-[13px] text-muted">Complete in under 1 minute.</p>
                  </div>
                  {isRevising && (
                    <button onClick={() => setIsRevising(false)} className="text-[12px] text-muted underline hover:text-bone">
                      Cancel
                    </button>
                  )}
                </div>

                {draft && !latestQuote && (
                  <div className="mb-4 rounded-lg border border-line bg-raised/40 p-3 text-[12px] text-muted">
                    Prefilled from your catalog item <strong className="text-bone">{draft.product_name}</strong>
                    {draft.price_break_applied ? ` (price break at ${draft.price_break_applied}+ units applied)` : ""}.
                    Check each number, edit if needed, then send. Stock is a snapshot, not reserved.
                    <span className="mt-1 block text-[11px]">
                      {assist?.message.source === "ai"
                        ? "Note to buyer drafted by the assistant. Every number in it was checked against your data."
                        : assist?.message.discarded_reason
                          ? `Assistant text was discarded (${assist.message.discarded_reason}). Plain template shown.`
                          : "Note to buyer is a plain template built from your data."}
                    </span>
                  </div>
                )}

                {submitError && (
                  <div className="mb-4 rounded-lg border border-error/40 bg-error/10 p-3 text-[12px] text-error">
                    {submitError}
                  </div>
                )}

                <QuoteForm
                  rfq={{
                    item: rfq.item, qty: rfq.qty, needInDays: rfq.need_in_days,
                  }}
                  products={products || []}
                  key={`${draft?.product_id ?? "none"}-${quotes.length}-${target?.id ?? ""}`}
                  initialValues={formInitialValues}
                  onEdit={handleFirstEdit}
                  onCheckItem={(pid) => checkItemMatch(token, pid)}
                  onSubmit={handleQuoteSubmit}
                  onEstimate={(kg) => estimateShipping(token, kg)}
                  isSubmitting={submitting}
                  versionNumber={quotes.length + 1}
                />
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Chat */}
        {activeTab === "chat" && (
          <SupplierChat
            messages={chatMessages || []}
            currentRole="supplier"
            currentUserName={sellerName}
            onSendMessage={handleSendMessage}
            onReviseFromTarget={() => { setActiveTab("quote"); setIsRevising(true); }}
          />
        )}
      </main>
    </div>
  );
}
