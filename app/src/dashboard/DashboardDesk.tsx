import { useState, useMemo, useCallback, useEffect, useRef } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft, AlertTriangle, FileSpreadsheet,
  TrendingDown, Target, ExternalLink, MessageSquare, Check,
  Save, Lock, X,
} from "lucide-react";
import { evaluate, giveUp, inr, MODES, negotiation, type Mode, type Quote } from "../landing/engine";
import { CostChart } from "../landing/CostChart";
import { QtyControl } from "../landing/QtyControl";
import { SupplierChat } from "../supplier/components/SupplierChat";
import { useApiPoll, useApiOnce } from "../lib/useApi";
import { quotesFromRFQDetails, needFromRFQ } from "../lib/convert";
import {
  getRFQDetails, sendTarget, lockDecision,
  getChatMessages, postChatMessage,
  getSupplierProfileForBuyer,
  type RFQDetailsDTO, type ChatMessageDTO, type SupplierProfileDTO,
} from "../api/client";
import { VerifiedBadge } from "../supplier/components/VerifiedBadge";

export function DashboardDesk() {
  const { rfqId } = useParams<{ rfqId: string }>();

  // Poll RFQ details every 2s for live updates
  const { data: details, loading, error, refetch } = useApiPoll<RFQDetailsDTO>(
    () => getRFQDetails(rfqId || "rfq_c27_01"),
    2000,
    [rfqId],
  );

  const [qty, setQty] = useState<number>(100);
  const [sheetMode, setSheetMode] = useState(false);
  const [mode, setMode] = useState<Mode>("cheapest");
  const [chatSupplierId, setChatSupplierId] = useState<string | null>(null);
  const [targetSuccessId, setTargetSuccessId] = useState<string | null>(null);
  const [showDecisionModal, setShowDecisionModal] = useState(false);
  const [decisionSaved, setDecisionSaved] = useState(false);
  const [profileSupplierId, setProfileSupplierId] = useState<string | null>(null);

  const rfq = details?.rfq;
  const apiQuotes = useMemo(() => details?.quotes || {}, [details]);
  const targets = useMemo(() => details?.targets || {}, [details]);

  // Sync qty to RFQ's actual quantity once on first load
  const qtyInitialized = useRef(false);
  useEffect(() => {
    if (rfq && !qtyInitialized.current) {
      qtyInitialized.current = true;
      setQty(rfq.qty);
      setMode((rfq.priority_mode as Mode) ?? "cheapest");
    }
  }, [rfq]);

  // Convert API quotes to engine Quote[] for the slider
  const engineQuotes: Quote[] = useMemo(() => {
    if (!rfq) return [];
    return quotesFromRFQDetails(apiQuotes, rfq.item);
  }, [apiQuotes, rfq]);

  // Run the local engine at the slider quantity for instant feedback
  const evaluation = useMemo(() => {
    if (engineQuotes.length === 0 || !rfq) return null;
    return evaluate(engineQuotes, { ...needFromRFQ(rfq), qty }, {}, mode);
  }, [engineQuotes, rfq, qty, mode]);

  const winner = evaluation?.winner ?? null;

  // Chat polling
  const { data: chatMessages } = useApiPoll<ChatMessageDTO[]>(
    () => chatSupplierId ? getChatMessages(rfqId || "rfq_c27_01", chatSupplierId) : Promise.resolve([]),
    2000,
    [chatSupplierId, rfqId],
  );

  // Supplier profile (click-through)
  const { data: supplierProfile } = useApiOnce<SupplierProfileDTO>(
    () => profileSupplierId ? getSupplierProfileForBuyer(rfqId || "rfq_c27_01", profileSupplierId) : Promise.resolve(null as any),
    [profileSupplierId, rfqId],
  );

  // Send target concession to runner-up supplier
  const handleSendTarget = useCallback(async (loserId: string, cutNeeded: number, targetFreight?: number, targetPerUnit?: number) => {
    try {
      await sendTarget(rfqId || "rfq_c27_01", {
        supplier_id: loserId,
        cut_needed: cutNeeded,
        target_freight: targetFreight,
        target_per_unit: targetPerUnit,
        concession_type: targetFreight !== undefined ? "freight" : "unit_price",
        message: targetFreight !== undefined
          ? `Cut freight to ₹${targetFreight} or below and you win this order.`
          : `Cut unit price by ₹${targetPerUnit} to win this order.`,
      });
      setTargetSuccessId(loserId);
      setTimeout(() => setTargetSuccessId(null), 3000);
      refetch();
    } catch (e) {
      console.error("Failed to send target:", e);
    }
  }, [rfqId, refetch]);

  const handleSaveDecision = async (winnerId: string, reason: string, approver: string) => {
    try {
      await lockDecision(rfqId || "rfq_c27_01", winnerId, reason, approver);
      setDecisionSaved(true);
      setShowDecisionModal(false);
      refetch();
    } catch (e) {
      console.error("Failed to save decision:", e);
    }
  };

  const handleSendMessage = async (text: string) => {
    if (!chatSupplierId) return;
    try {
      await postChatMessage(rfqId || "rfq_c27_01", chatSupplierId, {
        sender: "buyer",
        sender_name: rfq?.buyer_name || "Buyer",
        text,
      });
    } catch (e) {
      console.error("Failed to send message:", e);
    }
  };

  // ─── Loading / Error / Empty States ──────────────────────────────────

  if (loading && !details) {
    return (
      <div className="landing grain min-h-screen bg-ink text-bone flex items-center justify-center">
        <div className="text-center space-y-3">
          <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-line border-t-signal" />
          <p className="text-[13px] text-muted">Loading RFQ comparison…</p>
        </div>
      </div>
    );
  }

  if (error && !details) {
    return (
      <div className="landing grain min-h-screen bg-ink text-bone flex items-center justify-center">
        <div className="max-w-md rounded-2xl border border-error/40 bg-error/10 p-6 text-center space-y-3">
          <AlertTriangle size={28} className="mx-auto text-error" />
          <h2 className="display text-lg text-bone">Cannot reach the server</h2>
          <p className="text-[13px] text-muted">Make sure the backend is running on port 8000.</p>
          <code className="block rounded-lg bg-raised px-3 py-2 text-[12px] text-bone">{error}</code>
        </div>
      </div>
    );
  }

  if (!rfq || !evaluation) {
    return (
      <div className="landing grain min-h-screen bg-ink text-bone flex items-center justify-center">
        <div className="text-center space-y-3">
          <p className="text-[13px] text-muted">No quotes yet on this request.</p>
          <Link to="/app" className="rounded-full bg-signal px-4 py-2 text-[13px] text-ink">Back to requests</Link>
        </div>
      </div>
    );
  }

  const isDecided = rfq.status === "Decided" || decisionSaved;
  const liveDot = !isDecided;

  return (
    <div className="landing grain min-h-screen bg-ink text-bone pb-16">
      {/* Top Navigation */}
      <header className="sticky top-0 z-30 border-b border-line bg-ink/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            <Link to="/app" className="flex items-center gap-1.5 rounded-full border border-line bg-surface/80 px-3 py-1.5 text-[12px] font-medium text-muted hover:text-bone">
              <ArrowLeft size={13} /><span>Requests</span>
            </Link>
            <div className="h-4 w-px bg-line/60" />
            <div>
              <span className="display text-base font-semibold text-bone">Crossover Desk</span>
              <span className="label ml-2 text-signal">COMPARE ENGINE</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {liveDot && (
              <span className="flex items-center gap-1.5 text-[12px] text-live">
                <span className="h-1.5 w-1.5 rounded-full bg-live animate-pulse" /> Live
              </span>
            )}
            {!isDecided ? (
              <button
                type="button"
                onClick={() => setShowDecisionModal(true)}
                className="flex items-center gap-1.5 rounded-full border border-signal/40 bg-signal/15 px-3 py-1.5 text-[12px] font-semibold text-signal hover:bg-signal hover:text-ink transition-all active:scale-95"
              >
                <Save size={14} /><span>Save Decision</span>
              </button>
            ) : (
              <span className="flex items-center gap-1.5 rounded-full border border-success/40 bg-success/15 px-3 py-1.5 text-[12px] font-semibold text-success">
                <Lock size={14} /><span>Decided</span>
              </span>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 space-y-6">
        {/* Header Strip */}
        <div className="rounded-2xl border border-line bg-surface/70 p-5 backdrop-blur-sm shadow-sm">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <span className="label text-signal">REQUEST</span>
                <span className="text-muted">·</span>
                <span className="text-[13px] text-muted">{rfq.buyer_company}</span>
              </div>
              <h1 className="display text-2xl text-bone mt-1">
                {rfq.item} · <span className="num">{rfq.qty}</span> units
              </h1>
              <p className="text-[13px] text-muted mt-0.5">
                Needed within {rfq.need_in_days} days · {rfq.buyer_city}, {rfq.buyer_state}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1 rounded-full border border-line bg-raised px-2.5 py-0.5 text-[11px] font-medium text-bone">
                <MessageSquare size={12} /> {Object.keys(apiQuotes).length} quotes
              </span>
              <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${isDecided ? "border-success/30 bg-success/15 text-success" : "border-live/30 bg-live/15 text-live"}`}>
                {isDecided ? "Decided" : "Open"}
              </span>
              {rfq.note && (
                <span className="text-[12px] text-muted max-w-xs truncate">"{rfq.note}"</span>
              )}
            </div>
          </div>
        </div>

        {/* Live seller activity */}
        {details?.activity && details.activity.notified > 0 && (
          <div className="flex flex-wrap items-center gap-x-5 gap-y-1 rounded-2xl border border-line bg-surface/70 px-5 py-3 text-[13px]">
            <span className="label text-muted">Seller activity</span>
            {([
              ["notified", details.activity.notified],
              ["viewed", details.activity.viewed],
              ["quoting", details.activity.quoting],
              ["quoted", details.activity.quoted],
            ] as const).map(([label, n]) => (
              <span key={label} className="text-muted">
                <strong className="num text-bone">{n}</strong> {label}
              </span>
            ))}
            <span className="text-[11px] text-muted/80">synthetic demo sellers</span>
          </div>
        )}

        {/* 2-Column Layout */}
        <div className="grid gap-6 lg:grid-cols-[1.25fr_1fr]">
          {/* Left: Supplier Quotes */}
          <div className="space-y-4">
            <div className="rounded-2xl border border-line bg-surface/70 p-5 backdrop-blur-sm space-y-4 shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="display text-lg text-bone">Live Quote Comparison</h2>
                  <p className="text-[13px] text-muted">
                    {engineQuotes.length} supplier{engineQuotes.length !== 1 ? "s" : ""} quoted
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setSheetMode(s => !s)}
                  className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-[12px] font-medium transition-all ${
                    sheetMode
                      ? "border border-error bg-error/15 text-error"
                      : "border border-line bg-raised text-muted hover:text-bone"
                  }`}
                >
                  <FileSpreadsheet size={13} />
                  <span>{sheetMode ? "Naive Sheet View" : "Crossover Engine View"}</span>
                </button>
              </div>

              {/* Priority mode switch: winner under every mode, numbers from the engine */}
              <div className="rounded-xl border border-line bg-raised/30 p-3 space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="label text-muted">Priority</span>
                  {MODES.map(m => (
                    <button
                      key={m}
                      type="button"
                      onClick={() => setMode(m)}
                      className={`rounded-full border px-3 py-1 text-[12px] font-medium capitalize transition-all ${
                        mode === m ? "border-signal bg-signal/15 text-signal" : "border-line bg-surface text-muted hover:text-bone"
                      }`}
                    >
                      {m}
                      <span className="ml-1.5 text-[11px] font-normal text-muted">
                        {evaluation.winners[m]?.quote.supplier ?? "none"}
                      </span>
                    </button>
                  ))}
                </div>
                {giveUp(mode, evaluation.winners) && (
                  <p className="text-[12px] text-muted">{giveUp(mode, evaluation.winners)}</p>
                )}
                {mode === "balanced" && (
                  <p className="text-[11px] text-muted/80">Balanced pays up to 5% over the lowest landed cost to arrive sooner. The 5% is our assumption.</p>
                )}
              </div>

              <div className="space-y-3">
                {evaluation.rows.map((row) => {
                  const isWin = winner?.quote.id === row.quote.id;
                  const isBlocked = row.status === "blocked";
                  const isLate = row.status === "exception";
                  const versions = apiQuotes[row.quote.id] || [];
                  const latestVer = versions.length;
                  const target = targets[row.quote.id];

                  return (
                    <div
                      key={row.quote.id}
                      className={`rounded-xl border p-4 transition-all cursor-pointer ${
                        isWin ? "border-signal bg-signal/10 ring-1 ring-signal/40 shadow-sm"
                        : isBlocked ? "border-line/40 bg-surface/40 opacity-70"
                        : "border-line bg-surface/90 hover:border-signal/30"
                      }`}
                      onClick={() => setProfileSupplierId(row.quote.id)}
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-semibold text-bone">{row.quote.supplier}</span>
                            {latestVer > 1 && (
                              <span className="rounded bg-live/20 text-live px-1.5 py-0.2 text-[10px] font-bold">
                                revised v{latestVer}
                              </span>
                            )}
                            {isWin && (
                              <span className="rounded-full bg-signal px-2 py-0.5 text-[10px] font-bold text-ink uppercase tracking-wide">
                                Winner · {mode === "cheapest" ? "Lowest Landed" : mode === "fastest" ? "Fastest" : "Balanced"}
                              </span>
                            )}
                            {isLate && (
                              <span className="flex items-center gap-1 text-[11px] font-medium text-warn">
                                <AlertTriangle size={12} /> Needs exception ({row.quote.leadDays}d)
                              </span>
                            )}
                            {isBlocked && (
                              <span className="text-[11px] font-medium text-error">
                                Blocked: {row.reason}
                              </span>
                            )}
                          </div>
                          <p className="mt-1 font-mono text-[13px] text-muted">"{row.quote.raw}"</p>
                        </div>
                        <div className="text-right">
                          <p className="label text-muted">Total Landed</p>
                          <p className={`num text-lg font-bold ${isWin ? "text-signal" : "text-bone"}`}>
                            {row.landed !== null ? inr(row.landed) : "—"}
                          </p>
                        </div>
                      </div>

                      {!isBlocked && row.landed !== null && (
                        <div className="mt-3 flex flex-wrap items-center justify-between border-t border-line/60 pt-2.5 text-[12px] text-muted" onClick={e => e.stopPropagation()}>
                          <div className="flex items-center gap-3">
                            <span>Order: <strong className="text-bone">{row.packs} packs</strong> ({row.units} units)</span>
                            <span>·</span>
                            <span>Freight: {inr(row.quote.freight)}</span>
                            {row.overbuy > 0 && (
                              <span className="text-warn">+{row.overbuy} extra inventory</span>
                            )}
                          </div>
                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              onClick={() => setChatSupplierId(row.quote.id)}
                              className="flex items-center gap-1 rounded-full border border-line px-2.5 py-0.5 text-[11px] hover:text-bone hover:border-signal/50"
                            >
                              <MessageSquare size={11} /><span>Chat</span>
                            </button>
                          </div>
                        </div>
                      )}

                      {/* Target status indicator */}
                      {target && (
                        <div className="mt-2 text-[11px] text-signal">
                          ⚡ Target sent: {target.message}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Quantity Slider */}
            <div className="rounded-2xl border border-line bg-surface/70 p-5 backdrop-blur-sm">
              <QtyControl
                qty={qty}
                onQty={setQty}
                sheet={sheetMode}
                onSheet={setSheetMode}
                onReset={() => setQty(rfq.qty)}
              />
            </div>
          </div>

          {/* Right Column: Cost Curves + Negotiate + Why ───────────────── */}
          <div className="space-y-4">
            {/* Live Curves */}
            <div className="rounded-2xl border border-line bg-surface/70 p-5 backdrop-blur-sm space-y-4 shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="display text-lg text-bone">Crossover Cost Curves</h2>
                  <p className="text-[12px] text-muted">
                    At <strong className="text-bone">{qty} units</strong>, Supplier {winner?.quote.id ?? "None"} wins.
                  </p>
                </div>
                <div className="flex items-center gap-1.5 text-success text-[12px] font-medium">
                  <TrendingDown size={14} /><span>Cost crossover</span>
                </div>
              </div>
              <div className="rounded-xl border border-line bg-surface p-3">
                <CostChart qty={qty} winnerId={winner?.quote.id} quotes={engineQuotes} late={evaluation.rows.filter(r => r.status === "exception").map(r => r.quote.id)} />
              </div>
            </div>

            {/* Why This Supplier (gates + cheaper excluded) */}
            {evaluation.cheaperExcluded.length > 0 && (
              <div className="rounded-2xl border border-warn/30 bg-warn/5 p-5 space-y-3">
                <h3 className="display text-base text-bone flex items-center gap-2">
                  <AlertTriangle size={16} className="text-warn" />
                  Cheaper But Excluded
                </h3>
                {evaluation.cheaperExcluded.map((r) => (
                  <div key={r.quote.id} className="flex items-center justify-between text-[12px] border-b border-line/40 py-1.5 last:border-0">
                    <span className="text-bone font-medium">{r.quote.supplier}</span>
                    <span className="text-warn">{r.reason}</span>
                    <span className="num text-muted">{r.landed !== null ? inr(r.landed) : "—"}</span>
                  </div>
                ))}
              </div>
            )}

            {/* The Negotiate Panel */}
            {!isDecided && (
              <div className="rounded-2xl border border-line bg-surface/80 p-5 backdrop-blur-sm space-y-4 shadow-sm">
                <div className="flex items-center justify-between border-b border-line/60 pb-3">
                  <div className="flex items-center gap-2">
                    <Target size={16} className="text-signal" />
                    <h3 className="display text-base font-semibold text-bone">Negotiate Panel</h3>
                  </div>
                  <span className="label text-muted">Engine Concessions</span>
                </div>

                <p className="text-[13px] text-muted leading-relaxed">
                  Send exact concession targets to runners-up. If the supplier accepts, the winner updates live.
                </p>

                <div className="space-y-3">
                  {evaluation.rows
                    .filter(r => r.quote.id !== winner?.quote.id && r.status === "eligible" && r.landed !== null)
                    .map(loser => {
                      const neg = winner ? negotiation(loser, winner) : null;
                      if (!neg) return null;
                      const sent = targetSuccessId === loser.quote.id || targets[loser.quote.id]?.status === "pending";

                      return (
                        <div key={loser.quote.id} className="rounded-xl border border-line bg-raised/30 p-3.5 space-y-2.5">
                          <div className="flex items-start justify-between">
                            <div>
                              <span className="font-semibold text-bone text-[13px]">{loser.quote.supplier}</span>
                              <span className="num text-muted ml-2 text-[12px]">(Landed: {inr(loser.landed!)})</span>
                            </div>
                            <span className="num text-warn text-[12px] font-bold">Gap: {inr(neg.cut)}</span>
                          </div>

                          <p className="text-[12px] text-muted">
                            {neg.freight !== null ? (
                              <>Winning concession: <strong>Cut freight from {inr(loser.quote.freight)} to {inr(loser.quote.freight - neg.freight)}</strong>.</>
                            ) : (
                              <>Winning concession: <strong>Cut unit price by {inr(neg.perUnit)}/unit</strong>.</>
                            )}
                          </p>

                          <div className="flex items-center justify-between pt-1">
                            <button
                              type="button"
                              disabled={sent}
                              onClick={() => handleSendTarget(
                                loser.quote.id, neg.cut,
                                neg.freight !== null ? loser.quote.freight - neg.freight : undefined,
                                neg.perUnit,
                              )}
                              className={`flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-[12px] font-semibold transition-all ${
                                sent ? "border border-live/40 bg-live/20 text-live"
                                : "bg-signal text-ink hover:opacity-90 active:scale-95"
                              }`}
                            >
                              {sent ? (
                                <><Check size={12} strokeWidth={2.5} /><span>Target Sent</span></>
                              ) : (
                                <><Target size={12} /><span>Send Target</span></>
                              )}
                            </button>

                            <Link
                              to="/supplier/quote"
                              target="_blank"
                              className="text-[11px] text-muted underline hover:text-bone flex items-center gap-1"
                            >
                              <span>Open as Supplier</span><ExternalLink size={10} />
                            </Link>
                          </div>
                        </div>
                      );
                    })}
                </div>
              </div>
            )}

            {/* Decision Summary (read-only after decided) */}
            {isDecided && rfq.decision && (
              <div className="rounded-2xl border border-success/40 bg-success/10 p-5 space-y-3">
                <div className="flex items-center gap-2">
                  <Lock size={16} className="text-success" />
                  <h3 className="display text-base font-semibold text-success">Decision Saved</h3>
                </div>
                <div className="text-[13px] text-muted space-y-1">
                  <p>Winner: <strong className="text-bone">Supplier {rfq.decision.winner_id as string}</strong></p>
                  <p>Reason: <span className="text-bone">{rfq.decision.reason as string}</span></p>
                  <p>Approver: <span className="text-bone">{rfq.decision.approver as string}</span></p>
                </div>
              </div>
            )}

            {/* Chat Flyout */}
            {chatSupplierId && (
              <SupplierChat
                messages={chatMessages || []}
                currentRole="buyer"
                currentUserName={rfq.buyer_name}
                onSendMessage={handleSendMessage}
              />
            )}
          </div>
        </div>
      </main>

      {/* Supplier Profile Side Panel (click-through) */}
      {profileSupplierId && supplierProfile && (
        <div className="fixed inset-0 z-40 flex justify-end" onClick={() => setProfileSupplierId(null)}>
          <div className="absolute inset-0 bg-ink/60 backdrop-blur-sm" />
          <div
            className="relative w-full max-w-sm h-full overflow-y-auto border-l border-line bg-surface p-6 space-y-4"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <h3 className="display text-lg text-bone">Supplier Profile</h3>
              <button onClick={() => setProfileSupplierId(null)} className="text-muted hover:text-bone">
                <X size={18} />
              </button>
            </div>
            <div>
              <h4 className="text-base font-semibold text-bone">{supplierProfile.business_name}</h4>
              <p className="text-[13px] text-muted">{supplierProfile.location_city}, {supplierProfile.location_state}</p>
              <div className="mt-2"><VerifiedBadge tier={supplierProfile.verification_tier} /></div>
              {supplierProfile.description && (
                <p className="mt-2 text-[12px] text-muted">{supplierProfile.description}</p>
              )}
              <div className="mt-2 flex flex-wrap gap-1.5">
                {supplierProfile.categories.map(c => (
                  <span key={c} className="rounded-full bg-raised px-2 py-0.5 text-[11px] text-muted">{c}</span>
                ))}
              </div>
            </div>
            {supplierProfile.products.length > 0 && (
              <div className="border-t border-line/60 pt-3">
                <span className="label text-muted">Products</span>
                <div className="mt-2 space-y-2">
                  {supplierProfile.products.map(p => (
                    <div key={p.id} className="rounded-lg border border-line bg-raised/30 p-2.5 text-[12px]">
                      <span className="font-medium text-bone">{p.name}</span>
                      <div className="mt-0.5 flex gap-3 text-muted">
                        <span className="num">₹{p.pack_price}/{p.pack_size} {p.unit}</span>
                        <span>· {p.usual_lead_days}d lead</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Save Decision Modal */}
      {showDecisionModal && evaluation && (
        <SaveDecisionModal
          evaluation={evaluation}
          buyerName={rfq.buyer_name}
          onSave={handleSaveDecision}
          onClose={() => setShowDecisionModal(false)}
        />
      )}
    </div>
  );
}

// ─── Save Decision Modal ───────────────────────────────────────────────────

function SaveDecisionModal({
  evaluation, buyerName, onSave, onClose,
}: {
  evaluation: ReturnType<typeof evaluate>;
  buyerName: string;
  onSave: (winnerId: string, reason: string, approver: string) => void;
  onClose: () => void;
}) {
  const [winnerId, setWinnerId] = useState(evaluation.winner?.quote.id || "");
  const [reason, setReason] = useState(
    evaluation.winner
      ? `${evaluation.mode === "cheapest" ? "Lowest landed cost" : evaluation.mode === "fastest" ? "Fastest delivery" : "Best balance of cost and speed"} at ${inr(evaluation.winner.landed!)}. ${evaluation.winner.quote.supplier} wins.`
      : ""
  );
  const [approver, setApprover] = useState(buyerName);

  const eligible = evaluation.rows.filter(r => r.status === "eligible" || r.approved);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/80 backdrop-blur-md p-4">
      <div className="w-full max-w-md rounded-2xl border border-line bg-surface p-6 shadow-2xl space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="display text-xl text-bone">Save Decision</h3>
          <button onClick={onClose} className="text-muted hover:text-bone"><X size={18} /></button>
        </div>
        <p className="text-[13px] text-muted">This locks the RFQ. Suppliers can no longer revise quotes.</p>

        <div>
          <label className="label mb-1.5 block text-bone">Winner</label>
          <select
            value={winnerId}
            onChange={e => setWinnerId(e.target.value)}
            className="w-full rounded-lg border border-line bg-raised px-3 py-2 text-[14px] text-bone"
          >
            {eligible.map(r => (
              <option key={r.quote.id} value={r.quote.id}>
                {r.quote.supplier} — {r.landed !== null ? inr(r.landed) : "N/A"}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="label mb-1.5 block text-bone">Reason</label>
          <textarea
            value={reason}
            onChange={e => setReason(e.target.value)}
            rows={3}
            className="w-full rounded-lg border border-line bg-raised px-3 py-2 text-[13px] text-bone"
          />
        </div>

        <div>
          <label className="label mb-1.5 block text-bone">Approver</label>
          <input
            type="text"
            value={approver}
            onChange={e => setApprover(e.target.value)}
            className="w-full rounded-lg border border-line bg-raised px-3 py-2 text-[14px] text-bone"
          />
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <button onClick={onClose} className="rounded-full border border-line px-4 py-1.5 text-[13px] text-muted hover:text-bone">
            Cancel
          </button>
          <button
            onClick={() => onSave(winnerId, reason, approver)}
            disabled={!winnerId || !reason.trim() || !approver.trim()}
            className="flex items-center gap-1.5 rounded-full bg-signal px-5 py-1.5 text-[13px] font-medium text-ink hover:opacity-90 disabled:opacity-40"
          >
            <Save size={14} /><span>Save & Lock</span>
          </button>
        </div>
      </div>
    </div>
  );
}
