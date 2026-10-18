import { motion } from "motion/react";
import { useEffect, useState, useMemo } from "react";
import { Ambient } from "../components/Ambient";
import { LiveToasts, useChangeToasts } from "../components/LiveToasts";
import { Link } from "react-router-dom";
import {
  ArrowLeft, Building2, Package, Plus, ArrowRight,
  Store, AlertTriangle, Bell,
} from "lucide-react";
import { useNotificationAlerts } from "./hooks/useVoiceAlerts";
import { VerifiedBadge } from "./components/VerifiedBadge";
import { StatusChip } from "./components/StatusChip";
import { useApiPoll, useApiOnce } from "../lib/useApi";
import { useSupplierId } from "../lib/useSupplierId";
import { closesAt } from "../lib/windowTime";
import { AccountMenu } from "../components/AccountMenu";
import { computeStatus } from "./types";
import {
  getMe, getSellers, getNotifications, markNotificationViewed, getAutopilot, setAutopilot,
  getSupplierProfile, getSupplierProducts,
  addSupplierProduct, deleteSupplierProduct,
  type NotificationDTO, type SellerSummary, type SupplierProfileDTO, type SupplierProductDTO,
  type SellerOrderDTO, getSellerOrders,
} from "../api/client";


export function SupplierDashboard() {
  const [supplierId, setSupplierId] = useSupplierId();

  // Sellers (demo selector) and this seller's inbox
  const { data: sellers } = useApiOnce<SellerSummary[]>(() => getSellers(), []);
  const { data: me } = useApiOnce(() => getMe(), []);
  // The stored seller id may belong to someone else (an earlier user, or demo sellers switched off):
  // fall back to this user's own seller record, then the first seller the server lets them use.
  useEffect(() => {
    if (!sellers || sellers.length === 0) return;
    if (!sellers.some(s => s.supplier_id === supplierId)) {
      setSupplierId(me?.supplier_id && sellers.some(s => s.supplier_id === me.supplier_id) ? me.supplier_id : sellers[0].supplier_id);
    }
  }, [sellers, me, supplierId, setSupplierId]);
  const { data: inbox, loading: inboxLoading, error: inboxError, refetch: refetchInbox } = useApiPoll<NotificationDTO[]>(
    () => supplierId ? getNotifications(supplierId) : Promise.resolve([]), 2000, [supplierId],
  );

  // A request landing while the seller watches pops up here too (the OS notification covers other tabs)
  const inboxSig = useMemo(() => inbox ? Object.fromEntries(inbox.map(n => [n.id, n])) : undefined, [inbox]);
  const toasts = useChangeToasts(inboxSig, (a, b) => Object.keys(b).filter(id => !a[id]).map(id => ({
    tone: "new" as const,
    text: `New request: ${b[id].qty} × ${b[id].item}${b[id].verdict.can_fulfil === "yes" ? ". You can supply it." : ""}`,
  })));

  // Supplier profile
  const { data: profile } = useApiOnce<SupplierProfileDTO | null>(
    () => supplierId ? getSupplierProfile(supplierId) : Promise.resolve(null), [supplierId],
  );

  // Products
  const { data: products, refetch: refetchProducts } = useApiPoll<SupplierProductDTO[]>(
    () => supplierId ? getSupplierProducts(supplierId) : Promise.resolve([]), 5000, [supplierId],
  );

  const [activeTab, setActiveTab] = useState<"rfqs" | "products" | "orders">("rfqs")
  const { data: orders } = useApiPoll<SellerOrderDTO[]>(() => supplierId ? getSellerOrders(supplierId) : Promise.resolve([]), 5000, [supplierId]);
  const { data: autopilot, refetch: refetchAutopilot } = useApiPoll(() => supplierId ? getAutopilot(supplierId) : Promise.resolve(null), 5000, [supplierId]);
  const toggleAutopilot = async () => {
    try {
      await setAutopilot(supplierId, !autopilot?.enabled);
      refetchAutopilot();
    } catch (e) {
      console.error("Failed to change autopilot:", e);
    }
  };
  const unread = (inbox || []).filter(n => n.status === "new" || !!n.reminder).length;

  // OS notification alert — fires automatically, no toggle needed
  useNotificationAlerts(inbox ?? null);

  // Product form state
  const [showAddProduct, setShowAddProduct] = useState(false);
  const [newProdName, setNewProdName] = useState("");
  const [newProdPrice, setNewProdPrice] = useState<number | "">(12);
  const [newProdPackSize, setNewProdPackSize] = useState<number | "">(50);
  const [newProdMoq, setNewProdMoq] = useState<number | "">(50);
  const [newProdLead, setNewProdLead] = useState<number | "">(2);
  const [newProdStock, setNewProdStock] = useState<number | "">("");
  const [newProdFreight, setNewProdFreight] = useState<number | "">("");
  const [newProdFreeAbove, setNewProdFreeAbove] = useState<number | "">("");
  const [newProdPerUnitFreight, setNewProdPerUnitFreight] = useState<number | "">("");
  const [newProdGst, setNewProdGst] = useState<number | "">(18);
  const [newProdGstIncl, setNewProdGstIncl] = useState<"excl" | "incl" | "unstated">("excl");
  const [newProdTiers, setNewProdTiers] = useState<{ min: number | ""; price: number | "" }[]>([]);
  const [addError, setAddError] = useState<string | null>(null);

  const handleAddProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newProdName || typeof newProdPrice !== "number" || typeof newProdPackSize !== "number") return;
    try {
      await addSupplierProduct(supplierId, {
        name: newProdName,
        category: "fasteners",
        pack_price: Number(newProdPrice),
        pack_size: Number(newProdPackSize),
        moq: typeof newProdMoq === "number" ? newProdMoq : 1,
        usual_lead_days: typeof newProdLead === "number" ? newProdLead : 3,
        unit: Number(newProdPackSize) > 1 ? "box" : "pc",
        stock: typeof newProdStock === "number" ? newProdStock : null,
        freight: typeof newProdFreight === "number" ? newProdFreight : 0,
        free_freight_above: typeof newProdFreeAbove === "number" && newProdFreeAbove > 0 ? newProdFreeAbove : null,
        per_unit_freight: typeof newProdPerUnitFreight === "number" && newProdPerUnitFreight > 0 ? newProdPerUnitFreight : null,
        tax_rate: newProdGstIncl !== "unstated" && typeof newProdGst === "number" ? newProdGst : null,
        price_includes_tax: newProdGstIncl === "unstated" ? null : newProdGstIncl === "incl",
        price_breaks: newProdTiers
          .filter((t): t is { min: number; price: number } => typeof t.min === "number" && typeof t.price === "number")
          .map(t => ({ min_qty: t.min, pack_price: t.price })),
      });
      refetchProducts();
      setShowAddProduct(false);
      setNewProdName("");
      setNewProdStock("");
      setNewProdFreight(""); setNewProdFreeAbove(""); setNewProdPerUnitFreight(""); setNewProdTiers([]);
      setAddError(null);
    } catch (e) {
      setAddError(/422/.test(String(e)) ? "Check the numbers: prices and pack sizes must be above zero and nothing can be negative. Price tiers must get cheaper as quantity grows." : "Could not add the product.");
    }
  };

  const handleDeleteProduct = async (productId: string) => {
    try {
      await deleteSupplierProduct(supplierId, productId);
      refetchProducts();
    } catch (e) {
      console.error("Failed to delete product:", e);
    }
  };

  return (
    <div className="landing grain isolate min-h-screen bg-ink text-bone pb-16">
      <Ambient />
      <LiveToasts toasts={toasts} />
      {/* Header */}
      <header className="sticky top-0 z-30 border-b border-line bg-ink/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-y-2 px-4 py-3 sm:px-6">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <Link to="/" className="flex items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 text-[12px] text-muted hover:text-bone">
              <ArrowLeft size={13} /><span>Story</span>
            </Link>
            <div className="h-4 w-px bg-line/60" />
            <div>
              <span className="display text-base font-semibold text-bone">Crossover Supplier Portal</span>
              <span className="label ml-2 text-signal">SUPPLIER DESK</span>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            {(sellers?.length ?? 0) > 1 && <select
              value={supplierId}
              onChange={e => setSupplierId(e.target.value)}
              title="Demo: act as this seller"
              className="max-w-[180px] rounded-full border border-line bg-surface px-3 py-1 text-[12px] text-bone"
            >
              {(sellers || [{ supplier_id: supplierId, business_name: `Seller ${supplierId}` } as SellerSummary]).map(sl => (
                <option key={sl.supplier_id} value={sl.supplier_id}>{sl.supplier_id} · {sl.business_name}</option>
              ))}
            </select>}
            <button
              type="button"
              onClick={() => setActiveTab("rfqs")}
              className="relative rounded-full border border-line bg-surface p-1.5 text-muted hover:text-bone"
              title={`${unread} new request${unread === 1 ? "" : "s"}`}
            >
              <Bell size={15} />
              {unread > 0 && (
                <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-signal px-1 text-[10px] font-bold text-ink">
                  {unread}
                </span>
              )}
            </button>
            {profile && (
              <div className="hidden 2xl:flex items-center gap-2 whitespace-nowrap rounded-full border border-line bg-surface px-3 py-1 text-[12px]">
                <Store size={13} className="text-signal" />
                <span className="font-medium text-bone">{profile.business_name}</span>
                <span className="text-muted">({profile.location_city})</span>
              </div>
            )}

            <Link to="/app" className="rounded-full border border-line bg-raised px-3 py-1 text-[12px] font-medium text-bone hover:border-signal/50 hover:text-signal transition-colors">
              Buyer view
            </Link>
            <AccountMenu />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6 space-y-6">
        {/* Who wants what you sell, right now */}
        {(() => {
          const open = (inbox ?? []).filter(n => n.rfq_status === "Open" && !n.has_quoted && n.status !== "declined" && n.verdict.can_fulfil !== "no").length;
          const quoted = (inbox ?? []).filter(n => n.has_quoted).length;
          const fresh = (inbox ?? []).filter(n => n.status === "new").length;
          return (
            <div className="relative overflow-hidden rounded-3xl border border-line bg-surface p-6 sm:p-7">
              <div aria-hidden className="pointer-events-none absolute -left-24 -top-24 h-72 w-72 rounded-full bg-live/10 blur-3xl" />
              <div className="relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
                <div>
                  <p className="flex flex-wrap items-center gap-2 text-[13px] text-muted">
                    <span className="font-medium text-bone">{profile?.business_name || "Your business"}</span>
                    {profile && <VerifiedBadge tier={profile.verification_tier} />}
                  </p>
                  <h1 className="display mt-2 text-[clamp(1.8rem,4.2vw,3rem)] leading-[1.05] text-bone">
                    {open > 0
                      ? <><span className="num text-signal">{open}</span> buyer{open === 1 ? "" : "s"} want what you sell</>
                      : "You're all caught up"}
                  </h1>
                  <p className="mt-1 text-[14px] text-muted">Quote in one tap. Your price and stock are already filled in. Free for sellers.</p>
                </div>
                <div className="grid grid-cols-3 gap-2 sm:min-w-[22rem]">
                  {([["New", fresh, "text-signal"], ["To quote", open, "text-bone"], ["Quoted", quoted, "text-live"]] as const).map(([l, n, c]) => (
                    <motion.div key={l} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="rounded-2xl bg-raised/60 px-3 py-3 text-center">
                      <p className={`num text-[26px] font-bold leading-none ${c}`}>{n}</p>
                      <p className="mt-1 text-[11px] text-muted">{l}</p>
                    </motion.div>
                  ))}
                </div>
              </div>
            </div>
          );
        })()}

        {/* Autopilot: off by default */}
        <div className="flex items-center justify-between gap-4 rounded-2xl border border-line bg-surface/80 px-4 py-3">
          <p className="text-[13px] text-muted">
            <span className="label mr-2 text-bone">Autopilot</span>
            {autopilot?.enabled ? "On: " : "Off. "}sends a first quote from your catalog only when stock, lead time and minimum order all fit.
            It never answers a counter-offer.
          </p>
          <button
            type="button"
            role="switch"
            aria-checked={!!autopilot?.enabled}
            aria-label="Autopilot"
            onClick={toggleAutopilot}
            className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors ${
              autopilot?.enabled ? "bg-signal" : "bg-line"
            }`}
          >
            <span className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-surface shadow transition ${
              autopilot?.enabled ? "translate-x-5" : "translate-x-0"
            }`} />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-line gap-6 text-[14px] font-medium">
          <button
            type="button"
            onClick={() => setActiveTab("rfqs")}
            className={`pb-3 transition-colors border-b-2 ${activeTab === "rfqs" ? "border-signal text-bone font-semibold" : "border-transparent text-muted hover:text-bone"}`}
          >
            Inbox ({inbox?.length || 0}){unread > 0 && <span className="ml-1.5 rounded-full bg-signal px-1.5 text-[10px] font-bold text-ink">{unread} new</span>}
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("products")}
            className={`pb-3 transition-colors border-b-2 flex items-center gap-1.5 ${activeTab === "products" ? "border-signal text-bone font-semibold" : "border-transparent text-muted hover:text-bone"}`}
          >
            <span>My Products</span>
            <span className="rounded-full bg-raised px-1.5 py-0.2 text-[11px] text-muted">{products?.length || 0}</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("orders")}
            className={`pb-3 transition-colors border-b-2 flex items-center gap-1.5 ${activeTab === "orders" ? "border-signal text-bone font-semibold" : "border-transparent text-muted hover:text-bone"}`}
          >
            <span>Orders received</span>
            <span className="rounded-full bg-raised px-1.5 py-0.2 text-[11px] text-muted">{orders?.length || 0}</span>
          </button>
        </div>

        {activeTab === "orders" && (
          <div className="space-y-3" aria-label="Orders received">
            {(orders ?? []).length === 0 && (
              <div className="rounded-2xl border border-line bg-surface p-8 text-center">
                <p className="text-[15px] font-medium">No orders yet</p>
                <p className="text-[13px] text-muted">When a buyer chooses your quote, the order and the buyer's contact appear here.</p>
              </div>
            )}
            {(orders ?? []).map(o => (
              <motion.article key={o.rfq_id + o.qty} initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} className="rounded-2xl border border-line bg-surface p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-[12px] text-muted">{o.decided_at ? new Date(o.decided_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : ""}{o.split ? " · part of a split order" : ""}</p>
                    <h3 className="text-[18px] font-semibold"><span className="num">{o.qty}</span> × {o.item}</h3>
                  </div>
                  <div className="text-right"><p className="num text-[20px] font-bold">{o.total != null ? `₹${Math.round(o.total).toLocaleString("en-IN")}` : "—"}</p>
                    <span className="rounded-full bg-live/15 px-2.5 py-0.5 text-[11px] font-medium text-live">{o.status}</span></div>
                </div>
                <div className="mt-3 rounded-xl bg-raised/60 px-4 py-3 text-[13px]">
                  <p className="label text-muted">Buyer to deliver to</p>
                  <p className="mt-1 text-[15px] font-semibold">{o.buyer.company || o.buyer.name}</p>
                  <p className="num text-muted">{[o.buyer.name, o.buyer.phone, o.buyer.email, o.buyer.city].filter(Boolean).join(" · ")}</p>
                  {o.payment && <p className="mt-1 text-[12px] text-muted">{o.payment}</p>}
                </div>
              </motion.article>
            ))}
          </div>
        )}

        {/* Tab 1: Inbox */}
        {activeTab === "rfqs" && (
          <div className="space-y-4">
            {inboxLoading && !inbox ? (
              <div className="rounded-2xl border border-line bg-surface/80 p-8 text-center">
                <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-line border-t-signal" />
                <p className="mt-3 text-[13px] text-muted">Loading inbox…</p>
              </div>
            ) : inboxError ? (
              <div className="rounded-2xl border border-error/40 bg-error/10 p-6 text-center space-y-2">
                <AlertTriangle size={24} className="mx-auto text-error" />
                <p className="text-[13px] text-muted">Cannot reach server. Make sure the backend is running.</p>
              </div>
            ) : !inbox || inbox.length === 0 ? (
              <div className="rounded-2xl border border-line bg-surface/80 p-8 text-center space-y-3">
                <Package size={32} className="mx-auto text-muted" />
                <p className="text-[14px] text-bone">No requests yet</p>
                <p className="text-[13px] text-muted">When a buyer asks for an item in your catalog, it lands here. Add products with stock under My Products.</p>
              </div>
            ) : (
              inbox.map((n, idx) => {
                const st = computeStatus(n.has_quoted, null, n.rfq_status, false, n.status === "declined");
                const tone = n.verdict.can_fulfil === "yes" ? "border-success/40 bg-success/15 text-success"
                  : n.verdict.can_fulfil === "partly" ? "border-warn/40 bg-warn/15 text-warn"
                  : "border-error/40 bg-error/15 text-error";
                const label = n.verdict.can_fulfil === "yes" ? "Can fulfil" : n.verdict.can_fulfil === "partly" ? "Partly" : "Cannot fulfil";
                return (
                  <motion.div key={n.id} initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }}
                    transition={{ type: "spring", stiffness: 240, damping: 26, delay: Math.min(idx, 8) * 0.05 }}
                    className={`relative overflow-hidden rounded-2xl border bg-surface p-5 pl-6 transition-shadow hover:shadow-[0_18px_40px_-28px_var(--signal)] ${n.status === "new" ? "border-signal/50" : "border-line"}`}>
                    <span aria-hidden className={`absolute inset-y-0 left-0 w-1.5 ${n.verdict.can_fulfil === "yes" ? "bg-success" : n.verdict.can_fulfil === "partly" ? "bg-warn" : "bg-error"}`} />
                    {n.status === "new" && <span aria-hidden className="absolute right-4 top-4 h-2 w-2 animate-ping rounded-full bg-signal" />}
                    <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                      <div className="space-y-1.5">
                        <div className="flex flex-wrap items-center gap-2">
                          {n.status === "new" && <span className="rounded-full bg-signal px-2 py-0.5 text-[10px] font-bold text-ink">NEW</span>}
                          <span className="text-[20px] font-semibold text-bone"><span className="num">{n.qty}</span> × {n.item}</span>
                          <span className={`rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${tone}`}>{label}</span>
                          <StatusChip status={st} />
                        </div>
                        <p className="text-[13px] text-muted flex items-center gap-2">
                          <Building2 size={13} />
                          <span>{n.buyer_descriptor}</span>
                          <span>·</span>
                          <span>Needed within {n.need_in_days} days</span>
                          <span>·</span>
                          <span className="capitalize">Priority: {n.priority_mode}</span>
                        </p>
                        {n.reminder && (
                          <div className="rounded-lg border border-warn/40 bg-warn/10 p-2 text-[12px] text-warn" role="status">{n.reminder}</div>
                        )}
                        {n.closes_at && (
                          <p className="text-[11px] text-muted">
                            {n.window_closed
                              ? (n.has_quoted ? "Window closed. You can still revise the quote you sent." : "Window closed. New quotes are not being accepted.")
                              : `Quotes close ${closesAt(n.closes_at)}`}
                          </p>
                        )}
                        {n.unlocked && n.buyer_contact && (
                          <div className="rounded-lg border border-live/40 bg-live/10 p-2.5 text-[12px] text-bone">
                            <strong>A buyer unlocked you.</strong> Contact: {n.buyer_contact.name}, {n.buyer_contact.company}
                            {n.buyer_contact.phone ? ` · ${n.buyer_contact.phone}` : ""}
                            {n.buyer_contact.email ? ` · ${n.buyer_contact.email}` : ""}
                          </div>
                        )}
                        <ul className="text-[12px] text-muted list-disc pl-5">
                          {n.verdict.reasons.map(r => <li key={r}>{r}</li>)}
                        </ul>
                        <p className="text-[11px] text-muted/80">
                          Matched your catalog item: {n.product.name}. Not the same item? Skip it. Stock is a snapshot, not reserved.
                        </p>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <Link
                          to={n.quote_url}
                          onClick={() => { markNotificationViewed(supplierId, n.id).then(refetchInbox).catch(() => {}); }}
                          className="flex items-center gap-1.5 rounded-full bg-signal px-4 py-2 text-[13px] font-medium text-ink transition-transform hover:opacity-95 active:scale-95"
                        >
                          <span>{n.rfq_status !== "Open" ? "View" : n.has_quoted ? "View & Revise" : "Quote in < 1 min"}</span>
                          <ArrowRight size={14} />
                        </Link>
                      </div>
                    </div>
                  </motion.div>
                );
              })
            )}
          </div>
        )}

        {/* Tab 2: Products */}
        {activeTab === "products" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="display text-lg text-bone">My Products</h2>
                <p className="text-[13px] text-muted">Saved products prefill your quotes in 1 click.</p>
              </div>
              <button
                type="button"
                onClick={() => setShowAddProduct(true)}
                className="flex items-center gap-1.5 rounded-full bg-bone px-3.5 py-1.5 text-[12px] font-semibold text-ink hover:opacity-90"
              >
                <Plus size={14} /><span>Add Product</span>
              </button>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {(products || []).map(p => (
                <div key={p.id} className="rounded-xl border border-line bg-surface/90 p-4 space-y-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <span className="label text-muted">{p.category}</span>
                      <h3 className="font-semibold text-bone text-[14px] mt-0.5">{p.name}</h3>
                    </div>
                    <Package size={18} className="text-muted" />
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-[12px] border-t border-line/50 pt-2.5">
                    <div>
                      <span className="text-muted">Pack Price:</span>
                      <p className="num font-bold text-bone">₹{p.pack_price}</p>
                    </div>
                    <div>
                      <span className="text-muted">Pack Size:</span>
                      <p className="num font-medium text-bone">{p.pack_size} {p.unit}/pack</p>
                    </div>
                    <div>
                      <span className="text-muted">Lead Time:</span>
                      <p className="num font-medium text-bone">{p.usual_lead_days} days</p>
                    </div>
                    <div>
                      <span className="text-muted">MOQ:</span>
                      <p className="num font-medium text-bone">{p.moq} units</p>
                    </div>
                    <div>
                      <span className="text-muted">Stock (snapshot):</span>
                      <p className="num font-medium text-bone">{p.stock ?? "not tracked"}</p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleDeleteProduct(p.id)}
                    className="text-[11px] text-muted hover:text-error transition-colors"
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>

            {showAddProduct && (
              <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto overscroll-contain bg-ink/70 p-4 backdrop-blur-sm sm:items-center">
                <div className="my-auto max-h-[calc(100dvh-2rem)] w-full max-w-md overflow-y-auto overscroll-contain rounded-2xl border border-line bg-surface p-6 shadow-2xl">
                  <h3 className="display text-xl text-bone mb-1">Add Product</h3>
                  <p className="text-[13px] text-muted mb-4">Enables 1-tap quote generation.</p>
                  <form onSubmit={handleAddProduct} className="space-y-4">
                    <div>
                      <label className="label mb-1 block text-bone">Product Name</label>
                      <input type="text" required value={newProdName}
                        onChange={e => setNewProdName(e.target.value)}
                        placeholder="e.g. M10 Hex Bolt Grade 8.8"
                        className="w-full rounded-lg border border-line bg-surface px-3 py-2 text-[13px] text-bone" />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="label mb-1 block text-bone">Pack Price (₹)</label>
                        <input type="number" required min="0.1" step="any" value={newProdPrice}
                          onChange={e => setNewProdPrice(e.target.value === "" ? "" : Number(e.target.value))}
                          className="num w-full rounded-lg border border-line bg-surface px-3 py-2 text-[13px] text-bone" />
                      </div>
                      <div>
                        <label className="label mb-1 block text-bone">Units Per Pack</label>
                        <input type="number" required min="1" value={newProdPackSize}
                          onChange={e => setNewProdPackSize(e.target.value === "" ? "" : Number(e.target.value))}
                          className="num w-full rounded-lg border border-line bg-surface px-3 py-2 text-[13px] text-bone" />
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="label mb-1 block text-bone">Lead Days</label>
                        <input type="number" required min="1" value={newProdLead}
                          onChange={e => setNewProdLead(e.target.value === "" ? "" : Number(e.target.value))}
                          className="num w-full rounded-lg border border-line bg-surface px-3 py-2 text-[13px] text-bone" />
                      </div>
                      <div>
                        <label className="label mb-1 block text-bone">MOQ Units</label>
                        <input type="number" min="1" value={newProdMoq}
                          onChange={e => setNewProdMoq(e.target.value === "" ? "" : Number(e.target.value))}
                          className="num w-full rounded-lg border border-line bg-surface px-3 py-2 text-[13px] text-bone" />
                      </div>
                    </div>
                    <div>
                      <label className="label mb-1 block text-bone">Stock on hand (units)</label>
                      <input type="number" min="0" value={newProdStock}
                        onChange={e => setNewProdStock(e.target.value === "" ? "" : Number(e.target.value))}
                        placeholder="Leave blank if not tracked"
                        className="num w-full rounded-lg border border-line bg-surface px-3 py-2 text-[13px] text-bone" />
                      <p className="mt-1 text-[11px] text-muted">A snapshot, not reserved. Orders above stock become a partial fill.</p>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="label mb-1 block text-bone">Freight (₹)</label>
                        <input type="number" min="0" value={newProdFreight} placeholder="0 = free"
                          onChange={e => setNewProdFreight(e.target.value === "" ? "" : Number(e.target.value))}
                          className="num w-full rounded-lg border border-line bg-surface px-3 py-2 text-[13px] text-bone" />
                      </div>
                      <div>
                        <label className="label mb-1 block text-bone">Free delivery above (₹)</label>
                        <input type="number" min="1" value={newProdFreeAbove} placeholder="optional"
                          onChange={e => setNewProdFreeAbove(e.target.value === "" ? "" : Number(e.target.value))}
                          className="num w-full rounded-lg border border-line bg-surface px-3 py-2 text-[13px] text-bone" />
                      </div>
                      <div>
                        <label className="label mb-1 block text-bone">Per-unit freight (₹/unit)</label>
                        <input type="number" min="0.01" step="any" value={newProdPerUnitFreight} placeholder="optional"
                          onChange={e => setNewProdPerUnitFreight(e.target.value === "" ? "" : Number(e.target.value))}
                          className="num w-full rounded-lg border border-line bg-surface px-3 py-2 text-[13px] text-bone" />
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="label mb-1 block text-bone">GST on your price</label>
                        <select value={newProdGstIncl} onChange={e => setNewProdGstIncl(e.target.value as "excl" | "incl" | "unstated")}
                          className="w-full rounded-lg border border-line bg-surface px-3 py-2 text-[13px] text-bone">
                          <option value="excl">Price excludes GST</option>
                          <option value="incl">Price includes GST</option>
                          <option value="unstated">Not stated</option>
                        </select>
                      </div>
                      <div>
                        <label className="label mb-1 block text-bone">GST rate (%)</label>
                        <input type="number" min="0" max="100" value={newProdGst} disabled={newProdGstIncl === "unstated"}
                          onChange={e => setNewProdGst(e.target.value === "" ? "" : Number(e.target.value))}
                          className="num w-full rounded-lg border border-line bg-surface px-3 py-2 text-[13px] text-bone disabled:opacity-40" />
                      </div>
                    </div>
                    <div>
                      <label className="label mb-1 block text-bone">Volume pricing (optional)</label>
                      {newProdTiers.map((t, i) => (
                        <div key={i} className="mb-1.5 flex items-center gap-2">
                          <input type="number" min="1" value={t.min} placeholder="from units" aria-label={`Tier ${i + 1} quantity`}
                            onChange={e => setNewProdTiers(newProdTiers.map((x, j) => j === i ? { ...x, min: e.target.value === "" ? "" : Number(e.target.value) } : x))}
                            className="num w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-[13px] text-bone" />
                          <input type="number" min="0.01" step="any" value={t.price} placeholder="₹ per pack" aria-label={`Tier ${i + 1} price`}
                            onChange={e => setNewProdTiers(newProdTiers.map((x, j) => j === i ? { ...x, price: e.target.value === "" ? "" : Number(e.target.value) } : x))}
                            className="num w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-[13px] text-bone" />
                          <button type="button" onClick={() => setNewProdTiers(newProdTiers.filter((_, j) => j !== i))}
                            className="text-[12px] text-muted hover:text-bone">Remove</button>
                        </div>
                      ))}
                      <button type="button" disabled={newProdTiers.length >= 5} onClick={() => setNewProdTiers([...newProdTiers, { min: "", price: "" }])}
                        className="text-[12px] text-signal underline disabled:opacity-40">+ Add a price tier</button>
                      <p className="mt-1 text-[11px] text-muted">Cheaper per pack from a higher quantity, for example from 500 units at ₹9.</p>
                    </div>
                    {addError && <p className="text-[12px] text-error">{addError}</p>}
                    <div className="flex justify-end gap-2 pt-2">
                      <button type="button" onClick={() => setShowAddProduct(false)}
                        className="rounded-full border border-line px-4 py-1.5 text-[13px] text-muted hover:text-bone">
                        Cancel
                      </button>
                      <button type="submit"
                        className="rounded-full bg-signal px-5 py-1.5 text-[13px] font-medium text-ink hover:opacity-90">
                        Save Product
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
