import { useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowLeft, Building2, Package, Plus, ArrowRight,
  Store, AlertTriangle,
} from "lucide-react";
import { VerifiedBadge } from "./components/VerifiedBadge";
import { StatusChip } from "./components/StatusChip";
import { Money } from "./components/Money";
import { useApiPoll, useApiOnce } from "../lib/useApi";
import { computeStatus } from "./types";
import {
  getRFQs, getSupplierProfile, getSupplierProducts,
  addSupplierProduct, deleteSupplierProduct,
  getMyQuotes,
  type RFQDTO, type SupplierProfileDTO, type SupplierProductDTO, type QuoteVersionDTO,
} from "../api/client";

const SUPPLIER_ID = "A";
const DEMO_TOKEN = "tok_supplier_a";

export function SupplierDashboard() {
  // Poll RFQs (invited requests)
  const { data: rfqs, loading: rfqsLoading, error: rfqsError } = useApiPoll<RFQDTO[]>(
    () => getRFQs(), 5000, [],
  );

  // Supplier profile
  const { data: profile } = useApiOnce<SupplierProfileDTO>(
    () => getSupplierProfile(SUPPLIER_ID), [],
  );

  // Products
  const { data: products, refetch: refetchProducts } = useApiPoll<SupplierProductDTO[]>(
    () => getSupplierProducts(SUPPLIER_ID), 5000, [],
  );

  // My quotes on the seeded RFQ (for status display)
  const { data: myData } = useApiPoll<{ quotes: QuoteVersionDTO[]; target: any }>(
    () => getMyQuotes(DEMO_TOKEN), 2000, [],
  );

  const [activeTab, setActiveTab] = useState<"rfqs" | "products">("rfqs");

  // Product form state
  const [showAddProduct, setShowAddProduct] = useState(false);
  const [newProdName, setNewProdName] = useState("");
  const [newProdPrice, setNewProdPrice] = useState<number | "">(12);
  const [newProdPackSize, setNewProdPackSize] = useState<number | "">(50);
  const [newProdMoq, setNewProdMoq] = useState<number | "">(50);
  const [newProdLead, setNewProdLead] = useState<number | "">(2);

  const handleAddProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newProdName || typeof newProdPrice !== "number" || typeof newProdPackSize !== "number") return;
    try {
      await addSupplierProduct(SUPPLIER_ID, {
        name: newProdName,
        category: "fasteners",
        pack_price: Number(newProdPrice),
        pack_size: Number(newProdPackSize),
        moq: typeof newProdMoq === "number" ? newProdMoq : 1,
        usual_lead_days: typeof newProdLead === "number" ? newProdLead : 3,
        unit: Number(newProdPackSize) > 1 ? "box" : "pc",
      });
      refetchProducts();
      setShowAddProduct(false);
      setNewProdName("");
    } catch (e) {
      console.error("Failed to add product:", e);
    }
  };

  const handleDeleteProduct = async (productId: string) => {
    try {
      await deleteSupplierProduct(SUPPLIER_ID, productId);
      refetchProducts();
    } catch (e) {
      console.error("Failed to delete product:", e);
    }
  };

  const myQuotes = myData?.quotes || [];
  const myTarget = myData?.target || null;

  return (
    <div className="landing grain min-h-screen bg-ink text-bone pb-16">
      {/* Header */}
      <header className="sticky top-0 z-30 border-b border-line bg-ink/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            <Link to="/" className="flex items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 text-[12px] text-muted hover:text-bone">
              <ArrowLeft size={13} /><span>Story</span>
            </Link>
            <div className="h-4 w-px bg-line/60" />
            <div>
              <span className="display text-base font-semibold text-bone">Crossover Supplier Portal</span>
              <span className="label ml-2 text-signal">SUPPLIER DESK</span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {profile && (
              <div className="hidden sm:flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1 text-[12px]">
                <Store size={13} className="text-signal" />
                <span className="font-medium text-bone">{profile.business_name}</span>
                <span className="text-muted">({profile.location_city})</span>
              </div>
            )}
            <Link to="/app" className="rounded-full border border-line bg-raised px-3 py-1 text-[12px] font-medium text-bone hover:border-signal/50 hover:text-signal transition-colors">
              Switch to Buyer View
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6 space-y-6">
        {/* Verification Banner */}
        <div className="rounded-2xl border border-line bg-surface/90 p-5 shadow-sm backdrop-blur-md">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="label text-signal">SUPPLIER VERIFICATION</span>
                <span className="text-muted">·</span>
                <span className="text-[13px] text-muted">{profile?.business_name || "Loading…"}</span>
              </div>
              <h1 className="display text-2xl text-bone mt-1">Welcome back</h1>
              <p className="text-[13px] text-muted mt-0.5">
                Quotes compete exclusively on real landed cost with automatic pack rounding.
              </p>
            </div>
            <div className="flex flex-col sm:items-end gap-2">
              <div className="flex flex-wrap items-center gap-2">
                {profile && <VerifiedBadge tier={profile.verification_tier} />}
              </div>
              {profile?.categories.map(c => (
                <span key={c} className="rounded-full bg-raised px-2 py-0.5 text-[11px] text-muted">{c}</span>
              ))}
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-line gap-6 text-[14px] font-medium">
          <button
            type="button"
            onClick={() => setActiveTab("rfqs")}
            className={`pb-3 transition-colors border-b-2 ${activeTab === "rfqs" ? "border-signal text-bone font-semibold" : "border-transparent text-muted hover:text-bone"}`}
          >
            Invited Requests ({rfqs?.length || 0})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("products")}
            className={`pb-3 transition-colors border-b-2 flex items-center gap-1.5 ${activeTab === "products" ? "border-signal text-bone font-semibold" : "border-transparent text-muted hover:text-bone"}`}
          >
            <span>My Products</span>
            <span className="rounded-full bg-raised px-1.5 py-0.2 text-[11px] text-muted">{products?.length || 0}</span>
          </button>
        </div>

        {/* Tab 1: Requests */}
        {activeTab === "rfqs" && (
          <div className="space-y-4">
            {rfqsLoading && !rfqs ? (
              <div className="rounded-2xl border border-line bg-surface/80 p-8 text-center">
                <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-line border-t-signal" />
                <p className="mt-3 text-[13px] text-muted">Loading requests…</p>
              </div>
            ) : rfqsError ? (
              <div className="rounded-2xl border border-error/40 bg-error/10 p-6 text-center space-y-2">
                <AlertTriangle size={24} className="mx-auto text-error" />
                <p className="text-[13px] text-muted">Cannot reach server. Make sure the backend is running.</p>
              </div>
            ) : !rfqs || rfqs.length === 0 ? (
              <div className="rounded-2xl border border-line bg-surface/80 p-8 text-center space-y-3">
                <Package size={32} className="mx-auto text-muted" />
                <p className="text-[14px] text-bone">No requests yet</p>
                <p className="text-[13px] text-muted">When a buyer invites you to quote, the request will appear here.</p>
              </div>
            ) : (
              rfqs.map(rfq => {
                // Find this supplier's quotes on this RFQ
                const token = rfq.supplier_tokens?.[SUPPLIER_ID] || DEMO_TOKEN;
                const isSeeded = rfq.id === "rfq_c27_01";
                const quotes = isSeeded ? myQuotes : [];
                const target = isSeeded ? myTarget : null;
                const lq = quotes.length > 0 ? quotes[quotes.length - 1] : null;
                const st = computeStatus(quotes.length > 0, target?.status || null, rfq.status, false);

                return (
                  <div key={rfq.id} className="rounded-2xl border border-line bg-surface/80 p-5 backdrop-blur-sm">
                    <div className="rounded-xl border border-line bg-surface p-4 transition-all hover:border-line/80">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-lg text-bone">{rfq.item}</span>
                            <span className="num rounded bg-raised px-2 py-0.5 text-[12px] font-medium text-bone">
                              {rfq.qty} units
                            </span>
                            <StatusChip status={st} />
                          </div>
                          <p className="text-[13px] text-muted flex items-center gap-2">
                            <Building2 size={13} />
                            <span>{rfq.buyer_company} ({rfq.buyer_city})</span>
                            <span>·</span>
                            <span>Needed within {rfq.need_in_days} days</span>
                          </p>
                          {target && target.status === "pending" && (
                            <p className="text-[12px] text-signal font-medium mt-1">
                              ⚡ Buyer sent target: "{target.message}"
                            </p>
                          )}
                        </div>
                        <div className="flex items-center gap-3 shrink-0">
                          {lq && (
                            <div className="text-right hidden sm:block">
                              <span className="label text-muted block">Your Quote</span>
                              <Money amount={lq.landed_cost} className="num text-base font-bold text-bone" />
                              <span className="text-[11px] text-muted block">v{lq.version}</span>
                            </div>
                          )}
                          <Link
                            to={`/supplier/quote?token=${token}`}
                            className="flex items-center gap-1.5 rounded-full bg-signal px-4 py-2 text-[13px] font-medium text-ink transition-transform hover:opacity-95 active:scale-95"
                          >
                            <span>{lq ? "View & Revise" : "Quote in < 1 min"}</span>
                            <ArrowRight size={14} />
                          </Link>
                        </div>
                      </div>
                    </div>
                  </div>
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
              <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/70 backdrop-blur-sm p-4">
                <div className="w-full max-w-md rounded-2xl border border-line bg-surface p-6 shadow-2xl">
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
