import { useState, useMemo, useCallback, useEffect, useRef } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft, AlertTriangle, FileSpreadsheet,
  TrendingDown, Target, MessageSquare, Check,
  Save, Lock, X, Unlock, ShieldCheck,
} from "lucide-react";
import { FactTag } from "../components/FactTag";
import { evaluate, giveUp, inr, MODES, naivePick, negotiation, type Mode, type Quote } from "../landing/engine";
import { CostChart } from "../landing/CostChart";
import { QtyControl } from "../landing/QtyControl";
import { SupplierChat } from "../supplier/components/SupplierChat";
import { useApiPoll, useApiOnce } from "../lib/useApi";
import { quotesFromRFQDetails, needFromRFQ } from "../lib/convert";
import {
  getRFQDetails, sendTarget, lockDecision,
  getChatMessages, postChatMessage,
  getSupplierProfileForBuyer, getSummary, revealSeller, mockUpgrade, RevealsExhausted, recordException, withdrawException,
  type RFQDetailsDTO, type ChatMessageDTO, type SellerPanelDTO, type SellerIdentity, type PlanInfo, type SummaryDTO,
} from "../api/client";

export function DashboardDesk() {
  const { rfqId } = useParams<{ rfqId: string }>();

  // Poll RFQ details every 2s for live updates
  const { data: details, loading, error, refetch } = useApiPoll<RFQDetailsDTO>(
    () => getRFQDetails(rfqId ?? ""),
    2000,
    [rfqId],
  );

  const [qty, setQty] = useState<number>(100);
  const [sheetMode, setSheetMode] = useState(false);
  const [mode, setMode] = useState<Mode>("cheapest");
  // Target being reviewed before a person sends it: nothing goes out without this step
  const [reviewTarget, setReviewTarget] = useState<{ id: string; message: string } | null>(null);
  const [chatSupplierId, setChatSupplierId] = useState<string | null>(null);
  const [targetSuccessId, setTargetSuccessId] = useState<string | null>(null);
  const [showDecisionModal, setShowDecisionModal] = useState(false);
  const [decisionSaved, setDecisionSaved] = useState(false);
  const [profileSupplierId, setProfileSupplierId] = useState<string | null>(null);
  const [paywall, setPaywall] = useState(false);
  const [exceptionFor, setExceptionFor] = useState<string | null>(null);
  const [revealingAlias, setRevealingAlias] = useState<string | null>(null);
  const [revealError, setRevealError] = useState<string | null>(null);

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
    return evaluate(engineQuotes, { ...needFromRFQ(rfq), qty }, details?.exceptions ?? {}, mode);
  }, [engineQuotes, rfq, qty, mode, details?.exceptions]);

  const winner = evaluation?.winner ?? null;

  // Spreadsheet mode: what a sheet sorted by sticker price per unit would pick, ignoring freight, pack
  // rounding and the lead-time gate. Shown next to the engine's pick so the difference is visible.
  const sheetPick = useMemo(() => {
    if (!rfq || engineQuotes.length === 0) return null;
    const q = naivePick(engineQuotes, { ...needFromRFQ(rfq), qty });
    const row = q ? evaluation?.rows.find(r => r.quote.id === q.id) ?? null : null;
    return q && row ? { quote: q, landed: row.landed, unit: q.packPrice / (q.packSize ?? 1) } : null;
  }, [engineQuotes, rfq, qty, evaluation]);
  const unitPrice = (q: Quote) => q.packPrice / (q.packSize ?? 1);

  // Chat polling
  const { data: chatMessages } = useApiPoll<ChatMessageDTO[]>(
    () => chatSupplierId ? getChatMessages(rfqId ?? "", chatSupplierId) : Promise.resolve([]),
    2000,
    [chatSupplierId, rfqId],
  );

  // Savings vs the spreadsheet pick, only once a person has saved the decision
  const decidedNow = details?.rfq.status === "Decided" || decisionSaved;
  const { data: summary } = useApiOnce<SummaryDTO | null>(
    () => decidedNow ? getSummary(rfqId ?? "") : Promise.resolve(null),
    [decidedNow, rfqId],
  );

  // Supplier profile (click-through)
  const { data: supplierProfile, refetch: refetchPanel } = useApiOnce<SellerPanelDTO | null>(
    () => profileSupplierId ? getSupplierProfileForBuyer(rfqId ?? "", profileSupplierId) : Promise.resolve(null),
    [profileSupplierId, rfqId],
  );

  // Unlock one seller. Uses a free reveal; when none are left the paywall opens. Never throws into the UI.
  const handleReveal = useCallback(async (alias: string) => {
    setRevealingAlias(alias); setRevealError(null);
    try {
      const r = await revealSeller(rfqId ?? "", alias);
      refetch(); refetchPanel();
      return r;
    } catch (e) {
      if (e instanceof RevealsExhausted) setPaywall(true);
      else setRevealError(e instanceof Error ? e.message : "Could not reveal this seller.");
      return null;
    } finally {
      setRevealingAlias(null);
    }
  }, [rfqId, refetch, refetchPanel]);

  // Send target concession to runner-up supplier
  const handleSendTarget = useCallback(async (loserId: string, cutNeeded: number, message: string, targetFreight?: number, targetPerUnit?: number) => {
    try {
      await sendTarget(rfqId ?? "", {
        supplier_id: loserId,
        cut_needed: cutNeeded,
        target_freight: targetFreight,
        target_per_unit: targetPerUnit,
        concession_type: targetFreight !== undefined ? "freight" : "unit_price",
        message,
        sent_by: rfq?.buyer_name || "Buyer",
      });
      setReviewTarget(null);
      setTargetSuccessId(loserId);
      setTimeout(() => setTargetSuccessId(null), 3000);
      refetch();
    } catch (e) {
      console.error("Failed to send target:", e);
    }
  }, [rfqId, refetch, rfq]);

  const handleSaveDecision = async (winnerId: string, reason: string, approver: string) => {
    try {
      await lockDecision(rfqId ?? "", winnerId, reason, approver);
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
      await postChatMessage(rfqId ?? "", chatSupplierId, {
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
            {details?.plan && <PlanChip plan={details.plan} />}
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
              ["declined", details.activity.declined],
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

              {sheetMode && (
                <div className="rounded-xl border border-error/40 bg-error/10 p-3 text-[13px] space-y-1" aria-live="polite">
                  <p className="label text-error">Spreadsheet view: sorted by price per unit</p>
                  {sheetPick ? (
                    <p className="text-bone">
                      A sheet picks <strong>{sheetPick.quote.supplier}</strong> at <span className="num">{inr(sheetPick.unit)}</span> a unit.
                      {" "}It ignores freight, pack rounding and the delivery date.
                      {winner && sheetPick.landed !== null && winner.landed !== null && (
                        winner.quote.id === sheetPick.quote.id
                          ? <> Here Crossover agrees: {winner.quote.supplier} is also cheapest landed.</>
                          : <> Crossover picks <strong>{winner.quote.supplier}</strong> at <span className="num">{inr(winner.landed)}</span> landed,
                              {" "}<strong className="num text-signal">{inr(sheetPick.landed - winner.landed)}</strong> less than the sheet's pick ({inr(sheetPick.landed)}).</>
                      )}
                    </p>
                  ) : <p className="text-muted">No quote passes the delivery date, so a sheet would have nothing to pick.</p>}
                </div>
              )}

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
                {(sheetMode ? [...evaluation.rows].sort((a, b) => unitPrice(a.quote) - unitPrice(b.quote)) : evaluation.rows).map((row) => {
                  const isWin = winner?.quote.id === row.quote.id;
                  const isBlocked = row.status === "blocked";
                  const isLate = row.status === "exception";
                  const versions = apiQuotes[row.quote.id] || [];
                  const latestVer = versions.length;
                  const target = targets[row.quote.id];
                  const badge = details?.badges?.[row.quote.id];
                  const identity = details?.revealed?.[row.quote.id];

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
                            {versions[latestVer - 1]?.origin && versions[latestVer - 1].origin !== "manual" && (
                              <span className="rounded bg-raised px-1.5 py-0.5 text-[10px] font-medium text-muted" title="Numbers come from the seller's own catalog. Auto quotes were sent without a person reviewing them.">
                                {versions[latestVer - 1].origin === "auto" ? "auto · seller autopilot, not reviewed"
                                  : versions[latestVer - 1].origin === "ai_draft_sent" ? "assistant draft" : "assistant draft, edited"}
                              </span>
                            )}
                            {sheetMode && sheetPick?.quote.id === row.quote.id && (
                              <span className="rounded-full bg-error px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-ink">
                                Sheet pick
                              </span>
                            )}
                            {sheetMode && (
                              <span className="num text-[11px] text-muted">{inr(unitPrice(row.quote))}/unit</span>
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
                          {isLate && details?.exceptions?.[row.quote.id] && (
                            <p className="mt-1 text-[12px] text-bone" onClick={e => e.stopPropagation()}>
                              <strong>Exception recorded:</strong> “{details.exceptions[row.quote.id].reason}” — approved by {details.exceptions[row.quote.id].approver}{" "}
                              {!isDecided && (
                                <button type="button" className="text-muted underline hover:text-bone"
                                  onClick={() => withdrawException(rfqId ?? "", row.quote.id).then(() => refetch())}>withdraw</button>
                              )}
                            </p>
                          )}
                          {isLate && !details?.exceptions?.[row.quote.id] && !isDecided && (
                            <p className="mt-1 text-[12px] text-warn" onClick={e => e.stopPropagation()}>
                              Not recommended: {row.reason}.{" "}
                              <button type="button" className="font-medium underline hover:text-bone" onClick={() => setExceptionFor(row.quote.id)}>
                                Approve an exception
                              </button>
                            </p>
                          )}
                          {versions[latestVer - 1] && (
                            versions[latestVer - 1].tax_basis === "assumed_exclusive" ? (
                              <p className="mt-1 text-[11px] text-warn" title="The seller did not say whether their price includes GST. We compare it as excluding GST. Confirm before ordering.">
                                GST basis not stated: compared as excluding GST
                              </p>
                            ) : versions[latestVer - 1].compare_price != null && Math.abs((versions[latestVer - 1].compare_price as number) - versions[latestVer - 1].pack_price) > 0.005 ? (
                              <p className="mt-1 text-[11px] text-muted">
                                Quoted {inr(versions[latestVer - 1].pack_price)} {versions[latestVer - 1].price_includes_tax ? "incl." : "excl."} {versions[latestVer - 1].tax_rate}% GST
                                {" "}→ compared as <span className="num text-bone">{inr(versions[latestVer - 1].compare_price as number)}</span>{" "}
                                {rfq.gst_claimable === false ? "incl. GST" : "ex-GST"}
                              </p>
                            ) : null
                          )}
                          {badge && (
                            <p className="mt-1 flex items-center gap-1 text-[11px] text-muted">
                              <ShieldCheck size={11} className="shrink-0" />
                              <span>{badge.region} · {badge.verification_text}</span>
                            </p>
                          )}
                          {identity && (
                            <div className="mt-2 rounded-lg border border-live/40 bg-live/10 p-2 text-[12px] text-bone">
                              <strong>{identity.business_name}</strong>
                              <span className="text-muted"> · {identity.city}, {identity.state}</span>
                              <div className="num text-muted">
                                {identity.contact_name}{identity.phone ? ` · ${identity.phone}` : ""}{identity.email ? ` · ${identity.email}` : ""}
                              </div>
                            </div>
                          )}
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
                            {row.landed !== null && qty > 0 && (
                              <span title="Landed cost over the units you need" className="num">{inr(row.landed / qty)} per usable unit</span>
                            )}
                            {row.overbuy > 0 && (
                              <span className="text-warn" title="Extra units bought because of pack size or minimum order">
                                +{row.overbuy} extra units ({inr(row.overbuy * unitPrice(row.quote))} tied up)
                              </span>
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
                            {identity ? (
                              <span className="flex items-center gap-1 rounded-full border border-live/40 bg-live/10 px-2.5 py-0.5 text-[11px] text-live">
                                <Unlock size={11} /><span>Unlocked</span>
                              </span>
                            ) : (
                              <button
                                type="button"
                                disabled={revealingAlias === row.quote.id}
                                onClick={() => handleReveal(row.quote.id)}
                                title="Unlock this seller's name and contact"
                                className="flex items-center gap-1 rounded-full border border-signal/50 bg-signal/10 px-2.5 py-0.5 text-[11px] font-medium text-signal hover:bg-signal hover:text-ink disabled:opacity-40"
                              >
                                <Unlock size={11} /><span>{revealingAlias === row.quote.id ? "Revealing…" : "Reveal"}</span>
                              </button>
                            )}
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
                    At <strong className="text-bone">{qty} units</strong>, {winner?.quote.supplier ?? "No one"} wins.
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

            {/* Why this supplier: gates as pass/fail, facts tagged by where they came from */}
            {winner && winner.landed !== null && (
              <WhyCard row={winner} qty={qty} needInDays={rfq.need_in_days} mode={mode} />
            )}

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
                  The engine works out the exact concession. You review the message and send it yourself;
                  nothing is sent automatically. When the seller revises, the winner updates live.
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

                          {reviewTarget?.id === loser.quote.id && !sent && (
                            <div className="space-y-2 rounded-lg border border-signal/40 bg-signal/5 p-3">
                              <label className="label block text-muted">Message to {loser.quote.supplier} (edit freely)</label>
                              <textarea
                                value={reviewTarget.message}
                                onChange={e => setReviewTarget({ id: loser.quote.id, message: e.target.value })}
                                rows={2}
                                className="w-full rounded-lg border border-line bg-raised px-3 py-2 text-[13px] text-bone"
                              />
                              <p className="text-[11px] text-muted">
                                Target numbers come from the engine: gap {inr(neg.cut)}
                                {neg.freight !== null ? `, freight to ${inr(loser.quote.freight - neg.freight)}` : `, ${inr(neg.perUnit)} off per unit`}.
                              </p>
                              <div className="flex justify-end gap-2">
                                <button type="button" onClick={() => setReviewTarget(null)}
                                  className="rounded-full border border-line px-3 py-1 text-[12px] text-muted hover:text-bone">Cancel</button>
                                <button
                                  type="button"
                                  disabled={!reviewTarget.message.trim()}
                                  onClick={() => handleSendTarget(
                                    loser.quote.id, neg.cut, reviewTarget.message.trim(),
                                    neg.freight !== null ? loser.quote.freight - neg.freight : undefined,
                                    neg.perUnit,
                                  )}
                                  className="rounded-full bg-signal px-3.5 py-1 text-[12px] font-semibold text-ink disabled:opacity-40"
                                >
                                  Send as {rfq.buyer_name}
                                </button>
                              </div>
                            </div>
                          )}

                          <div className="flex items-center justify-between pt-1">
                            <button
                              type="button"
                              disabled={sent || reviewTarget?.id === loser.quote.id}
                              onClick={() => setReviewTarget({
                                id: loser.quote.id,
                                message: neg.freight !== null
                                  ? `Cut freight to ₹${loser.quote.freight - neg.freight} or below and you win this order.`
                                  : `Cut unit price by ₹${neg.perUnit} to win this order.`,
                              })}
                              className={`flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-[12px] font-semibold transition-all ${
                                sent ? "border border-live/40 bg-live/20 text-live"
                                : "bg-signal text-ink hover:opacity-90 active:scale-95"
                              }`}
                            >
                              {sent ? (
                                <><Check size={12} strokeWidth={2.5} /><span>Target Sent</span></>
                              ) : (
                                <><Target size={12} /><span>Review target</span></>
                              )}
                            </button>
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
                  <p>Winner: <strong className="text-bone">{(details?.revealed?.[rfq.decision.winner_id as string]?.business_name) ?? (rfq.decision.winner_id as string)}</strong></p>
                  {details?.revealed?.[rfq.decision.winner_id as string] && (
                    <p className="num">Contact: <span className="text-bone">
                      {details.revealed[rfq.decision.winner_id as string].contact_name} · {details.revealed[rfq.decision.winner_id as string].phone} · {details.revealed[rfq.decision.winner_id as string].email}
                    </span></p>
                  )}
                  <p>Payment: <span className="text-bone">{(rfq.decision.payment_note as string) ?? "Cash on delivery. Crossover never holds money."}</span></p>
                  <p>Reason: <span className="text-bone">{rfq.decision.reason as string}</span></p>
                  <p>Approver: <span className="text-bone">{rfq.decision.approver as string}</span></p>
                </div>
                {summary?.savings && (
                  <p className="text-[13px] text-bone">
                    Spreadsheet pick: {summary.savings.spreadsheet_pick} at {inr(summary.savings.spreadsheet_landed)}.
                    Crossover pick: {summary.savings.crossover_pick} at {inr(summary.savings.crossover_landed)}.
                    Difference: <strong className="num text-signal">{inr(summary.savings.difference)}</strong>
                    <span className="text-muted"> ({summary.savings.label})</span>
                  </p>
                )}
                <Link to={`/app/decision/${rfq.id}`} className="inline-block rounded-full border border-success/40 px-3 py-1 text-[12px] font-medium text-success hover:bg-success/10">
                  Open decision one-pager
                </Link>
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

      {/* Seller panel (click-through): anonymous until revealed */}
      {profileSupplierId && supplierProfile && (
        <div className="fixed inset-0 z-40 flex justify-end" onClick={() => setProfileSupplierId(null)}>
          <div className="absolute inset-0 bg-ink/60 backdrop-blur-sm" />
          <div
            className="relative w-full max-w-sm h-full overflow-y-auto border-l border-line bg-surface p-6 space-y-4"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <h3 className="display text-lg text-bone">{supplierProfile.revealed ? "Seller" : "Anonymous seller"}</h3>
              <button onClick={() => setProfileSupplierId(null)} className="text-muted hover:text-bone">
                <X size={18} />
              </button>
            </div>
            <div>
              <h4 className="text-base font-semibold text-bone">{supplierProfile.business_name}</h4>
              <p className="text-[13px] text-muted">
                {supplierProfile.revealed ? `${supplierProfile.location_city}, ${supplierProfile.location_state}` : supplierProfile.location_state}
              </p>
              <p className="mt-2 flex items-start gap-1.5 text-[12px] text-muted">
                <ShieldCheck size={13} className="mt-0.5 shrink-0" /><span>{supplierProfile.verification_text}</span>
              </p>
              {supplierProfile.description && <p className="mt-2 text-[12px] text-muted">{supplierProfile.description}</p>}
              <div className="mt-2 flex flex-wrap gap-1.5">
                {supplierProfile.categories.map(c => (
                  <span key={c} className="rounded-full bg-raised px-2 py-0.5 text-[11px] text-muted">{c}</span>
                ))}
              </div>
            </div>

            {supplierProfile.revealed && supplierProfile.contact ? (
              <div className="rounded-lg border border-live/40 bg-live/10 p-3 text-[13px] text-bone space-y-0.5">
                <div className="font-semibold">Contact</div>
                <div>{supplierProfile.contact.contact_name}</div>
                <div className="num">{supplierProfile.contact.phone}</div>
                <div className="num">{supplierProfile.contact.email}</div>
              </div>
            ) : (
              <div className="rounded-lg border border-line bg-raised/40 p-3 space-y-2">
                <p className="text-[12px] text-muted">
                  Name, city, products and contact are hidden until you reveal this seller. {details?.plan && <PlanLine plan={details.plan} />}
                </p>
                <button type="button" disabled={revealingAlias === supplierProfile.supplier_id}
                  onClick={() => handleReveal(supplierProfile.supplier_id)}
                  className="flex items-center gap-1.5 rounded-full bg-signal px-4 py-1.5 text-[12px] font-semibold text-ink disabled:opacity-40">
                  <Unlock size={13} /><span>Reveal {supplierProfile.supplier_id}</span>
                </button>
                {revealError && <p className="text-[12px] text-error">{revealError}</p>}
              </div>
            )}

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
          revealed={details?.revealed ?? {}}
          revealing={revealingAlias !== null}
          onReveal={handleReveal}
          onSave={handleSaveDecision}
          onClose={() => setShowDecisionModal(false)}
        />
      )}

      {exceptionFor && (
        <ExceptionModal
          supplier={exceptionFor}
          reason={evaluation.rows.find(r => r.quote.id === exceptionFor)?.reason ?? ""}
          giveUp={(() => {
            const row = evaluation.rows.find(r => r.quote.id === exceptionFor);
            const best = evaluation.pool[0];
            return row?.landed != null && best?.landed != null && row.landed < best.landed ? best.landed - row.landed : null;
          })()}
          defaultApprover={rfq.buyer_name}
          onClose={() => setExceptionFor(null)}
          onSave={async (reason, approver) => {
            await recordException(rfqId ?? "", exceptionFor, reason, approver);
            setExceptionFor(null);
            refetch();
          }}
        />
      )}

      {paywall && (
        <PaywallModal
          plan={details?.plan}
          onClose={() => setPaywall(false)}
          onUpgraded={() => { setPaywall(false); refetch(); }}
        />
      )}
    </div>
  );
}

// ─── Save Decision Modal ───────────────────────────────────────────────────

function SaveDecisionModal({
  evaluation, buyerName, revealed, revealing, onReveal, onSave, onClose,
}: {
  evaluation: ReturnType<typeof evaluate>;
  buyerName: string;
  revealed: Record<string, SellerIdentity>;
  revealing: boolean;
  onReveal: (alias: string) => Promise<unknown>;
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
        <p className="text-[13px] text-muted">
          This places the order and locks the request. Payment is cash on delivery; Crossover never holds money.
        </p>

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

        {winnerId && !revealed[winnerId] && (
          <p className="rounded-lg border border-line bg-raised/40 p-2.5 text-[12px] text-muted">
            To place the order you need {winnerId}'s contact. Reveal them first. It uses one of your free reveals,
            unless you have unlocked this seller before.
          </p>
        )}

        <div className="flex justify-end gap-2 pt-2">
          <button onClick={onClose} className="rounded-full border border-line px-4 py-1.5 text-[13px] text-muted hover:text-bone">
            Cancel
          </button>
          {winnerId && !revealed[winnerId] ? (
            <button
              onClick={() => onReveal(winnerId)}
              disabled={revealing}
              className="flex items-center gap-1.5 rounded-full bg-signal px-5 py-1.5 text-[13px] font-medium text-ink hover:opacity-90 disabled:opacity-40"
            >
              <Unlock size={14} /><span>{revealing ? "Revealing…" : `Reveal ${winnerId}`}</span>
            </button>
          ) : (
            <button
              onClick={() => onSave(winnerId, reason, approver)}
              disabled={!winnerId || !reason.trim() || !approver.trim()}
              className="flex items-center gap-1.5 rounded-full bg-signal px-5 py-1.5 text-[13px] font-medium text-ink hover:opacity-90 disabled:opacity-40"
            >
              <Save size={14} /><span>Place order & lock</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}


// ─── Reveals left, and the mock paywall ────────────────────────────────────

function PlanLine({ plan }: { plan: PlanInfo }) {
  return plan.plan === "pro"
    ? <>You are on the demo paid plan (mock), so reveals are unlimited.</>
    : <>You have {plan.reveals_left} of {plan.free_limit} free reveals left. A seller you have already unlocked costs nothing.</>;
}

function PlanChip({ plan }: { plan: PlanInfo }) {
  return (
    <span className="num rounded-full border border-line bg-surface px-2.5 py-1 text-[12px] text-muted"
      title="Reveals unlock a seller's name and contact">
      {plan.plan === "pro" ? "Reveals: unlimited (mock plan)" : `${plan.reveals_left} of ${plan.free_limit} free reveals left`}
    </span>
  );
}

/** The paywall is a mock. The upgrade button flips a flag on the demo server; no payment is taken or stored. */
function PaywallModal({ plan, onClose, onUpgraded }: { plan?: PlanInfo; onClose: () => void; onUpgraded: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const upgrade = async () => {
    setBusy(true); setError(null);
    try { await mockUpgrade(); onUpgraded(); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not upgrade."); setBusy(false); }
  };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/80 backdrop-blur-md p-4">
      <div className="w-full max-w-md space-y-4 rounded-2xl border border-line bg-surface p-6 shadow-2xl">
        <div className="flex items-center justify-between">
          <h3 className="display text-xl text-bone">You've used your free reveals</h3>
          <button onClick={onClose} className="text-muted hover:text-bone"><X size={18} /></button>
        </div>
        <p className="text-[13px] text-muted">
          Comparing quotes is free and stays free. Revealing a seller's name and contact uses a reveal.
          {plan ? ` You used ${plan.free_limit} of ${plan.free_limit}.` : ""} Sellers you have already unlocked stay unlocked.
        </p>
        <div className="space-y-2 rounded-xl border border-line bg-raised/40 p-3 text-[13px]">
          <div className="flex justify-between"><span className="text-bone">Reveal pack</span><span className="num text-muted">₹ 499 for 10 reveals</span></div>
          <div className="flex justify-between"><span className="text-bone">Monthly plan</span><span className="num text-muted">₹ 1,499 per month, unlimited</span></div>
          <p className="text-[11px] text-muted">Prices are assumptions for this demo, not results. Sellers pay nothing.</p>
        </div>
        <p className="rounded-lg border border-warn/40 bg-warn/10 p-2.5 text-[12px] text-warn">
          Mock screen: no payment is taken. The button below only switches this demo account to unlimited reveals.
        </p>
        {error && <p className="text-[12px] text-error">{error}</p>}
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="rounded-full border border-line px-4 py-1.5 text-[13px] text-muted hover:text-bone">Not now</button>
          <button onClick={upgrade} disabled={busy}
            className="rounded-full bg-signal px-5 py-1.5 text-[13px] font-semibold text-ink disabled:opacity-40">
            {busy ? "Switching…" : "Switch to the mock paid plan"}
          </button>
        </div>
      </div>
    </div>
  );
}


// ─── Exception dialog ──────────────────────────────────────────────────────

/** Case check 2 in the app: a late or short seller is only recommended with a written reason and a named approver. */
function ExceptionModal({ supplier, reason: why, giveUp, defaultApprover, onClose, onSave }: {
  supplier: string; reason: string; giveUp: number | null; defaultApprover: string;
  onClose: () => void; onSave: (reason: string, approver: string) => Promise<void>;
}) {
  const [reason, setReason] = useState("");
  const [approver, setApprover] = useState(defaultApprover);
  const [touched, setTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const blank = !reason.trim() || !approver.trim();
  const save = async () => {
    setTouched(true);
    if (blank) return;                                  // a blank reason or approver never unlocks the gate
    setBusy(true); setError(null);
    try { await onSave(reason.trim(), approver.trim()); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not save the exception."); setBusy(false); }
  };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/80 backdrop-blur-md p-4">
      <div className="w-full max-w-md space-y-4 rounded-2xl border border-line bg-surface p-6 shadow-2xl">
        <div className="flex items-center justify-between">
          <h3 className="display text-xl text-bone">Approve an exception</h3>
          <button onClick={onClose} className="text-muted hover:text-bone"><X size={18} /></button>
        </div>
        <p className="text-[13px] text-muted">
          <strong className="text-bone">{supplier}</strong> is not recommended: {why}.
          {giveUp !== null && <> Ordering from them would save <span className="num text-bone">{inr(giveUp)}</span>.</>}
          {" "}A written reason and a named approver are required, and both go on the saved record.
        </p>
        <div>
          <label className="label mb-1.5 block text-bone">Reason</label>
          <textarea value={reason} onChange={e => setReason(e.target.value)} rows={3}
            placeholder="e.g. Saves the difference and our stock covers the two extra days"
            className={`w-full rounded-lg border bg-raised px-3 py-2 text-[13px] text-bone ${touched && !reason.trim() ? "border-error" : "border-line"}`} />
          {touched && !reason.trim() && <p className="mt-1 text-[12px] text-error">A blank reason cannot unlock this seller.</p>}
        </div>
        <div>
          <label className="label mb-1.5 block text-bone">Approved by</label>
          <input value={approver} onChange={e => setApprover(e.target.value)}
            className={`w-full rounded-lg border bg-raised px-3 py-2 text-[14px] text-bone ${touched && !approver.trim() ? "border-error" : "border-line"}`} />
          {touched && !approver.trim() && <p className="mt-1 text-[12px] text-error">Name the person who approves it.</p>}
        </div>
        {error && <p className="text-[12px] text-error">{error}</p>}
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="rounded-full border border-line px-4 py-1.5 text-[13px] text-muted hover:text-bone">Cancel</button>
          <button onClick={save} disabled={busy}
            className="rounded-full bg-signal px-5 py-1.5 text-[13px] font-semibold text-ink disabled:opacity-40">
            {busy ? "Saving…" : "Record exception"}
          </button>
        </div>
      </div>
    </div>
  );
}


// ─── Why this supplier ─────────────────────────────────────────────────────

type EngineRow = NonNullable<ReturnType<typeof evaluate>["winner"]>;

/** Gates as pass/fail rows, then each number tagged observed, derived or assumed. Slider-aware. */
function WhyCard({ row, qty, needInDays, mode }: { row: EngineRow; qty: number; needInDays: number; mode: Mode }) {
  const q = row.quote;
  const unit = q.packPrice / (q.packSize ?? 1);
  const gates: Array<{ label: string; pass: boolean; note?: string }> = [
    { label: "Same item as the request", pass: true },
    { label: "Pack size known", pass: q.packSize !== null },
    row.approved
      ? { label: "Arrives by the date", pass: true, note: `${q.leadDays} days, needed in ${needInDays}: passed with a written exception` }
      : { label: "Arrives by the date", pass: q.leadDays <= needInDays, note: `${q.leadDays} days, needed in ${needInDays}` },
    row.fillQty !== undefined
      ? { label: "Can supply the full quantity", pass: row.approved, note: `stock covers ${row.fillQty} of ${qty}` }
      : { label: "Can supply the full quantity", pass: true },
  ];
  const facts: Array<{ label: string; value: string; tag: "observed" | "derived" | "assumed" }> = [
    { label: "Pack price", value: inr(q.packPrice), tag: "observed" },
    { label: "Freight", value: inr(q.freight), tag: "observed" },
    { label: "Lead time", value: `${q.leadDays} days`, tag: "observed" },
    { label: "Packs ordered", value: String(row.packs), tag: "derived" },
    { label: "Landed cost", value: inr(row.landed ?? 0), tag: "derived" },
    { label: "Cost per usable unit", value: inr((row.landed ?? 0) / Math.max(qty, 1)), tag: "derived" },
    { label: "Cash tied up in extra units", value: inr(row.overbuy * unit), tag: "derived" },
    { label: "Tax basis", value: "compared as quoted", tag: "assumed" },
    ...(mode === "balanced" ? [{ label: "Balanced tolerance", value: "5%", tag: "assumed" as const }] : []),
  ];
  return (
    <div className="space-y-3 rounded-2xl border border-line bg-surface/80 p-5 shadow-sm">
      <h3 className="display text-base font-semibold text-bone">Why {q.supplier}</h3>
      <ul className="space-y-1.5">
        {gates.map(g => (
          <li key={g.label} className="flex items-start gap-2 text-[13px]">
            <span className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${g.pass ? "bg-success/20 text-success" : "bg-error/20 text-error"}`}>
              {g.pass ? "✓" : "✕"}
            </span>
            <span className="text-bone">{g.label}{g.note && <span className="text-muted"> · {g.note}</span>}</span>
          </li>
        ))}
      </ul>
      <table className="w-full text-left text-[12px]">
        <tbody>
          {facts.map(f => (
            <tr key={f.label} className="border-t border-line/60">
              <td className="py-1 text-muted">{f.label}</td>
              <td className="num py-1 text-bone">{f.value}</td>
              <td className="py-1 text-right"><FactTag tag={f.tag} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
