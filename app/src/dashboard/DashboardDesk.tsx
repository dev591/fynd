import { useState, useMemo } from "react";
import { Link } from "react-router-dom";
import {
  ArrowLeft,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  FileSpreadsheet,
  TrendingDown,
  Sparkles,
  Target,
  QrCode,
  Share2,
  ExternalLink,
  MessageSquare,
  Check,
} from "lucide-react";
import { QUOTES, NEED } from "../landing/fixture";
import { evaluate, inr, negotiation, type Quote } from "../landing/engine";
import { CostChart } from "../landing/CostChart";
import { QtyControl } from "../landing/QtyControl";
import { useSupplierStore } from "../supplier/supplierStore";
import { SupplierChat } from "../supplier/components/SupplierChat";
import type { Profile } from "../wizard/types";

export function DashboardDesk() {
  const store = useSupplierStore();
  const storeData = store.getState();

  const [profile] = useState<Profile>(() => {
    try {
      const saved = localStorage.getItem("crossover_active_profile");
      if (saved) return JSON.parse(saved);
    } catch {
      // fallback
    }
    return {
      id: "usr_demo",
      role: "buyer",
      full_name: "Ramesh Sharma",
      email: "ramesh.sharma@fanworks.in",
      phone: "9820144556",
      company: "FanWorks Precision Manufacturing",
      business_type: "manufacturer",
      state: "Maharashtra",
      city: "Pune",
      categories: ["fasteners", "metals"],
      gstin: "27ABCDE1234F1Z5",
      pan_masked: "ABCDE1234F",
      verification: {
        email: true,
        tax_ids_consistent: true,
        registry: "demo",
      },
      buyer: {
        gst_claimable: true,
        spend_band: "₹20L to 1Cr",
        need_by_buffer_days: 5,
      },
    };
  });

  const [qty, setQty] = useState(NEED.qty);
  const [sheetMode, setSheetMode] = useState(false);
  const [showQrModal, setShowQrModal] = useState(false);
  const [chatSupplierId, setChatSupplierId] = useState<string | null>(null);
  const [copiedLink, setCopiedLink] = useState(false);
  const [targetSuccessId, setTargetSuccessId] = useState<string | null>(null);

  // Dynamic quotes: seamlessly overlay any revised quote from the supplier store!
  const liveQuotes: Quote[] = useMemo(() => {
    return QUOTES.map((base) => {
      const versions = storeData.quotes[base.id];
      if (versions && versions.length > 0) {
        const latest = versions[versions.length - 1];
        return {
          ...base,
          packPrice: latest.packPrice,
          packSize: latest.packSize,
          freight: latest.freight,
          leadDays: latest.leadDays,
          moq: latest.moq ?? base.moq,
          raw: `${inr(latest.packPrice)}/pack (${latest.packSize} pcs) + ${inr(latest.freight)} delivery (v${latest.version})`,
        };
      }
      return base;
    });
  }, [storeData.quotes]);

  const evaluation = useMemo(
    () => evaluate(liveQuotes, { ...NEED, qty }),
    [liveQuotes, qty]
  );

  const winner = evaluation.winner;

  // Send target concession to runner-up supplier
  const handleSendTarget = (loserId: string, cutNeeded: number, targetFreight?: number, targetPerUnit?: number) => {
    store.sendTarget(loserId, {
      cutNeeded,
      targetFreight,
      targetPerUnit,
      concessionType: targetFreight !== undefined ? "freight" : "unit_price",
      message:
        targetFreight !== undefined
          ? `Cut freight to ₹${targetFreight} or below and you win this order.`
          : `Cut unit price by ₹${targetPerUnit} to match the winning landed cost.`,
    });

    setTargetSuccessId(loserId);
    setTimeout(() => setTargetSuccessId(null), 3000);
  };

  const handleCopyInviteLink = () => {
    const url = `${window.location.origin}/supplier/quote`;
    navigator.clipboard?.writeText(url);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2000);
  };

  return (
    <div className="landing grain min-h-screen bg-ink text-bone pb-16">
      {/* Top Navigation */}
      <header className="sticky top-0 z-30 border-b border-line bg-ink/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            <Link
              to="/"
              className="flex items-center gap-1.5 rounded-full border border-line bg-surface/80 px-3 py-1.5 text-[12px] font-medium text-muted hover:text-bone"
            >
              <ArrowLeft size={13} />
              <span>Story</span>
            </Link>
            <div className="h-4 w-px bg-line/60" />
            <div>
              <span className="display text-base font-semibold text-bone">
                Crossover Desk
              </span>
              <span className="label ml-2 text-signal">BUYER COMPARE ENGINE</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setShowQrModal(true)}
              className="flex items-center gap-1.5 rounded-full border border-signal/40 bg-signal/15 px-3 py-1.5 text-[12px] font-semibold text-signal hover:bg-signal hover:text-ink transition-all active:scale-95"
            >
              <QrCode size={14} />
              <span>Invite Supplier (QR)</span>
            </button>

            <Link
              to="/supplier"
              className="hidden sm:flex items-center gap-1 rounded-full border border-line bg-raised px-3 py-1.5 text-[12px] font-medium text-bone hover:border-signal/50 hover:text-signal transition-colors"
            >
              <span>Seller Portal</span>
              <ExternalLink size={12} />
            </Link>
          </div>
        </div>
      </header>

      {/* Main Desk Content */}
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 space-y-6">
        {/* Banner with Profile & Active Policies */}
        <div className="rounded-2xl border border-line bg-surface/70 p-5 backdrop-blur-sm shadow-sm">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <span className="label text-signal">BUYER OPERATIONS</span>
                <span className="text-muted">·</span>
                <span className="text-[13px] text-muted">
                  Logged in as <strong className="text-bone">{profile.full_name}</strong> ({profile.company})
                </span>
              </div>
              <h1 className="display text-2xl text-bone mt-1">
                Quote Comparison & Negotiation Desk
              </h1>
            </div>

            {/* Verification & Engine Policy Badges */}
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1 rounded-full border border-live/30 bg-live/15 px-2.5 py-0.5 text-[11px] font-medium text-live">
                <CheckCircle2 size={12} /> Email Verified
              </span>
              <span className="inline-flex items-center gap-1 rounded-full border border-live/30 bg-live/15 px-2.5 py-0.5 text-[11px] font-medium text-live">
                <ShieldCheck size={12} /> Tax Verified
              </span>
              <span className="inline-flex items-center gap-1 rounded-full border border-bone/20 bg-raised px-2.5 py-0.5 text-[11px] font-medium text-bone">
                <Sparkles size={12} className="text-signal" /> ITC Ex-GST Policy Active
              </span>
            </div>
          </div>
        </div>

        {/* 2-Column Layout: Quotes Table on Left vs Cost Curves & Negotiation on Right */}
        <div className="grid gap-6 lg:grid-cols-[1.25fr_1fr]">
          {/* Left: Supplier Quotes Comparison */}
          <div className="space-y-4">
            <div className="rounded-2xl border border-line bg-surface/70 p-5 backdrop-blur-sm space-y-4 shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="display text-lg text-bone">Live Quote Comparison</h2>
                  <p className="text-[13px] text-muted">
                    Item: <strong className="text-bone">{NEED.item}</strong> · Needed within {NEED.needInDays} days
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setSheetMode((s) => !s)}
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
              </div>

              {/* Quotes Cards */}
              <div className="space-y-3">
                {evaluation.rows.map((row) => {
                  const isWin = winner?.quote.id === row.quote.id;
                  const isBlocked = row.status === "blocked";
                  const isLate = row.status === "exception";
                  const quoteVersions = storeData.quotes[row.quote.id];
                  const latestVer = quoteVersions ? quoteVersions.length : 1;

                  return (
                    <div
                      key={row.quote.id}
                      className={`rounded-xl border p-4 transition-all ${
                        isWin
                          ? "border-signal bg-signal/10 ring-1 ring-signal/40 shadow-sm"
                          : isBlocked
                          ? "border-line/40 bg-surface/40 opacity-70"
                          : "border-line bg-surface/90"
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-bone">
                              {row.quote.supplier}
                            </span>
                            <span className="label text-muted">via {row.quote.channel}</span>
                            {latestVer > 1 && (
                              <span className="rounded bg-live/20 text-live px-1.5 py-0.2 text-[10px] font-bold">
                                revised v{latestVer}
                              </span>
                            )}
                            {isWin && (
                              <span className="rounded-full bg-signal px-2 py-0.5 text-[10px] font-bold text-ink uppercase tracking-wide">
                                WINNER · LOWEST LANDED
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
                          <p className="mt-1 font-mono text-[13px] text-muted">
                            "{row.quote.raw}"
                          </p>
                        </div>

                        <div className="text-right">
                          <p className="label text-muted">Total Landed</p>
                          <p className={`num text-lg font-bold ${isWin ? "text-signal" : "text-bone"}`}>
                            {row.landed !== null ? inr(row.landed) : "Undefined"}
                          </p>
                        </div>
                      </div>

                      {/* Calculation Breakdown & Negotiation CTA */}
                      {!isBlocked && row.landed !== null && (
                        <div className="mt-3 flex flex-wrap items-center justify-between border-t border-line/60 pt-2.5 text-[12px] text-muted">
                          <div className="flex items-center gap-3">
                            <span>
                              Order: <strong className="text-bone">{row.packs} packs</strong> ({row.units} units)
                            </span>
                            <span>·</span>
                            <span>Freight: {inr(row.quote.freight)}</span>
                            {row.overbuy > 0 && (
                              <span className="text-warn">
                                +{row.overbuy} extra bolt inventory
                              </span>
                            )}
                          </div>

                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              onClick={() => setChatSupplierId(row.quote.id)}
                              className="flex items-center gap-1 rounded-full border border-line px-2.5 py-0.5 text-[11px] hover:text-bone hover:border-signal/50"
                            >
                              <MessageSquare size={11} />
                              <span>Chat</span>
                            </button>
                          </div>
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
                onReset={() => setQty(NEED.qty)}
              />
            </div>
          </div>

          {/* Right Column: Cost Curves + The Negotiate Panel (PDF Page 2 requirement) */}
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
                  <TrendingDown size={14} />
                  <span>Crosses at 150 units</span>
                </div>
              </div>

              <div className="rounded-xl border border-line bg-surface p-3">
                <CostChart qty={qty} winnerId={winner?.quote.id} />
              </div>
            </div>

            {/* The Negotiate Panel (PDF Page 2 requirement) */}
            <div className="rounded-2xl border border-line bg-surface/80 p-5 backdrop-blur-sm space-y-4 shadow-sm">
              <div className="flex items-center justify-between border-b border-line/60 pb-3">
                <div className="flex items-center gap-2">
                  <Target size={16} className="text-signal" />
                  <h3 className="display text-base font-semibold text-bone">
                    Live Negotiate Panel
                  </h3>
                </div>
                <span className="label text-muted">AI & Engine Concessions</span>
              </div>

              <p className="text-[13px] text-muted leading-relaxed">
                Send exact concession targets to runners-up. If the supplier accepts, the winner updates on your screen in real time.
              </p>

              <div className="space-y-3">
                {evaluation.rows
                  .filter((r) => r.quote.id !== winner?.quote.id && r.status === "eligible" && r.landed !== null)
                  .map((loser) => {
                    const neg = winner ? negotiation(loser, winner) : null;
                    if (!neg) return null;
                    const sent = targetSuccessId === loser.quote.id || storeData.targets[loser.quote.id]?.status === "pending";

                    return (
                      <div
                        key={loser.quote.id}
                        className="rounded-xl border border-line bg-raised/30 p-3.5 space-y-2.5"
                      >
                        <div className="flex items-start justify-between">
                          <div>
                            <span className="font-semibold text-bone text-[13px]">
                              {loser.quote.supplier}
                            </span>
                            <span className="num text-muted ml-2 text-[12px]">
                              (Landed: {inr(loser.landed!)})
                            </span>
                          </div>
                          <span className="num text-warn text-[12px] font-bold">
                            Gap: {inr(neg.cut)}
                          </span>
                        </div>

                        <p className="text-[12px] text-muted">
                          {neg.freight !== null ? (
                            <>
                              Winning concession: <strong>Cut freight from ₹{loser.quote.freight} to ₹{loser.quote.freight - neg.freight}</strong>.
                            </>
                          ) : (
                            <>
                              Winning concession: <strong>Cut unit price by ₹{neg.perUnit}/unit</strong>.
                            </>
                          )}
                        </p>

                        <div className="flex items-center justify-between pt-1">
                          <button
                            type="button"
                            disabled={sent}
                            onClick={() =>
                              handleSendTarget(
                                loser.quote.id,
                                neg.cut,
                                neg.freight !== null ? loser.quote.freight - neg.freight : undefined,
                                neg.perUnit
                              )
                            }
                            className={`flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-[12px] font-semibold transition-all ${
                              sent
                                ? "border border-live/40 bg-live/20 text-live"
                                : "bg-signal text-ink hover:opacity-90 active:scale-95"
                            }`}
                          >
                            {sent ? (
                              <>
                                <Check size={12} strokeWidth={2.5} />
                                <span>Target Active on Supplier Screen</span>
                              </>
                            ) : (
                              <>
                                <Target size={12} />
                                <span>
                                  Send Target ({neg.freight !== null ? `₹${loser.quote.freight - neg.freight} Freight` : `₹${neg.perUnit} Unit`})
                                </span>
                              </>
                            )}
                          </button>

                          <Link
                            to={`/supplier/quote`}
                            target="_blank"
                            className="text-[11px] text-muted underline hover:text-bone flex items-center gap-1"
                          >
                            <span>Open as Supplier</span>
                            <ExternalLink size={10} />
                          </Link>
                        </div>
                      </div>
                    );
                  })}
              </div>
            </div>

            {/* Direct Chat Flyout if opened */}
            {chatSupplierId && (
              <SupplierChat
                messages={store.getMessages(chatSupplierId)}
                currentRole="buyer"
                currentUserName={profile.full_name}
                onSendMessage={(text) =>
                  store.sendMessage(chatSupplierId, "buyer", text, profile.full_name)
                }
              />
            )}
          </div>
        </div>
      </main>

      {/* QR Moment Modal (PDF Page 2 & 7 requirement) */}
      {showQrModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/80 backdrop-blur-md p-4">
          <div className="w-full max-w-sm rounded-2xl border border-line bg-surface p-6 shadow-2xl text-center space-y-4">
            <h3 className="display text-xl text-bone">Invite Supplier to Quote</h3>
            <p className="text-[13px] text-muted">
              Suppliers can quote in under 1 minute from their phone with no login required.
            </p>

            {/* Stylized QR Code Graphic */}
            <div className="mx-auto w-48 h-48 rounded-xl border border-line bg-raised p-3 flex flex-col items-center justify-center">
              <QrCode size={130} className="text-bone" />
              <span className="num text-[10px] text-muted mt-2">M10 bolt · 100 units</span>
            </div>

            <div className="space-y-2">
              <button
                type="button"
                onClick={handleCopyInviteLink}
                className="w-full flex items-center justify-center gap-2 rounded-full border border-line bg-raised py-2 text-[13px] font-medium text-bone hover:border-signal/50"
              >
                <Share2 size={14} />
                <span>{copiedLink ? "Link Copied!" : "Copy Supplier Link"}</span>
              </button>

              <Link
                to="/supplier/quote"
                target="_blank"
                className="w-full flex items-center justify-center gap-2 rounded-full bg-signal py-2.5 text-[13px] font-medium text-ink hover:opacity-95"
              >
                <ExternalLink size={14} />
                <span>Open Supplier Portal in New Tab</span>
              </Link>
            </div>

            <button
              type="button"
              onClick={() => setShowQrModal(false)}
              className="text-[12px] text-muted underline hover:text-bone"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
