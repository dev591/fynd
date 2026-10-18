import { useState, useMemo, useCallback, useEffect, useRef } from "react";
import { Ambient } from "../components/Ambient";
import { LiveToasts, useChangeToasts } from "../components/LiveToasts";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft, AlertTriangle, FileSpreadsheet,
  Target, Check,
  Save, Lock, X, Unlock, ShieldCheck, Upload, Download,
} from "lucide-react";
import { FactTag } from "../components/FactTag";
import { NoticeBell } from "../components/NoticeBell";
import { DeliveryCheck } from "./DeliveryCheck";
import { closesAt, timeLeft, useNow } from "../lib/windowTime";
import { evaluate, giveUp, inr, naivePick, negotiation, type Mode, type Quote } from "../landing/engine";
import { CostChart } from "../landing/CostChart";
import { AnswerCard, PriorityControl, QtyStepper, QuoteBoard, arriveOn } from "./QuoteBoard";
import { AskDesk } from "./AskDesk";
import { SupplierChat } from "../supplier/components/SupplierChat";
import { useApiPoll, useApiOnce } from "../lib/useApi";
import { quotesFromRFQDetails, needFromRFQ } from "../lib/convert";
import {
  getRFQDetails, sendTarget, lockDecision,
  getChatMessages, postChatMessage,
  getSupplierProfileForBuyer, getPaymentConfig, getSummary, getAiOpinion, type AiOpinionDTO, getSplitOptions, lockSplitDecision, type SplitPlanDTO, getFinePrint, type FinePrintFlagDTO, revealSeller, mockUpgrade, RevealsExhausted, recordException, withdrawException, importQuotes, getImportTemplate, draftQuotesFromMessage, type ImportResult, type QuoteDraftRow,
  type DeliveryDTO, type RFQDetailsDTO, type ChatMessageDTO, type SellerPanelDTO, type SellerIdentity, type PlanInfo, type SummaryDTO,
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
  const [chooseId, setChooseId] = useState<string | null>(null);
  const [decisionSaved, setDecisionSaved] = useState(false);
  const [profileSupplierId, setProfileSupplierId] = useState<string | null>(null);
  const [paywall, setPaywall] = useState(false);
  const [exceptionFor, setExceptionFor] = useState<string | null>(null);
  const [showImport, setShowImport] = useState(false);
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

  // Announce quotes that land, revisions, and a change of best, so a quote sent from another laptop is seen here
  const liveSig = useMemo(() => {
    if (!rfq) return undefined;
    const quotes: Record<string, { v: number; landed: number | null }> = {};
    for (const [alias, versions] of Object.entries(apiQuotes)) {
      const last = versions[versions.length - 1];
      if (last) quotes[alias] = { v: versions.length, landed: last.landed_cost ?? null };
    }
    const atAsk = engineQuotes.length ? evaluate(engineQuotes, needFromRFQ(rfq), details?.exceptions ?? {}, (rfq.priority_mode as Mode) ?? "cheapest").winner : null;
    return { quotes, best: atAsk?.quote.id ?? null, bestLanded: atAsk?.landed ?? null };
  }, [apiQuotes, engineQuotes, rfq, details?.exceptions]);
  const toasts = useChangeToasts(liveSig, (a, b) => {
    const out: { tone: "new" | "best"; text: string }[] = [];
    for (const [alias, q] of Object.entries(b.quotes)) {
      const before = a.quotes[alias];
      const money = q.landed != null ? ` ${inr(q.landed)} to your door` : "";
      if (!before) out.push({ tone: "new", text: `${alias} just quoted${money}` });
      else if (q.v > before.v) out.push({ tone: "new", text: `${alias} revised their quote${money ? ":" + money : ""}` });
    }
    if (b.best && b.best !== a.best && a.best) out.push({ tone: "best", text: `New best: ${b.best}${b.bestLanded != null ? ` at ${inr(b.bestLanded)}` : ""}` });
    return out;
  });

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

  // AI's second reading of the quotes, shown beside the engine's pick. Refreshed when the set of quotes changes.
  const quoteSig = Object.values(details?.quotes ?? {}).map(v => v.length).join(",");
  const { data: opinion } = useApiOnce<AiOpinionDTO | null>(
    () => !decidedNow && quoteSig ? getAiOpinion(rfqId ?? "").catch(() => null) : Promise.resolve(null),
    [decidedNow, rfqId, quoteSig],
  );

  // Terms hidden in sellers' notes (advance payment, short price validity...), read when quotes change
  const { data: finePrint } = useApiOnce<Record<string, FinePrintFlagDTO[]>>(
    () => quoteSig ? getFinePrint(rfqId ?? "").catch(() => ({})) : Promise.resolve({}), [rfqId, quoteSig],
  );

  // Best two-seller split, offered next to the normal pick. Refreshed when quotes or signed exceptions change.
  const exceptionSig = Object.keys(details?.exceptions ?? {}).join(",");
  const { data: splitPlan } = useApiOnce<SplitPlanDTO | null>(
    () => !decidedNow && quoteSig ? getSplitOptions(rfqId ?? "").catch(() => null) : Promise.resolve(null),
    [decidedNow, rfqId, quoteSig, exceptionSig],
  );
  const [showSplitModal, setShowSplitModal] = useState(false);
  const handleSaveSplit = async (reason: string, approver: string) => {
    if (!splitPlan) return;
    try {
      await lockSplitDecision(rfqId ?? "", splitPlan.parts[0].quote_id, reason, approver);
      setDecisionSaved(true);
      setShowSplitModal(false);
      refetch();
    } catch (e) {
      console.error("Failed to save the split order:", e);
    }
  };

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
      <div className="landing grain isolate min-h-screen bg-ink text-bone flex items-center justify-center">
      <Ambient />
        <div className="text-center space-y-3">
          <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-line border-t-signal" />
          <p className="text-[13px] text-muted">Loading RFQ comparison…</p>
        </div>
      </div>
    );
  }

  if (error && !details) {
    return (
      <div className="landing grain isolate min-h-screen bg-ink text-bone flex items-center justify-center">
      <Ambient />
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
      <div className="landing grain isolate min-h-screen bg-ink text-bone flex items-center justify-center">
      <Ambient />
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
    <div className="landing grain isolate min-h-screen bg-ink text-bone pb-16">
      <Ambient />
      <LiveToasts toasts={toasts} />
      {/* Top Navigation */}
      <header className="sticky top-0 z-30 border-b border-line bg-ink/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-x-3 gap-y-2 px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            <Link to="/app" className="flex items-center gap-1.5 rounded-full border border-line bg-surface/80 px-3 py-1.5 text-[12px] font-medium text-muted hover:text-bone">
              <ArrowLeft size={13} /><span>Requests</span>
            </Link>
            <div className="h-4 w-px bg-line/60" />
            <div>
              <span className="display text-base font-semibold text-bone">Crossover Desk</span>
              <span className="label ml-2 text-signal">QUOTES</span>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            {details?.plan && <PlanChip plan={details.plan} />}
            <NoticeBell />
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

      <main className="mx-auto max-w-7xl space-y-5 px-4 py-6 sm:px-6">
        {/* What was asked, and how far along the answers are */}
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="label text-muted">{rfq.buyer_company} · <Link to={`/app/request/${rfq.id}`} className="text-signal underline">Details and history</Link></p>
            <h1 className="display text-[clamp(1.7rem,3.6vw,2.6rem)] leading-tight text-bone">
              <span className="num">{rfq.qty}</span> × {rfq.item}
            </h1>
            <p className="text-[13px] text-muted">
              Needed by {arriveOn(rfq.need_in_days)} · {rfq.buyer_city || rfq.buyer_state}{rfq.note ? ` · “${rfq.note}”` : ""}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {details?.activity && details.activity.notified > 0 && (
              <span className="rounded-full border border-line bg-surface px-3 py-1 text-[12px] text-muted">
                <strong className="num text-bone">{details.activity.quoted}</strong> of <span className="num">{details.activity.notified}</span> sellers replied
              </span>
            )}
            <WindowChip rfq={rfq} decided={isDecided} />
            <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${isDecided ? "border-success/30 bg-success/15 text-success" : "border-live/30 bg-live/15 text-live"}`}>
              {isDecided ? "Decided" : "Open"}
            </span>
          </div>
        </div>

        {/* The answer, with the split and the AI's reading beside it */}
        <div className="grid gap-4 lg:grid-cols-[1.7fr_1fr]">
          <div>
            {isDecided && rfq.decision ? (
              <>
            {/* Decision Summary (read-only after decided) */}
              <div className="rounded-2xl border border-success/40 bg-success/10 p-5 space-y-3">
                <div className="flex items-center gap-2">
                  <Lock size={16} className="text-success" />
                  <h3 className="display text-base font-semibold text-success">Decision Saved</h3>
                </div>
                <div className="text-[13px] text-muted space-y-1">
                  <p>Winner: <strong className="text-bone">{(details?.revealed?.[rfq.decision.winner_id as string]?.business_name) ?? (rfq.decision.winner_id as string)}</strong></p>
                  {details?.revealed?.[rfq.decision.winner_id as string]?.phone && (
                    <p className="num">Contact: <span className="text-bone">
                      {details.revealed[rfq.decision.winner_id as string].contact_name} · {details.revealed[rfq.decision.winner_id as string].phone} · {details.revealed[rfq.decision.winner_id as string].email}
                    </span></p>
                  )}
                  {summary?.split && (
                    <p>Split order: <span className="text-bone">{summary.split.parts.map(p => `${p.quote_id} ${p.qty} units (${inr(p.landed)})`).join(" + ")}</span></p>
                  )}
                  <p>Payment: <span className="text-bone">{(rfq.decision.payment_note as string) ?? "Choose how to pay."}</span></p>
                  <Link to={`/app/pay/${rfq.id}`} className="inline-block rounded-full bg-signal px-3.5 py-1 text-[12px] font-semibold text-ink">
                    {(rfq.decision.payment as { status?: string } | undefined)?.status === "choose" ? "Choose how to pay" : "Payment details"}
                  </Link>
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
                <DeliveryCheck rfqId={rfq.id} saved={(rfq.decision as { delivery?: DeliveryDTO }).delivery ?? null} onSaved={() => refetch()} />
                <Link to={`/app/decision/${rfq.id}`} className="inline-block rounded-full border border-success/40 px-3 py-1 text-[12px] font-medium text-success hover:bg-success/10">
                  Open decision one-pager
                </Link>
              </div>
                          </>
            ) : (
              <AnswerCard
                winner={winner} rows={evaluation.rows} pool={evaluation.pool} mode={mode} qty={qty} needInDays={rfq.need_in_days}
                budget={rfq.budget}
                name={winner ? details?.revealed?.[winner.quote.id]?.business_name : undefined}
                decided={isDecided}
                waiting={details?.activity ? Math.max(0, details.activity.notified - details.activity.quoted - details.activity.declined) : 0}
                onChoose={() => { setChooseId(null); setShowDecisionModal(true); }}
              />
            )}
          </div>
          <div className="space-y-4">
            {splitPlan && !decidedNow && (
              <div className="space-y-3 rounded-2xl border border-signal/40 bg-signal/5 p-4 text-[13px]" aria-label="Split order option">
                <div>
                  <p className="label text-signal">SPLIT ORDER OPTION</p>
                  <p className="mt-1 text-bone">
                    {splitPlan.reason === "no_single_supplier_can_fill"
                      ? `No single seller can cover ${rfq.qty} units. Buying from two sellers does.`
                      : `Buying from two sellers costs ${inr(splitPlan.saving ?? 0)} less than the best single seller.`}
                  </p>
                </div>
                <ul className="divide-y divide-line rounded-xl border border-line bg-surface/80">
                  {splitPlan.parts.map(p => (
                    <li key={p.quote_id} className="flex items-center justify-between gap-3 px-3 py-2">
                      <span className="text-bone"><strong>{p.quote_id}</strong> <span className="text-muted">· {p.qty} units ({p.packs} pack{p.packs === 1 ? "" : "s"}) · {p.lead_days} days</span></span>
                      <span className="num font-medium text-bone">{inr(p.landed)}</span>
                    </li>
                  ))}
                  <li className="flex items-center justify-between gap-3 px-3 py-2">
                    <span className="text-muted">Total landed · arrives in {splitPlan.lead_days} days{splitPlan.overbuy > 0 ? ` · ${splitPlan.overbuy} extra unit${splitPlan.overbuy === 1 ? "" : "s"}` : ""}</span>
                    <span className="num text-[15px] font-semibold text-bone">{inr(splitPlan.total_landed)}</span>
                  </li>
                </ul>
                {splitPlan.best_single && (
                  <p className="text-[12px] text-muted">Best single seller: {splitPlan.best_single.quote_id} at {inr(splitPlan.best_single.landed)}.</p>
                )}
                <button type="button" onClick={() => setShowSplitModal(true)}
                  className="rounded-full bg-signal px-4 py-1.5 text-[13px] font-semibold text-ink hover:opacity-95">
                  Order this split
                </button>
                <p className="text-[11px] text-muted">Two orders, two sellers, two reveals. You review everything before it is saved.</p>
              </div>
            )}

            {opinion && !decidedNow && (
              <div className={`rounded-2xl border p-4 text-[13px] ${opinion.agrees ? "border-line bg-surface/80" : "border-warn/50 bg-warn/5"}`}>
                <p className="label text-muted">AI second opinion · {opinion.label}</p>
                <p className="mt-1 text-bone">
                  <strong>{opinion.agrees ? `AI agrees with ${opinion.engine_pick}.` : `AI would pick ${opinion.pick}.`}</strong> {opinion.reason}
                </p>
                {!opinion.agrees && (
                  <p className="mt-1 text-[12px] text-muted">
                    The rules still recommend {opinion.engine_pick}. You decide; both views are saved with your decision.
                  </p>
                )}
              </div>
            )}

            {!splitPlan && !opinion && !isDecided && details?.activity && details.activity.notified > 0 && (
              <div className="rounded-2xl border border-line bg-surface/70 p-4 text-[13px]">
                <p className="label text-muted">Sellers right now</p>
                <div className="mt-2 grid grid-cols-3 gap-2 text-center">
                  {([["Opened it", details.activity.viewed], ["Typing a quote", details.activity.quoting], ["Sent a quote", details.activity.quoted]] as const).map(([l, n]) => (
                    <div key={l} className="rounded-xl bg-raised/50 px-2 py-2.5">
                      <p className="num text-[20px] font-bold text-bone">{n}</p>
                      <p className="text-[11px] text-muted">{l}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Controls: what matters, how many, and the spreadsheet comparison */}
        <div className="space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-line bg-surface/70 px-4 py-3">
            <PriorityControl mode={mode} onMode={setMode} winners={evaluation.winners} />
            <QtyStepper qty={qty} base={rfq.qty} onQty={setQty} />
            <div className="flex items-center gap-2">
              {!isDecided && (
                <button type="button" onClick={() => setShowImport(true)}
                  className="flex items-center gap-1.5 rounded-full border border-line bg-raised px-3 py-1.5 text-[12px] font-medium text-muted hover:text-bone">
                  <Upload size={13} /><span>Import quotes</span>
                </button>
              )}
              <button type="button" onClick={() => setSheetMode(s => !s)} aria-pressed={sheetMode}
                className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[12px] font-medium transition-all ${sheetMode ? "border border-error bg-error/15 text-error" : "border border-line bg-raised text-muted hover:text-bone"}`}>
                <FileSpreadsheet size={13} /><span>{sheetMode ? "Hide spreadsheet view" : "Compare with a spreadsheet"}</span>
              </button>
            </div>
          </div>
          {giveUp(mode, evaluation.winners) && mode !== "cheapest" && (
            <p className="px-1 text-[12px] text-muted">{giveUp(mode, evaluation.winners)}{mode === "balanced" ? " Balanced pays up to 5% more to arrive sooner; the 5% is our assumption." : ""}</p>
          )}
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

        </div>

        {!isDecided && engineQuotes.length > 0 && (
          <AskDesk rfqId={rfq.id} quoteSig={`${quoteSig}|${exceptionSig}`} onApply={(q, m) => { if (q) setQty(q); if (m) setMode(m); }} />
        )}

        {/* Every quote side by side, best first */}
        <section aria-label="All quotes">
          <div className="mb-3 flex items-baseline justify-between">
            <h2 className="display text-xl text-bone">All quotes, best first</h2>
            <span className="text-[12px] text-muted">{engineQuotes.length} quote{engineQuotes.length === 1 ? "" : "s"} · scroll sideways</span>
          </div>
          <QuoteBoard
            rows={evaluation.rows} pool={evaluation.pool} winnerId={winner?.quote.id ?? null} mode={mode} qty={qty}
            needInDays={rfq.need_in_days} details={details} sheetPickId={sheetMode ? sheetPick?.quote.id ?? null : null}
            decided={isDecided} revealingAlias={revealingAlias}
            onReveal={handleReveal} onChat={setChatSupplierId} onException={setExceptionFor} onOpen={setProfileSupplierId}
            onChoose={(id) => { setChooseId(id); setShowDecisionModal(true); }}
            onWithdraw={(id) => withdrawException(rfqId ?? "", id).then(() => refetch())}
            finePrint={finePrint ?? undefined}
          />
        </section>

        {/* Ask a seller to beat the best, and talk to them */}
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="space-y-4">
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
                    .filter(r => r.quote.id !== winner?.quote.id && r.status === "eligible" && r.landed !== null
                      && !details?.quotes?.[r.quote.id]?.slice(-1)[0]?.imported)
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

          </div>
          <div className="space-y-4">
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

        {/* For anyone who wants the working: chart, every number and where it came from */}
        <details className="group rounded-2xl border border-line bg-surface/70 p-5">
          <summary className="flex cursor-pointer list-none items-center justify-between text-[14px] font-medium text-bone">
            <span>How Crossover worked this out</span>
            <span className="text-[12px] text-muted group-open:hidden">Cost chart, every number and where it came from</span>
          </summary>
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-line bg-surface p-4">
              <p className="text-[13px] text-muted">How each seller's total grows with quantity. At <strong className="text-bone">{qty} units</strong>, {winner?.quote.id ?? "no one"} is best.</p>
              <div className="mt-3"><CostChart qty={qty} winnerId={winner?.quote.id} quotes={engineQuotes} late={evaluation.rows.filter(r => r.status === "exception").map(r => r.quote.id)} /></div>
            </div>
            <div className="space-y-4">
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

            </div>
          </div>
        </details>
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
          initialWinnerId={chooseId}
          buyerName={rfq.buyer_name}
          revealed={details?.revealed ?? {}}
          revealing={revealingAlias !== null}
          onReveal={handleReveal}
          onSave={handleSaveDecision}
          onClose={() => setShowDecisionModal(false)}
        />
      )}

      {showSplitModal && splitPlan && (
        <SplitOrderModal
          plan={splitPlan}
          revealed={details?.revealed ?? {}}
          revealing={revealingAlias !== null}
          defaultApprover={rfq.buyer_name}
          onReveal={handleReveal}
          onSave={handleSaveSplit}
          onClose={() => setShowSplitModal(false)}
        />
      )}

      {showImport && (
        <ImportModal
          rfqId={rfqId ?? ""}
          onClose={() => setShowImport(false)}
          onLoaded={() => refetch()}
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
  evaluation, initialWinnerId, buyerName, revealed, revealing, onReveal, onSave, onClose,
}: {
  evaluation: ReturnType<typeof evaluate>;
  initialWinnerId?: string | null;
  buyerName: string;
  revealed: Record<string, SellerIdentity>;
  revealing: boolean;
  onReveal: (alias: string) => Promise<unknown>;
  onSave: (winnerId: string, reason: string, approver: string) => void;
  onClose: () => void;
}) {
  const [winnerId, setWinnerId] = useState(initialWinnerId || evaluation.winner?.quote.id || "");
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


// ─── Split order ───────────────────────────────────────────────────────────

/** Order the engine's two-seller split. Both sellers must be revealed first; the quantities are the server's, not editable. */
function SplitOrderModal({ plan, revealed, revealing, defaultApprover, onReveal, onSave, onClose }: {
  plan: SplitPlanDTO;
  revealed: Record<string, unknown>;
  revealing: boolean;
  defaultApprover: string;
  onReveal: (alias: string) => void;
  onSave: (reason: string, approver: string) => void;
  onClose: () => void;
}) {
  const [reason, setReason] = useState(
    plan.reason === "no_single_supplier_can_fill"
      ? "No single seller could cover the quantity, so the order is split."
      : "Splitting the order is cheaper than any single seller.");
  const [approver, setApprover] = useState(defaultApprover);
  const hidden = plan.parts.filter(p => !revealed[p.quote_id]);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/80 p-4 backdrop-blur-md" role="dialog" aria-label="Order the split">
      <div className="w-full max-w-md space-y-4 rounded-2xl border border-line bg-surface p-6 shadow-2xl">
        <div className="flex items-center justify-between">
          <h3 className="display text-xl text-bone">Order the split</h3>
          <button onClick={onClose} className="text-muted hover:text-bone" aria-label="Close"><X size={18} /></button>
        </div>
        <p className="text-[13px] text-muted">This places two orders and locks the request. Payment is cash on delivery; Crossover never holds money.</p>
        <ul className="space-y-1 text-[13px]">
          {plan.parts.map(p => (
            <li key={p.quote_id} className="flex items-center justify-between rounded-lg border border-line bg-raised/40 px-3 py-2">
              <span className="text-bone">{p.quote_id}: {p.qty} units · <span className="num">{inr(p.landed)}</span></span>
              <span className={revealed[p.quote_id] ? "text-success" : "text-muted"}>{revealed[p.quote_id] ? "Revealed" : "Hidden"}</span>
            </li>
          ))}
        </ul>
        <div>
          <label className="label mb-1.5 block text-bone">Reason</label>
          <textarea value={reason} onChange={e => setReason(e.target.value)} rows={2}
            className="w-full rounded-lg border border-line bg-raised px-3 py-2 text-[13px] text-bone" />
        </div>
        <div>
          <label className="label mb-1.5 block text-bone">Approver</label>
          <input type="text" value={approver} onChange={e => setApprover(e.target.value)}
            className="w-full rounded-lg border border-line bg-raised px-3 py-2 text-[14px] text-bone" />
        </div>
        {hidden.length > 0 && (
          <p className="rounded-lg border border-line bg-raised/40 p-2.5 text-[12px] text-muted">
            You need both sellers' contacts to place the order. Revealing uses one free reveal each, unless you have unlocked them before.
          </p>
        )}
        <div className="flex flex-wrap justify-end gap-2 pt-1">
          <button onClick={onClose} className="rounded-full border border-line px-4 py-1.5 text-[13px] text-muted hover:text-bone">Cancel</button>
          {hidden.length > 0 ? hidden.map(p => (
            <button key={p.quote_id} onClick={() => onReveal(p.quote_id)} disabled={revealing}
              className="flex items-center gap-1.5 rounded-full bg-signal px-4 py-1.5 text-[13px] font-medium text-ink hover:opacity-90 disabled:opacity-40">
              <Unlock size={14} /><span>{revealing ? "Revealing…" : `Reveal ${p.quote_id}`}</span>
            </button>
          )) : (
            <button onClick={() => onSave(reason, approver)} disabled={!reason.trim() || !approver.trim()}
              className="flex items-center gap-1.5 rounded-full bg-signal px-5 py-1.5 text-[13px] font-medium text-ink hover:opacity-90 disabled:opacity-40">
              <Save size={14} /><span>Place split order & lock</span>
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
    ? <>You are on the paid plan, so reveals are unlimited.</>
    : <>You have {plan.reveals_left} of {plan.free_limit} free reveals left. A seller you have already unlocked costs nothing.</>;
}

function PlanChip({ plan }: { plan: PlanInfo }) {
  return (
    <Link to="/app/pricing" className="num rounded-full border border-line bg-surface px-2.5 py-1 text-[12px] text-muted hover:border-signal/60 hover:text-bone"
      title="Reveals unlock a seller's name and contact. See prices.">
      {plan.plan === "pro" ? "Reveals: unlimited (Pro)" : `${plan.reveals_left} reveals left`}
    </Link>
  );
}

/** The paywall is a mock. The upgrade button flips a flag on the demo server; no payment is taken or stored. */
function PaywallModal({ plan, onClose, onUpgraded }: { plan?: PlanInfo; onClose: () => void; onUpgraded: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { data: payCfg } = useApiOnce(() => getPaymentConfig().catch(() => null), []);
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
        {payCfg?.enabled ? (
          <>
            {payCfg.mode === "test" && <p className="rounded-lg border border-live/40 bg-live/10 p-2.5 text-[12px] text-live">Razorpay test mode: no real money moves.</p>}
            <div className="flex justify-end gap-2">
              <button onClick={onClose} className="rounded-full border border-line px-4 py-1.5 text-[13px] text-muted hover:text-bone">Not now</button>
              <Link to="/app/pricing" className="rounded-full bg-signal px-5 py-1.5 text-[13px] font-semibold text-ink">See prices and pay</Link>
            </div>
          </>
        ) : (
          <>
            <p className="rounded-lg border border-warn/40 bg-warn/10 p-2.5 text-[12px] text-warn">
              Payments are not switched on for this server. The button below only switches this demo account to unlimited reveals, with no payment.
            </p>
            {error && <p className="text-[12px] text-error">{error}</p>}
            <div className="flex justify-end gap-2">
              <button onClick={onClose} className="rounded-full border border-line px-4 py-1.5 text-[13px] text-muted hover:text-bone">Not now</button>
              <button onClick={upgrade} disabled={busy} className="rounded-full bg-signal px-5 py-1.5 text-[13px] font-semibold text-ink disabled:opacity-40">
                {busy ? "Switching…" : "Switch to the demo plan"}
              </button>
            </div>
          </>
        )}
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
  const unit = (row.packPrice ?? q.packPrice) / (q.packSize ?? 1);
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
    { label: "Pack price", value: inr(row.packPrice ?? q.packPrice), tag: "observed" },
    { label: "Freight", value: inr(row.freight ?? q.freight), tag: "observed" },
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


// ─── Import quotes (CSV or JSON) ───────────────────────────────────────────

/** Quotes the buyer already has. Good rows load; bad rows are listed by row number and skipped. */
function ImportModal({ rfqId, onClose, onLoaded }: { rfqId: string; onClose: () => void; onLoaded: () => void }) {
  const [text, setText] = useState("");
  const [format, setFormat] = useState<"csv" | "json">("csv");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  // "Paste a message": the model reads it, you check every value, then it goes through the normal import.
  const [mode, setMode] = useState<"file" | "message">("file");
  const [message, setMessage] = useState("");
  const [draft, setDraft] = useState<{ rows: QuoteDraftRow[]; warnings: string[] } | null>(null);
  const [reading, setReading] = useState(false);

  const readMessage = async () => {
    setReading(true); setError(null); setResult(null); setDraft(null);
    const r = await draftQuotesFromMessage(message, rfqId);
    setReading(false);
    if (r.fallback) { setError(r.message ?? "Couldn't read that automatically."); return; }
    setDraft({ rows: r.rows, warnings: r.warnings });
  };
  const editRow = (i: number, field: keyof QuoteDraftRow, value: string) =>
    setDraft(d => d && ({ ...d, rows: d.rows.map((row, j) => j !== i ? row : {
      ...row, [field]: field === "supplier" ? value : value.trim() === "" ? null : Number(value) }) }));
  const importDraft = async () => {
    if (!draft) return;
    setBusy(true); setError(null); setResult(null);
    try {
      const r = await importQuotes(rfqId, "json", JSON.stringify({ quotes: draft.rows }));
      setResult(r);
      if (r.imported > 0) { onLoaded(); setDraft(null); setMessage(""); }
    } catch (e) {
      setError((e instanceof Error ? e.message : "Could not import.").replace(/^API \d+: /, "").replace(/^\{"detail":"?|"?\}$/g, ""));
    } finally {
      setBusy(false);
    }
  };

  const readFile = async (file: File) => {
    const body = await file.text();
    setText(body);
    setFormat(file.name.toLowerCase().endsWith(".json") || /^\s*[\[{]/.test(body) ? "json" : "csv");
    setResult(null); setError(null);
  };
  const template = async () => {
    const t = await getImportTemplate();
    setText(format === "json" ? t.json : t.csv);
    setResult(null); setError(null);
  };
  const run = async () => {
    setBusy(true); setError(null); setResult(null);
    try {
      const r = await importQuotes(rfqId, format, text);
      setResult(r);
      if (r.imported > 0) onLoaded();
    } catch (e) {
      // A rejected file (empty, wrong columns, too big) comes back as one clear sentence.
      const m = e instanceof Error ? e.message : "Could not import.";
      setError(m.replace(/^API \d+: /, "").replace(/^\{"detail":"?|"?\}$/g, ""));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/80 backdrop-blur-md p-4">
      <div className="max-h-[90vh] w-full max-w-2xl space-y-4 overflow-y-auto rounded-2xl border border-line bg-surface p-6 shadow-2xl">
        <div className="flex items-center justify-between">
          <h3 className="display text-xl text-bone">Import quotes you already have</h3>
          <button onClick={onClose} className="text-muted hover:text-bone"><X size={18} /></button>
        </div>
        <p className="text-[13px] text-muted">
          Upload a CSV or JSON file, or paste it. Needed columns: supplier, pack price, lead days. Units per pack, freight,
          minimum order, stock, GST rate and "price includes GST" are optional. A missing pack size is not guessed: that quote is
          blocked as "pack size unknown". These suppliers are yours, so there is nothing to reveal. Crossover has not checked them.
        </p>
        <div role="group" aria-label="How to bring quotes in" className="flex w-fit rounded-full border border-line p-0.5 text-[12px]">
          {([["file", "File or table"], ["message", "Paste a message"]] as const).map(([m, label]) => (
            <button key={m} type="button" aria-pressed={mode === m} onClick={() => { setMode(m); setError(null); setResult(null); }}
              className={`rounded-full px-3 py-1 ${mode === m ? "bg-signal text-ink" : "text-muted hover:text-bone"}`}>{label}</button>
          ))}
        </div>

        {mode === "message" && (
          <div className="space-y-3">
            <p className="text-[12px] text-muted">
              Paste what a supplier sent you on WhatsApp or email. AI reads it into rows; you check and edit every value before
              anything is saved. A price, pack size, freight or lead time that the message doesn't state is left blank, never guessed.
            </p>
            <textarea value={message} onChange={e => { setMessage(e.target.value); setDraft(null); }} rows={5} maxLength={5000}
              placeholder={"Acme Traders: M10 bolt Rs 10 per piece, delivery Rs 200, 3 days"}
              className="w-full rounded-lg border border-line bg-raised px-3 py-2 text-[13px] text-bone" />
            <button type="button" onClick={readMessage} disabled={reading || !message.trim()}
              className="rounded-full border border-signal/50 bg-signal/10 px-4 py-1.5 text-[12px] font-semibold text-signal hover:bg-signal hover:text-ink disabled:opacity-40">
              {reading ? "Reading…" : "Read it"}
            </button>
            {draft && (
              <div className="space-y-2 rounded-lg border border-line bg-raised/30 p-3">
                <p className="label text-muted">Check these before importing</p>
                {draft.rows.length > 0 && (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-[12px]">
                      <thead className="text-muted"><tr>
                        {["Supplier", "Units/pack", "Pack price ₹", "Freight ₹", "Lead days", "MOQ"].map(h => <th key={h} className="pb-1 pr-2 font-medium">{h}</th>)}
                      </tr></thead>
                      <tbody>
                        {draft.rows.map((row, i) => (
                          <tr key={i} className="border-t border-line/60">
                            <td className="py-1 pr-2"><input value={row.supplier ?? ""} onChange={e => editRow(i, "supplier", e.target.value)}
                              aria-label="Supplier" className="w-32 rounded border border-line bg-surface px-1.5 py-1 text-bone" /></td>
                            {(["pack_size", "pack_price", "freight", "lead_days", "moq"] as const).map(f => (
                              <td key={f} className="py-1 pr-2"><input value={row[f] ?? ""} onChange={e => editRow(i, f, e.target.value)} inputMode="decimal"
                                aria-label={f.replace("_", " ")} className="num w-20 rounded border border-line bg-surface px-1.5 py-1 text-bone" /></td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                {draft.warnings.length > 0 && (
                  <ul className="list-disc space-y-0.5 pl-5 text-[12px] text-warn">
                    {draft.warnings.map((w, i) => <li key={i}>{w}</li>)}
                  </ul>
                )}
                {draft.rows.length > 0 && (
                  <button type="button" onClick={importDraft} disabled={busy}
                    className="rounded-full bg-signal px-4 py-1.5 text-[12px] font-semibold text-ink disabled:opacity-40">
                    {busy ? "Importing…" : `Import ${draft.rows.length} quote${draft.rows.length === 1 ? "" : "s"}`}
                  </button>
                )}
              </div>
            )}
          </div>
        )}

        <div className={`flex flex-wrap items-center gap-2 text-[12px] ${mode === "message" ? "hidden" : ""}`}>
          <label className="flex cursor-pointer items-center gap-1.5 rounded-full border border-line bg-raised px-3 py-1 text-bone hover:border-signal/50">
            <Upload size={12} /><span>Choose a file</span>
            <input type="file" accept=".csv,.json,text/csv,application/json" className="hidden"
              onChange={e => { const f = e.target.files?.[0]; if (f) readFile(f); e.target.value = ""; }} />
          </label>
          <button type="button" onClick={template} className="flex items-center gap-1.5 rounded-full border border-line px-3 py-1 text-muted hover:text-bone">
            <Download size={12} /><span>Use the template</span>
          </button>
          <div role="group" aria-label="Format" className="ml-auto flex rounded-full border border-line p-0.5">
            {(["csv", "json"] as const).map(f => (
              <button key={f} type="button" aria-pressed={format === f} onClick={() => setFormat(f)}
                className={`rounded-full px-2.5 py-0.5 uppercase ${format === f ? "bg-signal text-ink" : "text-muted"}`}>{f}</button>
            ))}
          </div>
        </div>
        <textarea value={text} onChange={e => { setText(e.target.value); setResult(null); setError(null); }} rows={9} spellCheck={false}
          hidden={mode === "message"}
          placeholder={"supplier,units_per_pack,pack_price,freight,lead_days\nAcme Traders,1,10,200,3"}
          className="num w-full rounded-lg border border-line bg-raised px-3 py-2 text-[12px] text-bone" />
        {error && <p role="alert" className="rounded-lg border border-error/40 bg-error/10 p-2.5 text-[13px] text-error">{error}</p>}
        {result && (
          <div className="space-y-2 rounded-lg border border-line bg-raised/40 p-3 text-[13px]" aria-live="polite">
            <p className="text-bone">
              <strong>{result.imported}</strong> quote{result.imported === 1 ? "" : "s"} loaded
              {result.skipped_rows > 0 && <>, <strong className="text-warn">{result.skipped_rows}</strong> row{result.skipped_rows === 1 ? "" : "s"} skipped</>}.
            </p>
            {result.errors.length > 0 && (
              <ul className="list-disc space-y-0.5 pl-5 text-[12px] text-warn">
                {result.errors.map((e, i) => <li key={i}>{e.message}</li>)}
              </ul>
            )}
          </div>
        )}
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="rounded-full border border-line px-4 py-1.5 text-[13px] text-muted hover:text-bone">
            {result && result.imported > 0 ? "Done" : "Cancel"}
          </button>
          {mode === "file" && (
            <button onClick={run} disabled={busy || !text.trim()}
              className="rounded-full bg-signal px-5 py-1.5 text-[13px] font-semibold text-ink disabled:opacity-40">
              {busy ? "Importing…" : "Import"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}


// ─── Quote window countdown ────────────────────────────────────────────────

export function WindowChip({ rfq, decided }: { rfq: NonNullable<RFQDetailsDTO["rfq"]>; decided: boolean }) {
  const now = useNow();
  if (decided || !rfq.window_ends_at) return null;
  const left = rfq.window_closed ? null : timeLeft(rfq.window_ends_at, now);
  const label = left
    ? `Quotes close in ${left}`
    : "Window closed. Quoted sellers can still revise";
  return (
    <span className={`num inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${left ? "border-live/30 bg-live/10 text-live" : "border-line bg-raised text-muted"}`}
      title={`Closes ${closesAt(rfq.window_ends_at)}${rfq.demo_timing ? ". Demo timing: shortened for this demo." : ""}`}>
      {label}
    </span>
  );
}
