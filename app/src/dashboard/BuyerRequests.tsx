import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Plus, ArrowRight, Package, AlertTriangle, Building2 } from "lucide-react";
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
    <div className="landing grain min-h-screen bg-ink text-bone pb-16">
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
              <span className="label text-signal">BUYER OPERATIONS</span>
              <h1 className="display text-2xl text-bone mt-1">Quote Requests</h1>
              <p className="text-[13px] text-muted mt-0.5">
                Raise a request, compare anonymous quotes on landed cost, negotiate, then reveal the seller you choose.
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
            <p className="text-[12px] text-muted">The sample uses synthetic demo sellers and prices.</p>
            {sampleError && <p className="text-[12px] text-error">{sampleError}</p>}
          </div>
        ) : (
          /* Request Rows */
          <div className="space-y-3">
            {rfqs.map(rfq => {
              return (
                <Link
                  key={rfq.id}
                  to={`/app/compare/${rfq.id}`}
                  className="block rounded-xl border border-line bg-surface/90 p-4 transition-all hover:border-signal/30 hover:bg-surface"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-lg text-bone">{rfq.item}</span>
                        <span className="num rounded bg-raised px-2 py-0.5 text-[12px] font-medium text-bone">
                          {rfq.qty} units
                        </span>
                        <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium ${
                          rfq.status === "Open" ? "border border-live/30 bg-live/15 text-live"
                          : rfq.status === "Decided" ? "border border-success/30 bg-success/15 text-success"
                          : "border border-line bg-raised text-muted"
                        }`}>
                          {rfq.status}
                        </span>
                      </div>
                      <p className="text-[13px] text-muted flex items-center gap-2">
                        <Building2 size={13} />
                        <span>{rfq.buyer_company}</span>
                        <span>·</span>
                        <span>Needed within {rfq.need_in_days} days</span>
                      </p>
                      {rfq.note && (
                        <p className="text-[12px] text-muted truncate max-w-lg">"{rfq.note}"</p>
                      )}
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <span className="text-[12px] text-muted">
                        {rfq.matched_count} seller{rfq.matched_count === 1 ? "" : "s"} notified · {rfq.quote_count} quoted
                      </span>
                      <div className="flex items-center gap-1 text-signal text-[13px] font-medium">
                        <span>Compare</span>
                        <ArrowRight size={14} />
                      </div>
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
