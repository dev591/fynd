import { useEffect, useState } from "react";
import { Ambient } from "../components/Ambient";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowLeft, Package, Send, Check, ExternalLink,
} from "lucide-react";
import { IntakePanel } from "./IntakePanel";
import { useApiOnce } from "../lib/useApi";
import { dateFromDays, daysFromToday, tomorrow } from "../lib/dates";
import { useSession } from "../lib/useSession";
import { getLastOrder, getMe, createRFQ, type LastOrderDTO, type PriorityMode, type RFQCreateResponse, type WindowKey } from "../api/client";

const PRIORITY_OPTIONS: { id: PriorityMode; label: string; hint: string }[] = [
  { id: "cheapest", label: "Cheapest", hint: "Lowest landed cost" },
  { id: "fastest", label: "Fastest", hint: "Shortest lead time" },
  { id: "balanced", label: "Balanced", hint: "Fastest within 5% of cheapest" },
];

export function NewRequestForm() {
  const navigate = useNavigate();

  // Form state
  const [item, setItem] = useState("");
  const [qty, setQty] = useState<number | "">("");
  const [budget, setBudget] = useState<number | "">("");        // optional ceiling for this item, in rupees
  const [needBy, setNeedBy] = useState(() => dateFromDays(5));
  const needInDays = daysFromToday(needBy);
  // Last order vs today, once an item is typed. Numbers only; history marked synthetic is demo data.
  const [lastOrder, setLastOrder] = useState<LastOrderDTO | null>(null);
  const [note, setNote] = useState("");
  const [priority, setPriority] = useState<PriorityMode>("cheapest");
  const [windowKey, setWindowKey] = useState<WindowKey | "auto">("auto");     // auto = from the priority
  // Who is asking comes from the signed-in profile, not from a hardcoded buyer.
  const session = useSession();
  const { data: me } = useApiOnce(() => getMe(), []);
  const [buyerCompany, setBuyerCompany] = useState("");
  const [buyerName, setBuyerName] = useState("");
  const [buyerCity, setBuyerCity] = useState("");
  const [buyerState, setBuyerState] = useState("");
  useEffect(() => {
    if (item.trim().length < 3) { setLastOrder(null); return; }
    const t = setTimeout(() => {
      getLastOrder(item.trim(), typeof qty === "number" && qty > 0 ? qty : undefined, needInDays >= 1 ? needInDays : undefined)
        .then(setLastOrder).catch(() => setLastOrder(null));
    }, 450);
    return () => clearTimeout(t);
  }, [item, qty, needInDays]);

  useEffect(() => {
    const p = me?.profile;
    setBuyerCompany(c => c || p?.company || "My company");
    setBuyerName(n => n || p?.full_name || session?.user.email?.split("@")[0] || "Buyer");
    setBuyerCity(c => c || p?.city || "");
    setBuyerState(s => s || p?.state || "");
  }, [me, session]);

  const [submitting, setSubmitting] = useState(false);
  const [created, setCreated] = useState<RFQCreateResponse | null>(null);
  const [createdMore, setCreatedMore] = useState<RFQCreateResponse[]>([]);
  // More items on the same order. Each one becomes its own request, compared on its own.
  type Extra = { item: string; qty: number | ""; budget: number | "" };
  const [extras, setExtras] = useState<Extra[]>([]);
  const budgetOk = (b: number | "") => b === "" || b > 0;
  const extraOk = (x: Extra) => x.item.trim() && typeof x.qty === "number" && x.qty > 0 && budgetOk(x.budget);
  const [orderId, setOrderId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const isValid = item.trim() && typeof qty === "number" && qty > 0 && needInDays >= 1 && budgetOk(budget) && extras.every(extraOk);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isValid) return;
    setSubmitting(true);
    setError(null);
    try {
      // Items asked together share one order id, so they can be compared and read as one order afterwards.
      const oid = extras.length ? "ord_" + Array.from(crypto.getRandomValues(new Uint8Array(8)), b => b.toString(16).padStart(2, "0")).join("") : undefined;
      const make = (it: string, q: number, bud: number | "") => createRFQ({
        item: it.trim(),
        qty: q,
        ...(typeof bud === "number" ? { budget: bud } : {}),
        ...(oid ? { order_id: oid } : {}),
        need_in_days: Number(needInDays),
        buyer_company: buyerCompany,
        buyer_name: buyerName,
        buyer_city: buyerCity,
        buyer_state: buyerState,
        note: note.trim() || undefined,
        priority_mode: priority,
        gst_claimable: me?.profile?.buyer?.gst_claimable ?? true,
        window: windowKey === "auto" ? undefined : windowKey,
        source: "form",
      });
      const res = await make(item, Number(qty), budget);
      const more: RFQCreateResponse[] = [];
      for (const x of extras) more.push(await make(x.item, Number(x.qty), x.budget));
      setOrderId(oid ?? null);
      setCreatedMore(more);
      setCreated(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create request");
    } finally {
      setSubmitting(false);
    }
  };

  // ─── Created State ────────────────────────────────────────────────────

  if (created) {
    return (
      <div className="landing grain isolate min-h-screen bg-ink text-bone pb-16">
      <Ambient />
        <header className="sticky top-0 z-30 border-b border-line bg-ink/90 backdrop-blur-md">
          <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3">
            <Link to="/app" className="flex items-center gap-1.5 rounded-full border border-line bg-surface/80 px-3 py-1.5 text-[12px] text-muted hover:text-bone">
              <ArrowLeft size={13} /><span>Requests</span>
            </Link>
            <span className="label text-signal">REQUEST CREATED</span>
          </div>
        </header>

        <main className="mx-auto max-w-3xl px-4 py-6 space-y-6">
          <div className="rounded-2xl border border-signal/40 bg-signal/10 p-6 text-center space-y-2">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-signal/20">
              <Check size={24} className="text-signal" strokeWidth={2.5} />
            </div>
            <h1 className="display text-2xl text-bone">Request created</h1>
            <p className="text-[13px] text-muted">
              <strong className="text-bone">{created.rfq.item}</strong> · {created.rfq.qty} units · needed within {created.rfq.need_in_days} days
            </p>
            <p className="text-[13px] text-signal">
              {created.matched
                ? `${created.matched} seller${created.matched === 1 ? "" : "s"} stock this item and ${created.matched === 1 ? "was" : "were"} notified.`
                : "No seller in the network stocks this item yet."}
            </p>
            <p className="mx-auto max-w-[52ch] text-[12px] text-muted">
              Quotes arrive without seller names, so you compare on cost and lead time only. You unlock a seller's
              contact when you choose them.
            </p>
          </div>

          {createdMore.length > 0 && (
            <ul className="rounded-2xl border border-line bg-surface/90 divide-y divide-line text-[13px]">
              {[created, ...createdMore].map(r => (
                <li key={r.id} className="flex items-center justify-between gap-3 px-4 py-3">
                  <span className="text-bone"><strong>{r.rfq.item}</strong> <span className="text-muted">· {r.rfq.qty} units · {r.matched} seller{r.matched === 1 ? "" : "s"} notified</span></span>
                  <button type="button" onClick={() => navigate(`/app/compare/${r.id}`)} className="text-signal underline">Compare</button>
                </li>
              ))}
              <li className="px-4 py-2 text-[11px] text-muted">Each item goes to sellers as its own request, so a different seller can win each one. The combined order shows the best seller for every item side by side.</li>
            </ul>
          )}

          <div className="flex flex-col sm:flex-row gap-3">
            {orderId && (
              <button
                type="button"
                onClick={() => navigate(`/app/order/${orderId}`)}
                className="flex-1 flex items-center justify-center gap-2 rounded-full bg-signal py-3 text-[14px] font-semibold text-ink hover:opacity-95"
              >
                <span>See the combined order</span>
                <ExternalLink size={16} />
              </button>
            )}
            <button
              type="button"
              onClick={() => navigate(`/app/compare/${created.id}`)}
              className={`flex-1 flex items-center justify-center gap-2 rounded-full py-3 text-[14px] font-semibold hover:opacity-95 ${orderId ? "border border-line bg-raised text-bone" : "bg-signal text-ink"}`}
            >
              <span>{orderId ? `Compare ${created.rfq.item} only` : "Watch quotes arrive"}</span>
              <ExternalLink size={16} />
            </button>
            <button
              type="button"
              onClick={() => { setCreated(null); setCreatedMore([]); setExtras([]); setOrderId(null); setItem(""); setQty(""); setBudget(""); setNote(""); }}
              className="flex items-center justify-center gap-2 rounded-full border border-line bg-raised px-5 py-3 text-[14px] font-medium text-bone hover:border-signal/50"
            >
              <Package size={16} /><span>Create another</span>
            </button>
          </div>
        </main>
      </div>
    );
  }

  // ─── Form State ────────────────────────────────────────────────────

  return (
    <div className="landing grain isolate min-h-screen bg-ink text-bone pb-16">
      <Ambient />
      <header className="sticky top-0 z-30 border-b border-line bg-ink/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3">
          <Link to="/app" className="flex items-center gap-1.5 rounded-full border border-line bg-surface/80 px-3 py-1.5 text-[12px] text-muted hover:text-bone">
            <ArrowLeft size={13} /><span>Requests</span>
          </Link>
          <span className="label text-signal">NEW REQUEST</span>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-6 space-y-6">
        <h1 className="sr-only">New request</h1>

        <IntakePanel
          buyer={{ company: buyerCompany, name: buyerName, city: buyerCity, state: buyerState }}
          onCreated={setCreated}
        />

        <div className="flex items-center gap-3 text-[12px] text-muted">
          <div className="h-px flex-1 bg-line/60" /><span>or fill the form</span><div className="h-px flex-1 bg-line/60" />
        </div>

        {error && (
          <div className="rounded-xl border border-error/40 bg-error/10 p-4 text-[13px] text-error">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="rounded-2xl border border-line bg-surface/90 p-5 sm:p-6 space-y-5 shadow-sm">
          {/* Item */}
          <div>
            <label className="label mb-1.5 block text-bone">Item <span className="text-signal">*</span></label>
            <input
              type="text"
              required
              value={item}
              onChange={e => setItem(e.target.value)}
              placeholder="e.g. M10 bolt"
              className="w-full rounded-lg border border-line bg-raised px-3 py-2.5 text-[15px] text-bone placeholder:text-muted/40 focus:border-signal focus:outline-none"
            />
          </div>

          {/* Quantity + Need By */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label mb-1.5 block text-bone">Quantity <span className="text-signal">*</span></label>
              <input
                type="number"
                required
                min="1"
                value={qty}
                onChange={e => setQty(e.target.value === "" ? "" : Number(e.target.value))}
                placeholder="100"
                className="num w-full rounded-lg border border-line bg-raised px-3 py-2.5 text-[15px] text-bone placeholder:text-muted/40 focus:border-signal focus:outline-none"
              />
            </div>
            <div>
              <label className="label mb-1.5 block text-bone">Need by (date) <span className="text-signal">*</span></label>
              <input
                type="date"
                required
                min={tomorrow()}
                value={needBy}
                onChange={e => setNeedBy(e.target.value)}
                className="num w-full rounded-lg border border-line bg-raised px-3 py-2.5 text-[15px] text-bone focus:border-signal focus:outline-none"
              />
              {needInDays >= 1 && <p className="mt-1 text-[11px] text-muted">{needInDays} day{needInDays === 1 ? "" : "s"} from today</p>}
            </div>
          </div>

          <div>
            <label className="label mb-1.5 block text-bone">Budget <span className="text-muted">(₹, optional)</span></label>
            <input
              type="number" min="1" value={budget} aria-label="Budget in rupees"
              onChange={e => setBudget(e.target.value === "" ? "" : Number(e.target.value))}
              placeholder="e.g. 5000"
              className="num w-full rounded-lg border border-line bg-raised px-3 py-2.5 text-[15px] text-bone placeholder:text-muted/40 focus:border-signal focus:outline-none"
            />
            <p className="mt-1 text-[11px] text-muted">The most you want to spend on this item, delivered. We show how each quote compares. Sellers never see it.</p>
          </div>

          {extras.map((x, i) => (
            <div key={i} className="grid grid-cols-2 items-end gap-3 sm:grid-cols-[1fr_6rem_8rem_auto]">
              <div className="col-span-2 sm:col-span-1">
                <label className="label mb-1.5 block text-bone">Item {i + 2}</label>
                <input type="text" value={x.item} placeholder="e.g. M8 nut" aria-label={`Item ${i + 2}`}
                  onChange={e => setExtras(extras.map((y, j) => j === i ? { ...y, item: e.target.value } : y))}
                  className="w-full rounded-lg border border-line bg-raised px-3 py-2.5 text-[15px] text-bone placeholder:text-muted/40 focus:border-signal focus:outline-none" />
              </div>
              <div>
                <label className="label mb-1.5 block text-bone">Qty</label>
                <input type="number" min="1" value={x.qty} placeholder="100" aria-label={`Quantity ${i + 2}`}
                  onChange={e => setExtras(extras.map((y, j) => j === i ? { ...y, qty: e.target.value === "" ? "" : Number(e.target.value) } : y))}
                  className="num w-full rounded-lg border border-line bg-raised px-3 py-2.5 text-[15px] text-bone placeholder:text-muted/40 focus:border-signal focus:outline-none" />
              </div>
              <div>
                <label className="label mb-1.5 block text-bone">Budget ₹</label>
                <input type="number" min="1" value={x.budget} placeholder="optional" aria-label={`Budget ${i + 2}`}
                  onChange={e => setExtras(extras.map((y, j) => j === i ? { ...y, budget: e.target.value === "" ? "" : Number(e.target.value) } : y))}
                  className="num w-full rounded-lg border border-line bg-raised px-3 py-2.5 text-[15px] text-bone placeholder:text-muted/40 focus:border-signal focus:outline-none" />
              </div>
              <button type="button" onClick={() => setExtras(extras.filter((_, j) => j !== i))}
                className="mb-1 rounded-full border border-line px-3 py-2 text-[12px] text-muted hover:text-bone">Remove</button>
            </div>
          ))}
          <div>
            <button type="button" onClick={() => setExtras([...extras, { item: "", qty: "", budget: "" }])} disabled={extras.length >= 9}
              className="text-[13px] text-signal underline disabled:opacity-40">+ Add another item to this order</button>
            {extras.length > 0 && <p className="mt-1 text-[11px] text-muted">Same need-by date and settings for every item. Each item goes to sellers as its own request, so a different seller can win each one. You'll see them together as one order.</p>}
          </div>

          <div>
            <label className="label mb-1.5 block text-bone">Sellers have</label>
            <select value={windowKey} onChange={e => setWindowKey(e.target.value as WindowKey | "auto")}
              className="w-full rounded-lg border border-line bg-raised px-3 py-2.5 text-[14px] text-bone focus:border-signal focus:outline-none">
              <option value="auto">{({ fastest: "15 minutes", balanced: "until end of today", cheapest: "24 hours" } as Record<string, string>)[priority]} (suggested for {priority})</option>
              <option value="15m">15 minutes</option>
              <option value="today">Until the end of today</option>
              <option value="24h">24 hours</option>
              <option value="3d">3 days</option>
            </select>
            <p className="mt-1 text-[11px] text-muted">
              You're told when the first quote arrives, when enough have, and when the window closes with the best option.
              Sellers who haven't answered get a reminder.
            </p>
          </div>

          {lastOrder && (lastOrder.last || lastOrder.today) && (
            <div className="rounded-xl border border-line bg-raised/40 p-3 text-[13px] space-y-1">
              <p className="label text-muted">Last order vs today</p>
              {lastOrder.last ? (
                <p className="text-bone">
                  {lastOrder.last.label}: <span className="num">₹{Math.round(lastOrder.last.landed).toLocaleString("en-IN")}</span> for{" "}
                  <span className="num">{lastOrder.last.qty}</span> units on {lastOrder.last.date}.
                </p>
              ) : <p className="text-muted">No earlier order for this item.</p>}
              {lastOrder.today ? (
                <p className="text-bone">
                  Best today for {lastOrder.qty} units: <span className="num">₹{Math.round(lastOrder.today.landed).toLocaleString("en-IN")}</span>{" "}
                  ({lastOrder.today.lead_days} days, {lastOrder.today.sellers_checked} seller{lastOrder.today.sellers_checked === 1 ? "" : "s"} checked).
                  {lastOrder.difference !== null && lastOrder.difference !== 0 && (
                    <> That is <strong className="num text-signal">₹{Math.abs(Math.round(lastOrder.difference)).toLocaleString("en-IN")}</strong>{" "}
                    {lastOrder.difference > 0 ? "less" : "more"} than last time.</>
                  )}
                </p>
              ) : <p className="text-muted">No seller stocks this item yet.</p>}
              <p className="text-[11px] text-muted">{lastOrder.note}</p>
            </div>
          )}

          {/* Priority */}
          <div>
            <label className="label mb-1.5 block text-bone">Priority</label>
            <div className="grid grid-cols-3 gap-2">
              {PRIORITY_OPTIONS.map(o => (
                <button
                  type="button"
                  key={o.id}
                  onClick={() => setPriority(o.id)}
                  className={`rounded-lg border p-2.5 text-center transition-all ${
                    priority === o.id
                      ? "border-signal bg-signal/10 text-bone ring-1 ring-signal/40"
                      : "border-line bg-raised text-muted hover:text-bone"
                  }`}
                >
                  <span className="block text-[13px] font-medium">{o.label}</span>
                  <span className="block text-[11px] text-muted">{o.hint}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Buyer Info (collapsible) */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label mb-1 block text-muted">Your Company</label>
              <input
                type="text"
                value={buyerCompany}
                onChange={e => setBuyerCompany(e.target.value)}
                className="w-full rounded-lg border border-line bg-raised px-3 py-2 text-[13px] text-bone"
              />
            </div>
            <div>
              <label className="label mb-1 block text-muted">Your Name</label>
              <input
                type="text"
                value={buyerName}
                onChange={e => setBuyerName(e.target.value)}
                className="w-full rounded-lg border border-line bg-raised px-3 py-2 text-[13px] text-bone"
              />
            </div>
          </div>

          {/* Note */}
          <div>
            <label className="label mb-1.5 block text-muted">Note to Suppliers (optional)</label>
            <textarea
              value={note}
              onChange={e => setNote(e.target.value)}
              rows={2}
              placeholder="e.g. Need delivery by Friday. Standard ex-GST commercial invoicing."
              className="w-full rounded-lg border border-line bg-raised px-3 py-2 text-[14px] text-bone placeholder:text-muted/40 focus:border-signal focus:outline-none"
            />
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={!isValid || submitting}
            className="flex w-full items-center justify-center gap-2 rounded-full bg-signal py-3 px-6 font-medium text-ink shadow-md transition-all hover:opacity-95 active:scale-98 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Send size={16} />
            <span>{submitting ? "Creating…" : extras.length ? `Create ${extras.length + 1} requests` : "Create request"}</span>
          </button>
        </form>
      </main>
    </div>
  );
}
