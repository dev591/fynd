import { useState, useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  Building2,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  FileSpreadsheet,
  TrendingDown,
  Sparkles,
} from "lucide-react";
import { QUOTES, NEED } from "../landing/fixture";
import { evaluate, inr } from "../landing/engine";
import { CostChart } from "../landing/CostChart";
import { QtyControl } from "../landing/QtyControl";
import type { Profile } from "../wizard/types";

export function DashboardDesk() {
  const navigate = useNavigate();

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

  const evaluation = useMemo(
    () => evaluate(QUOTES, { ...NEED, qty }),
    [qty]
  );

  const winner = evaluation.winner;

  return (
    <div className="landing grain min-h-screen bg-ink text-bone">
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
              <span className="label ml-2 text-signal">LIVE CALCULATOR</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1 text-[12px]">
              <Building2 size={13} className="text-muted" />
              <span className="font-medium text-bone">{profile.company}</span>
              <span className="text-muted">({profile.city})</span>
            </div>

            <button
              type="button"
              onClick={() => navigate("/login")}
              className="rounded-full border border-line px-3 py-1 text-[12px] text-muted hover:bg-raised hover:text-bone transition-colors"
            >
              Switch Role / Edit Profile
            </button>
          </div>
        </div>
      </header>

      {/* Main Desk Content */}
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 space-y-6">
        {/* Banner with Profile & Badges */}
        <div className="rounded-2xl border border-line bg-surface/70 p-5 backdrop-blur-sm">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <span className="label text-signal">{profile.role.toUpperCase()} DESK</span>
                <span className="text-muted">·</span>
                <span className="text-[13px] text-muted">
                  Logged in as <strong className="text-bone">{profile.full_name}</strong>
                </span>
              </div>
              <h1 className="display text-2xl text-bone mt-1">
                Order Recommendation & Quote Audit
              </h1>
            </div>

            {/* Verification Badges */}
            <div className="flex flex-wrap items-center gap-2">
              {profile.verification.email && (
                <span className="inline-flex items-center gap-1 rounded-full border border-live/30 bg-live/15 px-2.5 py-0.5 text-[11px] font-medium text-live">
                  <CheckCircle2 size={12} /> Email Verified
                </span>
              )}
              {profile.verification.tax_ids_consistent && (
                <span className="inline-flex items-center gap-1 rounded-full border border-live/30 bg-live/15 px-2.5 py-0.5 text-[11px] font-medium text-live">
                  <ShieldCheck size={12} /> Tax Verified
                </span>
              )}
              {profile.buyer?.gst_claimable && (
                <span className="inline-flex items-center gap-1 rounded-full border border-bone/20 bg-raised px-2.5 py-0.5 text-[11px] font-medium text-bone">
                  <Sparkles size={12} className="text-signal" /> ITC Ex-GST Active
                </span>
              )}
            </div>
          </div>
        </div>

        {/* 2-Column Layout: Cost Curve vs Quotes Table */}
        <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
          {/* Left: Quotes Breakdown Table */}
          <div className="space-y-4">
            <div className="rounded-2xl border border-line bg-surface/70 p-5 backdrop-blur-sm space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="display text-lg text-bone">Current Inquiries</h2>
                  <p className="text-[13px] text-muted">
                    Item: <strong className="text-bone">M10 bolt</strong> · Needed by Friday (5 days)
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
                    <span>{sheetMode ? "Naive Spreadsheet View" : "Crossover Engine View"}</span>
                  </button>
                </div>
              </div>

              {/* Quotes List */}
              <div className="space-y-3">
                {evaluation.rows.map((row) => {
                  const isWin = winner?.quote.id === row.quote.id;
                  const isBlocked = row.status === "blocked";
                  const isLate = row.status === "exception";

                  return (
                    <div
                      key={row.quote.id}
                      className={`rounded-xl border p-4 transition-all ${
                        isWin
                          ? "border-signal bg-signal/10 ring-1 ring-signal/40"
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
                            Raw quote: "{row.quote.raw}"
                          </p>
                        </div>

                        <div className="text-right">
                          <p className="label text-muted">Total Landed</p>
                          <p className={`num text-lg font-bold ${isWin ? "text-signal" : "text-bone"}`}>
                            {row.landed !== null ? inr(row.landed) : "Undefined"}
                          </p>
                        </div>
                      </div>

                      {/* Calculation Breakdown */}
                      {!isBlocked && row.landed !== null && (
                        <div className="mt-3 flex flex-wrap items-center justify-between border-t border-line/60 pt-2.5 text-[12px] text-muted">
                          <div className="flex items-center gap-3">
                            <span>
                              Order: <strong className="text-bone">{row.packs} packs</strong> ({row.units} units)
                            </span>
                            {row.overbuy > 0 && (
                              <span className="text-warn">
                                +{row.overbuy} extra bolt inventory
                              </span>
                            )}
                          </div>
                          <div>
                            <span>
                              Goods: {inr(row.packs * row.quote.packPrice)} + Freight: {inr(row.quote.freight)}
                            </span>
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

          {/* Right: Interactive Cost Chart */}
          <div className="space-y-4">
            <div className="rounded-2xl border border-line bg-surface/70 p-5 backdrop-blur-sm space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="display text-lg text-bone">Live Crossover Curves</h2>
                  <p className="text-[13px] text-muted">
                    At <strong className="text-bone">{qty} units</strong>, Supplier {winner?.quote.id ?? "None"} is the optimal order.
                  </p>
                </div>
                <div className="flex items-center gap-1.5 text-success text-[13px] font-medium">
                  <TrendingDown size={15} />
                  <span>Crossover at 150 units</span>
                </div>
              </div>

              <div className="rounded-xl border border-line bg-surface p-4">
                <CostChart qty={qty} winnerId={winner?.quote.id} />
              </div>

              <div className="rounded-xl border border-line bg-raised/40 p-4 text-[13px] text-muted leading-relaxed">
                <p>
                  <strong>Why this matters:</strong> Under 150 units, Supplier B's ₹50 freight beats Supplier A's ₹200 freight despite B charging ₹1 more per bolt. At 150 units, the curves cross and Supplier A becomes cheaper.
                </p>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
