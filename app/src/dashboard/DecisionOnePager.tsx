import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AlertTriangle, ArrowLeft, Check, Copy, Printer, Share2 } from "lucide-react";
import { useApiOnce } from "../lib/useApi";
import { createShareLink, getSharedSummary, getSummary, type SummaryDTO } from "../api/client";
import { inr } from "../landing/engine";

/** Printable summary of one decision. Buyer view at /app/decision/:rfqId, read-only share view at /share/:token. */
export function DecisionOnePager({ shared = false }: { shared?: boolean }) {
  const { rfqId, token } = useParams<{ rfqId: string; token: string }>();
  const { data: s, loading, error } = useApiOnce<SummaryDTO>(
    () => shared ? getSharedSummary(token || "") : getSummary(rfqId || ""),
    [rfqId, token],
  );
  const [link, setLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [shareError, setShareError] = useState<string | null>(null);

  const share = async () => {
    setShareError(null);
    try {
      const r = await createShareLink(rfqId || "");
      setLink(`${window.location.origin}${r.url}`);
    } catch (e) {
      setShareError(e instanceof Error ? e.message : "Could not create the link.");
    }
  };

  if (loading && !s) {
    return <div className="landing min-h-screen bg-ink p-10 text-center text-[13px] text-muted">Loading…</div>;
  }
  if (error || !s) {
    return (
      <div className="landing min-h-screen bg-ink p-10 text-center space-y-2">
        <AlertTriangle className="mx-auto text-error" />
        <p className="text-[13px] text-muted">{shared ? "This link isn't valid." : "Could not load this decision."}</p>
      </div>
    );
  }

  const pick = s.pick;
  const mode = s.rfq.priority_mode;
  return (
    <div className="onepager landing min-h-screen bg-ink text-bone pb-16">
      <header className="print:hidden sticky top-0 z-30 border-b border-line bg-ink/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3">
          {shared ? <span className="label text-signal">SHARED DECISION · READ ONLY</span> : (
            <Link to={`/app/compare/${s.rfq.id}`} className="flex items-center gap-1.5 rounded-full border border-line bg-surface/80 px-3 py-1.5 text-[12px] text-muted hover:text-bone">
              <ArrowLeft size={13} /><span>Compare</span>
            </Link>
          )}
          <div className="flex items-center gap-2">
            <button type="button" onClick={() => window.print()}
              className="flex items-center gap-1.5 rounded-full border border-line bg-raised px-3 py-1.5 text-[12px] font-medium text-bone">
              <Printer size={13} /><span>Print</span>
            </button>
            {!shared && s.decided && (
              <button type="button" onClick={share}
                className="flex items-center gap-1.5 rounded-full bg-signal px-3 py-1.5 text-[12px] font-semibold text-ink">
                <Share2 size={13} /><span>Create share link</span>
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-3xl space-y-6 px-4 py-6 text-[14px]">
        {link && (
          <div className="print:hidden space-y-1 rounded-xl border border-signal/40 bg-signal/10 p-3">
            <div className="flex items-center gap-2">
              <code className="flex-1 truncate text-[12px]">{link}</code>
              <button type="button" onClick={() => { navigator.clipboard?.writeText(link); setCopied(true); setTimeout(() => setCopied(false), 2000); }}
                className="flex items-center gap-1 rounded-full border border-line bg-surface px-2.5 py-1 text-[11px]">
                {copied ? <Check size={12} /> : <Copy size={12} />}<span>{copied ? "Copied" : "Copy"}</span>
              </button>
            </div>
            <p className="text-[11px] text-muted">Anyone with this link can read this page, including every supplier's quote price. Share it only with people who may see them.</p>
          </div>
        )}
        {shareError && <p className="print:hidden text-[12px] text-error">{shareError}</p>}

        <section className="space-y-1">
          <p className="label text-signal">DECISION ONE-PAGER</p>
          <h1 className="display text-3xl">{s.rfq.item} · <span className="num">{s.rfq.qty}</span> units</h1>
          <p className="text-muted">
            {s.rfq.buyer_company} · needed within {s.rfq.need_in_days} days · priority: <span className="capitalize">{mode}</span> · request came from {s.rfq.source}
          </p>
        </section>

        <section className="rounded-2xl border border-line bg-surface p-5 space-y-2">
          {s.decided && s.decision ? (
            <>
              <p className="label text-success">DECIDED</p>
              <h2 className="display text-2xl">{pick?.supplier} · <span className="num">{pick?.landed != null ? inr(pick.landed) : "—"}</span> landed</h2>
              <p className="text-muted">Reason: {s.decision.reason}</p>
              <p className="text-muted">Approved by {s.decision.approver} on {new Date(s.decision.decided_at).toLocaleString()}</p>
              {s.overrode_engine && s.engine_winner && (
                <p className="text-warn">The approver chose a different supplier than the engine's pick ({s.engine_winner.supplier}).</p>
              )}
            </>
          ) : (
            <>
              <p className="label text-warn">NOT DECIDED YET</p>
              <p className="text-muted">Engine's current pick: {pick?.supplier ?? "none"}</p>
            </>
          )}
        </section>

        {s.savings && (
          <section className="rounded-2xl border border-line bg-surface p-5">
            <p className="label text-muted">Savings vs the spreadsheet pick ({s.savings.label})</p>
            <p className="mt-1">
              Spreadsheet pick: <strong>{s.savings.spreadsheet_pick}</strong> at <span className="num">{inr(s.savings.spreadsheet_landed)}</span>.
              Crossover pick: <strong>{s.savings.crossover_pick}</strong> at <span className="num">{inr(s.savings.crossover_landed)}</span>.
              Difference: <strong className="num text-signal">{inr(s.savings.difference)}</strong>.
            </p>
          </section>
        )}

        <section className="space-y-2">
          <h2 className="display text-xl">Why</h2>
          {s.explainer && (
            <p>
              {s.explainer.text}
              <span className="ml-2 text-[11px] text-muted">
                {s.explainer.source === "ai" ? "(wording by AI; every number checked against the engine)" : "(engine reasons)"}
              </span>
            </p>
          )}
          <ul className="list-disc space-y-1 pl-5 text-muted">
            {s.reasons.map(r => <li key={r}>{r}</li>)}
          </ul>
        </section>

        <section className="space-y-2">
          <h2 className="display text-xl">Winner under each priority</h2>
          <div className="grid grid-cols-3 gap-2 text-[13px]">
            {["cheapest", "fastest", "balanced"].map(m => {
              const w = s.winners_by_mode[m];
              return (
                <div key={m} className={`rounded-xl border p-3 ${m === mode ? "border-signal" : "border-line"} bg-surface`}>
                  <p className="label capitalize text-muted">{m}</p>
                  <p className="font-semibold">{w?.supplier ?? "none"}</p>
                  <p className="num text-muted">{w?.landed != null ? `${inr(w.landed)} · ${w.lead_days}d` : "—"}</p>
                </div>
              );
            })}
          </div>
        </section>

        <section className="space-y-2">
          <h2 className="display text-xl">Gates and exceptions</h2>
          <table className="w-full text-left text-[13px]">
            <thead className="text-muted"><tr><th className="py-1">Supplier</th><th>Status</th><th className="text-right">Landed</th><th className="text-right">Lead</th></tr></thead>
            <tbody>
              {s.rows.map(r => (
                <tr key={r.quote_id} className="border-t border-line align-top">
                  <td className="py-1.5 font-medium">{r.supplier}</td>
                  <td>
                    <span className="capitalize">{r.status}</span>
                    {r.reason && <span className="block text-[12px] text-muted">{r.reason}{r.approved ? " (exception signed)" : ""}</span>}
                  </td>
                  <td className="num text-right">{r.landed != null ? inr(r.landed) : "—"}</td>
                  <td className="num text-right">{r.lead_days}d</td>
                </tr>
              ))}
            </tbody>
          </table>
          {s.cheaper_excluded.length > 0 && (
            <p className="text-[12px] text-warn">Cheaper but excluded: {s.cheaper_excluded.map(r => r.supplier).join(", ")}.</p>
          )}
        </section>

        <section className="space-y-1 border-t border-line pt-4 text-[12px] text-muted">
          <p>Input fingerprint: <code className="num text-bone">{s.fingerprint}</code> (same inputs always give the same fingerprint)</p>
          <p>
            AI calls on this request: {s.ai_calls.length === 0 ? "none" : s.ai_calls.map(c => c.kind).join(", ")}.
            AI proposes wording and drafts; the engine and the catalog decide; a person confirms.
          </p>
          <p>{s.synthetic_note}</p>
        </section>
      </main>
    </div>
  );
}
