import { useState, useMemo } from "react";
import { Link } from "react-router-dom";
import {
  ArrowLeft,
  Building2,
  Clock,
  History,
  RotateCcw,
  MessageSquare,
  Share2,
} from "lucide-react";
import { useSupplierStore } from "./supplierStore";
import { QuoteForm } from "./components/QuoteForm";
import { StatusChip } from "./components/StatusChip";
import { NegotiationTargetCard } from "./components/NegotiationTargetCard";
import { SupplierChat } from "./components/SupplierChat";
import { Money } from "./components/Money";
import { VerifiedBadge } from "./components/VerifiedBadge";
import type { QuoteVersion } from "./types";

interface SupplierQuotePageProps {
  supplierId?: string; // defaults to "A" (Supplier A)
}

export function SupplierQuotePage({ supplierId = "A" }: SupplierQuotePageProps) {
  const store = useSupplierStore();
  const rfq = store.getRFQ();
  const quotes = store.getQuotesForSupplier(supplierId);
  const target = store.getTargetForSupplier(supplierId);
  const status = store.getSupplierStatus(supplierId);
  const messages = store.getMessages(supplierId);
  const products = store.getState().products;

  const [activeTab, setActiveTab] = useState<"quote" | "chat">("quote");
  const [isRevising, setIsRevising] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);

  const latestQuote: QuoteVersion | null = quotes.length > 0 ? quotes[quotes.length - 1] : null;

  // Determine initial values for form
  const formInitialValues = useMemo(() => {
    // If revising from target, apply the target values!
    if (target && target.status === "pending") {
      return {
        packPrice: latestQuote?.packPrice ?? 10,
        packSize: latestQuote?.packSize ?? 1,
        freight: target.targetFreight !== undefined ? target.targetFreight : (latestQuote?.freight ?? 150),
        leadDays: latestQuote?.leadDays ?? 3,
        moq: latestQuote?.moq ?? 1,
        notes: `Revised to match buyer counter-offer: ${target.message}`,
      };
    }

    if (latestQuote) {
      return {
        packPrice: latestQuote.packPrice,
        packSize: latestQuote.packSize,
        freight: latestQuote.freight,
        leadDays: latestQuote.leadDays,
        moq: latestQuote.moq,
        maxQty: latestQuote.maxQty,
        taxRate: latestQuote.taxRate,
        priceIncludesTax: latestQuote.priceIncludesTax,
        notes: latestQuote.notes,
      };
    }

    return undefined;
  }, [latestQuote, target]);

  const handleQuoteSubmit = (data: {
    packPrice: number;
    packSize: number;
    freight: number;
    leadDays: number;
    moq?: number;
    maxQty?: number;
    taxRate?: number;
    priceIncludesTax?: boolean;
    notes?: string;
  }) => {
    store.submitQuote(supplierId, data);
    setIsRevising(false);
  };

  const handleCopyLink = () => {
    navigator.clipboard?.writeText(window.location.href);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2000);
  };

  return (
    <div className="landing grain min-h-screen bg-ink text-bone pb-16">
      {/* Mobile-Friendly Top Bar */}
      <header className="sticky top-0 z-30 border-b border-line bg-ink/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2.5">
            <Link
              to="/supplier"
              className="flex items-center gap-1 text-[13px] text-muted hover:text-bone"
            >
              <ArrowLeft size={14} />
              <span className="hidden sm:inline">Supplier Portal</span>
            </Link>
            <span className="text-muted/50">·</span>
            <span className="label text-signal">SUPPLIER QUOTE DESK</span>
          </div>

          <div className="flex items-center gap-2">
            <VerifiedBadge tier="tax_ids" />
            <button
              type="button"
              onClick={handleCopyLink}
              className="flex items-center gap-1.5 rounded-full border border-line bg-surface px-2.5 py-1 text-[11px] text-muted hover:text-bone"
              title="Copy mobile invite link"
            >
              <Share2 size={12} />
              <span>{copiedLink ? "Copied!" : "Share Link"}</span>
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-6 space-y-6">
        {/* Top: The Buyer's Request Header Card (PDF Page 3 requirement) */}
        <div className="rounded-2xl border border-line bg-surface/90 p-5 shadow-sm backdrop-blur-md">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-2 text-[12px] text-muted">
                <Building2 size={13} className="text-signal" />
                <span className="font-semibold text-bone">{rfq.buyerCompany}</span>
                <span>·</span>
                <span>{rfq.buyerCity}, {rfq.buyerState}</span>
              </div>
              <h1 className="display text-2xl text-bone mt-1.5">
                Request for Quotation: <span className="text-signal">{rfq.item}</span>
              </h1>
            </div>

            <span className="rounded-full bg-signal/15 border border-signal/30 px-3 py-1 text-[12px] font-semibold text-signal shrink-0">
              {rfq.status}
            </span>
          </div>

          {/* Key Request Parameters */}
          <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 gap-3 border-t border-line/60 pt-3 text-[13px]">
            <div>
              <span className="label text-muted block">Quantity Required</span>
              <span className="num text-base font-bold text-bone">{rfq.qty} units</span>
            </div>
            <div>
              <span className="label text-muted block">Delivery Window</span>
              <span className="num text-base font-bold text-bone">Within {rfq.needInDays} days</span>
            </div>
            <div className="col-span-2 sm:col-span-1">
              <span className="label text-muted block">Contact Person</span>
              <span className="font-medium text-bone">{rfq.buyerName}</span>
            </div>
          </div>

          {rfq.note && (
            <p className="mt-3 rounded-lg border border-line/60 bg-raised/30 p-2.5 text-[12px] text-muted leading-relaxed">
              <strong>Buyer Note:</strong> "{rfq.note}"
            </p>
          )}
        </div>

        {/* View Tabs: Quote Submission vs Discussion */}
        <div className="flex border-b border-line gap-4 text-[13px] font-medium">
          <button
            type="button"
            onClick={() => setActiveTab("quote")}
            className={`pb-2.5 transition-colors border-b-2 flex items-center gap-1.5 ${
              activeTab === "quote"
                ? "border-signal text-bone font-semibold"
                : "border-transparent text-muted hover:text-bone"
            }`}
          >
            <span>Quote Submission</span>
            {latestQuote && (
              <span className="rounded bg-raised px-1.5 py-0.2 text-[10px] text-muted">
                v{latestQuote.version}
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("chat")}
            className={`pb-2.5 transition-colors border-b-2 flex items-center gap-1.5 ${
              activeTab === "chat"
                ? "border-signal text-bone font-semibold"
                : "border-transparent text-muted hover:text-bone"
            }`}
          >
            <MessageSquare size={14} />
            <span>Buyer Negotiation Thread</span>
            {messages.length > 0 && (
              <span className="rounded-full bg-signal text-ink px-1.5 py-0.2 text-[10px] font-bold">
                {messages.length}
              </span>
            )}
          </button>
        </div>

        {/* Tab 1: Quote Form or Status Card */}
        {activeTab === "quote" && (
          <div className="space-y-6">
            {/* If quote already submitted and not currently editing revision */}
            {latestQuote && !isRevising ? (
              <div className="space-y-5">
                {/* Screen 2: Status Page Card (PDF Page 3 requirement) */}
                <div className="rounded-2xl border border-line bg-surface/90 p-5 shadow-sm">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-line/60">
                    <div>
                      <p className="label text-muted">Quote Submission Status</p>
                      <h3 className="display text-xl text-bone mt-0.5">
                        Version {latestQuote.version} Active
                      </h3>
                    </div>
                    <StatusChip status={status} />
                  </div>

                  {/* Summary of submitted quote */}
                  <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3 text-[13px]">
                    <div>
                      <span className="label text-muted block">Pack Price</span>
                      <Money amount={latestQuote.packPrice} className="text-base font-bold text-bone" />
                      <span className="text-[11px] text-muted block">({latestQuote.packSize} pc/pack)</span>
                    </div>
                    <div>
                      <span className="label text-muted block">Freight</span>
                      <Money amount={latestQuote.freight} className="text-base font-bold text-bone" />
                    </div>
                    <div>
                      <span className="label text-muted block">Lead Time</span>
                      <span className="num text-base font-bold text-bone">{latestQuote.leadDays} days</span>
                    </div>
                    <div>
                      <span className="label text-muted block">Total Landed</span>
                      <Money amount={latestQuote.landedCost} className="text-base font-bold text-signal" />
                    </div>
                  </div>

                  {latestQuote.notes && (
                    <div className="mt-3 text-[12px] text-muted">
                      <strong>Terms:</strong> {latestQuote.notes}
                    </div>
                  )}

                  <div className="mt-4 flex items-center justify-between border-t border-line/60 pt-3 text-[12px]">
                    <span className="text-muted flex items-center gap-1">
                      <Clock size={12} /> Submitted at {latestQuote.submittedAt}
                    </span>

                    <button
                      type="button"
                      onClick={() => setIsRevising(true)}
                      className="flex items-center gap-1 rounded-full border border-line bg-raised px-3 py-1.5 font-medium text-bone hover:border-signal/50 hover:text-signal transition-colors"
                    >
                      <RotateCcw size={12} />
                      <span>Revise Quote Terms</span>
                    </button>
                  </div>
                </div>

                {/* If Buyer Sent a Target, prominent callout card */}
                {target && target.status === "pending" && (
                  <NegotiationTargetCard
                    target={target}
                    onRevise={() => setIsRevising(true)}
                  />
                )}

                {/* Revision History */}
                {quotes.length > 1 && (
                  <div className="rounded-xl border border-line bg-surface/50 p-4">
                    <span className="label text-muted flex items-center gap-1.5 mb-2">
                      <History size={13} />
                      Previous Revisions ({quotes.length} total)
                    </span>
                    <div className="space-y-2">
                      {quotes.map((q) => (
                        <div
                          key={q.version}
                          className="flex items-center justify-between text-[12px] border-b border-line/40 py-1.5 last:border-0"
                        >
                          <span className="font-semibold text-bone">v{q.version}</span>
                          <span className="text-muted">₹{q.packPrice}/pack · ₹{q.freight} freight</span>
                          <Money amount={q.landedCost} className="font-mono text-bone" />
                          <span className="text-muted">{q.submittedAt}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              /* Screen 1: Quote Form (New or Revising) */
              <div className="rounded-2xl border border-line bg-surface/90 p-5 sm:p-6 shadow-sm">
                <div className="flex items-center justify-between mb-4 pb-3 border-b border-line/60">
                  <div>
                    <h2 className="display text-xl text-bone">
                      {isRevising ? `Revise Quote (Version ${quotes.length + 1})` : "Submit Quotation"}
                    </h2>
                    <p className="text-[13px] text-muted">
                      Complete in under 1 minute. Enter transparent pack sizes and freight.
                    </p>
                  </div>

                  {isRevising && (
                    <button
                      type="button"
                      onClick={() => setIsRevising(false)}
                      className="text-[12px] text-muted underline hover:text-bone"
                    >
                      Cancel revision
                    </button>
                  )}
                </div>

                <QuoteForm
                  rfq={rfq}
                  products={products}
                  initialValues={formInitialValues}
                  onSubmit={handleQuoteSubmit}
                  versionNumber={quotes.length + 1}
                />
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Negotiation Chat Thread */}
        {activeTab === "chat" && (
          <SupplierChat
            messages={messages}
            currentRole="supplier"
            currentUserName="Suresh Gupta (Supplier A)"
            onSendMessage={(text) =>
              store.sendMessage(supplierId, "supplier", text, "Suresh Gupta")
            }
            onReviseFromTarget={() => {
              setActiveTab("quote");
              setIsRevising(true);
            }}
          />
        )}
      </main>
    </div>
  );
}
