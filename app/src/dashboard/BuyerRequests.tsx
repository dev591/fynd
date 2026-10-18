import { useState } from "react";
import { Ambient } from "../components/Ambient";
import { motion } from "motion/react";
import { Link, useNavigate } from "react-router-dom";
import { Plus, ArrowRight, Package, AlertTriangle } from "lucide-react";
import { useApiPoll } from "../lib/useApi";
import { AccountMenu } from "../components/AccountMenu";
import { NoticeBell } from "../components/NoticeBell";
import { createSampleRequest, getRFQs, getSavings, type RFQDTO } from "../api/client";

export function BuyerRequests() {
  const navigate = useNavigate();
  const [sampling, setSampling] = useState(false);
  const [sampleError, setSampleError] = useState<string | null>(null);
  const trySample = async () => {
    setSampling(true); setSampleError(null);
    try {
      const r = await createSampleRequest();
      navigate(`/app/compare/${r.id}`);
    } catch (e) {
      setSampleError(e instanceof Error ? e.message : "Could not create the sample request.");
      setSampling(false);
    }
  };

  const { data: rfqs, loading, error } = useApiPoll<RFQDTO[]>(
    () => getRFQs(), 3000, [],
  );

  const { data: savings } = useApiPoll(() => getSavings(), 5000, []);

  return (
    <div className="landing grain isolate min-h-screen bg-ink text-bone pb-16">
      <Ambient />
      {/* Header */}
      <header className="sticky top-0 z-30 border-b border-line bg-ink/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6">
          <Link to="/" className="flex items-center gap-1.5 rounded-full border border-line bg-surface/80 px-3 py-1.5 text-[12px] font-medium text-muted hover:text-bone">
            <span>Story</span>
          </Link>
          <div>
            <span className="display text-base font-semibold text-bone">Crossover Desk</span>
            <span className="label ml-2 text-signal">BUYER</span>
          </div>
          <div className="flex items-center gap-3">
            <Link to="/supplier" className="rounded-full border border-line bg-raised px-3 py-1.5 text-[12px] font-medium text-bone hover:border-signal/50 hover:text-signal">
              Supplier Portal
            </Link>
            <NoticeBell />
            <AccountMenu />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6 space-y-6">
        {/* Banner */}
        <div className="rounded-2xl border border-line bg-surface/70 p-5 backdrop-blur-sm shadow-sm">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <span className="label text-signal">YOUR REQUESTS</span>
              <h1 className="display mt-1 text-[clamp(1.6rem,3.4vw,2.4rem)] text-bone">What do you need today?</h1>
              <p className="text-[13px] text-muted mt-0.5">
                Say it once. Sellers who stock it quote, and we show you the best one in plain words.
              </p>
            </div>
            <Link
              to="/app/new"
              className="flex items-center gap-2 rounded-full bg-signal px-5 py-2.5 text-[14px] font-semibold text-ink transition-all hover:opacity-95 active:scale-95"
            >
              <Plus size={16} /><span>New Request</span>
            </Link>
          </div>
        </div>

        {savings && savings.decided_count > 0 && (
          <div className="rounded-xl border border-success/30 bg-success/10 px-4 py-2.5 text-[13px] text-bone">
            Saved <strong className="num text-success">₹{Math.round(savings.total).toLocaleString("en-IN")}</strong> versus
            spreadsheet picks across {savings.decided_count} decided request{savings.decided_count === 1 ? "" : "s"}
            <span className="text-muted"> ({savings.label})</span>
          </div>
        )}

        {/* States */}
        {loading && !rfqs ? (
          <div className="rounded-2xl border border-line bg-surface/80 p-8 text-center">
            <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-line border-t-signal" />
            <p className="mt-3 text-[13px] text-muted">Loading requests…</p>
          </div>
        ) : error ? (
          <div className="rounded-2xl border border-error/40 bg-error/10 p-6 text-center space-y-3">
            <AlertTriangle size={28} className="mx-auto text-error" />
            <h2 className="display text-lg text-bone">Cannot reach the server</h2>
            <p className="text-[13px] text-muted">Make sure the backend is running on port 8000.</p>
            <code className="block rounded-lg bg-raised px-3 py-2 text-[12px] text-bone">{error}</code>
          </div>
        ) : !rfqs || rfqs.length === 0 ? (
          <div className="rounded-2xl border border-line bg-surface/80 p-8 text-center space-y-4">
            <Package size={40} className="mx-auto text-muted" />
            <div>
              <h3 className="display text-lg text-bone">No requests yet</h3>
              <p className="text-[13px] text-muted max-w-sm mx-auto mt-1">
                A request for quotation (RFQ) asks every seller who stocks an item to quote.
                The Crossover engine compares them on total landed cost, not sticker price.
              </p>
            </div>
            <div className="flex flex-wrap items-center justify-center gap-3">
              <Link
                to="/app/new"
                className="inline-flex items-center gap-2 rounded-full bg-signal px-5 py-2.5 text-[14px] font-semibold text-ink hover:opacity-95"
              >
                <Plus size={16} /><span>Create your first request</span>
              </Link>
              <button type="button" onClick={trySample} disabled={sampling}
                className="inline-flex items-center gap-2 rounded-full border border-line bg-raised px-5 py-2.5 text-[14px] font-medium text-bone hover:border-signal/50 disabled:opacity-40">
                {sampling ? "Setting up…" : "Try a sample request"}
              </button>
            </div>
            {sampleError && <p className="text-[12px] text-error">{sampleError}</p>}
          </div>
        ) : (
          /* Requests as live cards: a ring fills as sellers reply */
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {rfqs.map((rfq, i) => (
              <motion.div key={rfq.id} initial={{ opacity: 0, y: 22 }} animate={{ opacity: 1, y: 0 }}
                transition={{ type: "spring", stiffness: 240, damping: 26, delay: Math.min(i, 9) * 0.05 }}>
                <Link to={`/app/compare/${rfq.id}`}
                  className="group relative flex h-full flex-col rounded-2xl border border-line bg-surface p-5 transition-all hover:-translate-y-1 hover:border-signal/50 hover:shadow-[0_22px_40px_-28px_var(--signal)]">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="num text-[12px] text-muted">{rfq.qty} units</p>
                      <h3 className="truncate text-[18px] font-semibold text-bone">{rfq.item}</h3>
                    </div>
                    <ReplyRing replied={rfq.quote_count} asked={rfq.matched_count} live={rfq.status === "Open"} />
                  </div>
                  <p className="mt-2 text-[13px] text-muted">Needed in {rfq.need_in_days} day{rfq.need_in_days === 1 ? "" : "s"}{rfq.note ? ` · “${rfq.note}”` : ""}</p>
                  <div className="mt-auto flex items-center justify-between pt-4">
                    <span className={`flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-medium ${
                      rfq.status === "Open" ? "bg-live/15 text-live" : rfq.status === "Decided" ? "bg-success/15 text-success" : "bg-raised text-muted"}`}>
                      {rfq.status === "Open" && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-live" />}
                      {rfq.status === "Open" ? "Taking quotes" : rfq.status}
                    </span>
                    <span className="flex items-center gap-1 text-[13px] font-medium text-signal">
                      {rfq.status === "Decided" ? "See decision" : "Compare"}
                      <ArrowRight size={14} className="transition-transform group-hover:translate-x-1" />
                    </span>
                  </div>
                </Link>
              </motion.div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

/** Fills as sellers reply. Live requests breathe. */
function ReplyRing({ replied, asked, live }: { replied: number; asked: number; live: boolean }) {
  const r = 20, c = 2 * Math.PI * r, k = asked > 0 ? Math.min(1, replied / asked) : 0;
  return (
    <div className="relative grid h-14 w-14 shrink-0 place-items-center" title={`${replied} of ${asked} sellers replied`}>
      {live && <span className="absolute inset-1 animate-ping rounded-full bg-live/10" />}
      <svg viewBox="0 0 48 48" className="absolute inset-0 -rotate-90">
        <circle cx="24" cy="24" r={r} fill="none" stroke="var(--line)" strokeWidth="4" />
        <motion.circle cx="24" cy="24" r={r} fill="none" stroke="var(--live)" strokeWidth="4" strokeLinecap="round"
          strokeDasharray={c} initial={{ strokeDashoffset: c }} animate={{ strokeDashoffset: c * (1 - k) }}
          transition={{ duration: 0.9, ease: "easeOut" }} />
      </svg>
      <span className="num relative text-[12px] font-semibold text-bone">{replied}/{asked}</span>
    </div>
  );
}
