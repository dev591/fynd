import { useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowLeft,
  Building2,
  Package,
  Plus,
  ArrowRight,
  CheckCircle2,
  Store,
} from "lucide-react";
import { useSupplierStore } from "./supplierStore";
import { VerifiedBadge } from "./components/VerifiedBadge";
import { StatusChip } from "./components/StatusChip";
import { Money } from "./components/Money";
import type { Profile } from "../wizard/types";

export function SupplierDashboard() {
  const store = useSupplierStore();
  const rfq = store.getRFQ();
  const quotes = store.getQuotesForSupplier("A");
  const target = store.getTargetForSupplier("A");
  const status = store.getSupplierStatus("A");
  const products = store.getState().products;

  const [activeTab, setActiveTab] = useState<"rfqs" | "products">("rfqs");

  // Load supplier profile from local storage or mock
  const [profile] = useState<Profile>(() => {
    try {
      const saved = localStorage.getItem("crossover_active_profile");
      if (saved) {
        const p = JSON.parse(saved);
        if (p.role === "supplier") return p;
      }
    } catch {
      // fallback
    }
    return {
      id: "usr_supplier_suresh",
      role: "supplier",
      full_name: "Suresh Gupta",
      email: "suresh@boltexpress.co",
      phone: "9819022334",
      company: "Bolt Express Industrial Supplies",
      business_type: "distributor",
      state: "Maharashtra",
      city: "Mumbai",
      categories: ["fasteners", "tools"],
      gstin: "27XYZAB5678C1Z2",
      pan_masked: "XYZAB5678C",
      verification: {
        email: true,
        tax_ids_consistent: true,
        registry: "demo",
      },
      supplier: {
        default_lead_days: 3,
        gst_inclusive_default: false,
        regions: ["Maharashtra", "Gujarat", "Karnataka"],
      },
    };
  });

  // New product form modal state
  const [showAddProduct, setShowAddProduct] = useState(false);
  const [newProdName, setNewProdName] = useState("");
  const [newProdPrice, setNewProdPrice] = useState<number | "">(12);
  const [newProdPackSize, setNewProdPackSize] = useState<number | "">(50);
  const [newProdMoq, setNewProdMoq] = useState<number | "">(50);
  const [newProdLead, setNewProdLead] = useState<number | "">(2);

  const handleAddProduct = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newProdName || typeof newProdPrice !== "number" || typeof newProdPackSize !== "number") return;

    store.addProduct({
      name: newProdName,
      category: "fasteners",
      packPrice: Number(newProdPrice),
      packSize: Number(newProdPackSize),
      moq: typeof newProdMoq === "number" ? newProdMoq : 1,
      usualLeadDays: typeof newProdLead === "number" ? newProdLead : 3,
      unit: Number(newProdPackSize) > 1 ? "box" : "pc",
    });

    setShowAddProduct(false);
    setNewProdName("");
  };

  const latestQuote = quotes.length > 0 ? quotes[quotes.length - 1] : null;

  return (
    <div className="landing grain min-h-screen bg-ink text-bone pb-16">
      {/* Top Header */}
      <header className="sticky top-0 z-30 border-b border-line bg-ink/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            <Link
              to="/"
              className="flex items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 text-[12px] text-muted hover:text-bone"
            >
              <ArrowLeft size={13} />
              <span>Story</span>
            </Link>
            <div className="h-4 w-px bg-line/60" />
            <div>
              <span className="display text-base font-semibold text-bone">
                Crossover Supplier Portal
              </span>
              <span className="label ml-2 text-signal">SUPPLIER DESK</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1 text-[12px]">
              <Store size={13} className="text-signal" />
              <span className="font-medium text-bone">{profile.company}</span>
              <span className="text-muted">({profile.city})</span>
            </div>

            <Link
              to="/app"
              className="rounded-full border border-line bg-raised px-3 py-1 text-[12px] font-medium text-bone hover:border-signal/50 hover:text-signal transition-colors"
            >
              Switch to Buyer View
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6 space-y-6">
        {/* Banner with Verification Tier Status (PDF Page 3 requirement) */}
        <div className="rounded-2xl border border-line bg-surface/90 p-5 shadow-sm backdrop-blur-md">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="label text-signal">SUPPLIER VERIFICATION</span>
                <span className="text-muted">·</span>
                <span className="text-[13px] text-muted">{profile.company}</span>
              </div>
              <h1 className="display text-2xl text-bone mt-1">
                Welcome back, {profile.full_name}
              </h1>
              <p className="text-[13px] text-muted mt-0.5">
                Quotes submitted here compete exclusively on real landed cost with automatic pack rounding.
              </p>
            </div>

            {/* Badges and Upgrade Steps */}
            <div className="flex flex-col sm:items-end gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <VerifiedBadge tier="registry" />
                <span className="inline-flex items-center gap-1 rounded-full border border-live/30 bg-live/15 px-2.5 py-0.5 text-[11px] font-medium text-live">
                  <CheckCircle2 size={12} /> Tax Verified ({profile.state})
                </span>
              </div>

              <span className="text-[11px] text-muted">
                GSTIN: <span className="font-mono text-bone">{profile.gstin || "27XYZAB5678C1Z2"}</span>
              </span>
            </div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="flex border-b border-line gap-6 text-[14px] font-medium">
          <button
            type="button"
            onClick={() => setActiveTab("rfqs")}
            className={`pb-3 transition-colors border-b-2 ${
              activeTab === "rfqs"
                ? "border-signal text-bone font-semibold"
                : "border-transparent text-muted hover:text-bone"
            }`}
          >
            Invited Requests ({1})
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("products")}
            className={`pb-3 transition-colors border-b-2 flex items-center gap-1.5 ${
              activeTab === "products"
                ? "border-signal text-bone font-semibold"
                : "border-transparent text-muted hover:text-bone"
            }`}
          >
            <span>My Product Catalog</span>
            <span className="rounded-full bg-raised px-1.5 py-0.2 text-[11px] text-muted">
              {products.length}
            </span>
          </button>
        </div>

        {/* Tab 1: Requests List (PDF Page 3 requirement) */}
        {activeTab === "rfqs" && (
          <div className="space-y-4">
            <div className="rounded-2xl border border-line bg-surface/80 p-5 backdrop-blur-sm">
              <div className="flex items-center justify-between pb-3 border-b border-line/60">
                <div>
                  <h2 className="display text-lg text-bone">Live RFQ Inquiries</h2>
                  <p className="text-[12px] text-muted">
                    Sealed bids: You only see the buyer's request and counter-offers specifically sent to you.
                  </p>
                </div>
              </div>

              {/* RFQ Card */}
              <div className="mt-4 rounded-xl border border-line bg-surface p-4 transition-all hover:border-line/80">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-lg text-bone">{rfq.item}</span>
                      <span className="num rounded bg-raised px-2 py-0.5 text-[12px] font-medium text-bone">
                        {rfq.qty} units
                      </span>
                      <StatusChip status={status} />
                    </div>

                    <p className="text-[13px] text-muted flex items-center gap-2">
                      <Building2 size={13} />
                      <span>{rfq.buyerCompany} ({rfq.buyerCity})</span>
                      <span>·</span>
                      <span>Needed within {rfq.needInDays} days</span>
                    </p>

                    {target && target.status === "pending" && (
                      <p className="text-[12px] text-signal font-medium mt-1">
                        ⚡ Buyer sent target: "{target.message}"
                      </p>
                    )}
                  </div>

                  <div className="flex items-center gap-3 shrink-0">
                    {latestQuote && (
                      <div className="text-right hidden sm:block">
                        <span className="label text-muted block">Your Quote</span>
                        <Money amount={latestQuote.landedCost} className="num text-base font-bold text-bone" />
                        <span className="text-[11px] text-muted block">v{latestQuote.version}</span>
                      </div>
                    )}

                    <Link
                      to="/supplier/quote"
                      className="flex items-center gap-1.5 rounded-full bg-signal px-4 py-2 text-[13px] font-medium text-ink transition-transform hover:opacity-95 active:scale-95"
                    >
                      <span>{latestQuote ? "View & Revise Quote" : "Quote in < 1 min"}</span>
                      <ArrowRight size={14} />
                    </Link>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: My Products Manager (PDF Page 4 requirement) */}
        {activeTab === "products" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="display text-lg text-bone">My Products</h2>
                <p className="text-[13px] text-muted">
                  Saved products prefill your quotes in 1 click so you never have to re-type pack sizes.
                </p>
              </div>

              <button
                type="button"
                onClick={() => setShowAddProduct(true)}
                className="flex items-center gap-1.5 rounded-full bg-bone px-3.5 py-1.5 text-[12px] font-semibold text-ink hover:opacity-90"
              >
                <Plus size={14} />
                <span>Add Product</span>
              </button>
            </div>

            {/* Products Grid */}
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {products.map((p) => (
                <div
                  key={p.id}
                  className="rounded-xl border border-line bg-surface/90 p-4 space-y-3"
                >
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
                      <p className="num font-bold text-bone">₹{p.packPrice}</p>
                    </div>
                    <div>
                      <span className="text-muted">Pack Size:</span>
                      <p className="num font-medium text-bone">{p.packSize} {p.unit}/pack</p>
                    </div>
                    <div>
                      <span className="text-muted">Lead Time:</span>
                      <p className="num font-medium text-bone">{p.usualLeadDays} days</p>
                    </div>
                    <div>
                      <span className="text-muted">MOQ:</span>
                      <p className="num font-medium text-bone">{p.moq} units</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Modal: Add Product */}
            {showAddProduct && (
              <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/70 backdrop-blur-sm p-4">
                <div className="w-full max-w-md rounded-2xl border border-line bg-surface p-6 shadow-2xl">
                  <h3 className="display text-xl text-bone mb-1">Add Product to Catalog</h3>
                  <p className="text-[13px] text-muted mb-4">
                    Allows 1-tap quote generation during incoming buyer RFQs.
                  </p>

                  <form onSubmit={handleAddProduct} className="space-y-4">
                    <div>
                      <label className="label mb-1 block text-bone">Product Name</label>
                      <input
                        type="text"
                        required
                        value={newProdName}
                        onChange={(e) => setNewProdName(e.target.value)}
                        placeholder="e.g. M10 Hex Bolt Grade 8.8"
                        className="w-full rounded-lg border border-line bg-surface px-3 py-2 text-[13px] text-bone"
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="label mb-1 block text-bone">Pack Price (₹)</label>
                        <input
                          type="number"
                          required
                          min="0.1"
                          step="any"
                          value={newProdPrice}
                          onChange={(e) => setNewProdPrice(e.target.value === "" ? "" : Number(e.target.value))}
                          className="num w-full rounded-lg border border-line bg-surface px-3 py-2 text-[13px] text-bone"
                        />
                      </div>
                      <div>
                        <label className="label mb-1 block text-bone">Units Per Pack</label>
                        <input
                          type="number"
                          required
                          min="1"
                          value={newProdPackSize}
                          onChange={(e) => setNewProdPackSize(e.target.value === "" ? "" : Number(e.target.value))}
                          className="num w-full rounded-lg border border-line bg-surface px-3 py-2 text-[13px] text-bone"
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="label mb-1 block text-bone">Lead Days</label>
                        <input
                          type="number"
                          required
                          min="1"
                          value={newProdLead}
                          onChange={(e) => setNewProdLead(e.target.value === "" ? "" : Number(e.target.value))}
                          className="num w-full rounded-lg border border-line bg-surface px-3 py-2 text-[13px] text-bone"
                        />
                      </div>
                      <div>
                        <label className="label mb-1 block text-bone">MOQ Units</label>
                        <input
                          type="number"
                          min="1"
                          value={newProdMoq}
                          onChange={(e) => setNewProdMoq(e.target.value === "" ? "" : Number(e.target.value))}
                          className="num w-full rounded-lg border border-line bg-surface px-3 py-2 text-[13px] text-bone"
                        />
                      </div>
                    </div>

                    <div className="flex justify-end gap-2 pt-2">
                      <button
                        type="button"
                        onClick={() => setShowAddProduct(false)}
                        className="rounded-full border border-line px-4 py-1.5 text-[13px] text-muted hover:text-bone"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        className="rounded-full bg-signal px-5 py-1.5 text-[13px] font-medium text-ink hover:opacity-90"
                      >
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
