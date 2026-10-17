import { useState, useMemo } from "react";
import {
  Calculator,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  Sparkles,
  Send,
  Package,
  Truck,
  Calendar,
} from "lucide-react";
import { order } from "../../landing/engine";
import { Money } from "./Money";
import type { RFQItem, SupplierProduct } from "../types";

interface QuoteFormProps {
  rfq: RFQItem;
  products?: SupplierProduct[];
  initialValues?: {
    packPrice?: number;
    packSize?: number;
    freight?: number;
    leadDays?: number;
    moq?: number;
    maxQty?: number;
    taxRate?: number;
    priceIncludesTax?: boolean;
    notes?: string;
  };
  onSubmit: (data: {
    packPrice: number;
    packSize: number;
    freight: number;
    leadDays: number;
    moq?: number;
    maxQty?: number;
    taxRate?: number;
    priceIncludesTax?: boolean;
    notes?: string;
  }) => void;
  isSubmitting?: boolean;
  versionNumber?: number;
}

export function QuoteForm({
  rfq,
  products = [],
  initialValues,
  onSubmit,
  isSubmitting = false,
  versionNumber = 1,
}: QuoteFormProps) {
  // Required fields
  const [packPrice, setPackPrice] = useState<number | "">(initialValues?.packPrice ?? 10);
  const [packSize, setPackSize] = useState<number | "">(initialValues?.packSize ?? 1);
  const [freight, setFreight] = useState<number | "">(initialValues?.freight ?? 150);
  const [leadDays, setLeadDays] = useState<number | "">(initialValues?.leadDays ?? 3);

  // Folded optional fields
  const [showOptional, setShowOptional] = useState(false);
  const [moq, setMoq] = useState<number | "">(initialValues?.moq ?? 1);
  const [maxQty, setMaxQty] = useState<number | "">(initialValues?.maxQty ?? "");
  const [taxRate, setTaxRate] = useState<number | "">(initialValues?.taxRate ?? 18);
  const [priceIncludesTax, setPriceIncludesTax] = useState(initialValues?.priceIncludesTax ?? false);
  const [notes, setNotes] = useState(initialValues?.notes ?? "");

  // Catalog item picker & item match check
  const [selectedProductId, setSelectedProductId] = useState<string>("");

  const handleSelectProduct = (prodId: string) => {
    setSelectedProductId(prodId);
    const p = products.find((x) => x.id === prodId);
    if (!p) return;
    setPackPrice(p.packPrice);
    setPackSize(p.packSize);
    setMoq(p.moq);
    setLeadDays(p.usualLeadDays);
  };

  // AI Item-match check (warn only, doesn't block)
  const itemMismatchWarning = useMemo(() => {
    if (!selectedProductId) return null;
    const p = products.find((x) => x.id === selectedProductId);
    if (!p) return null;
    const rfqLower = rfq.item.toLowerCase();
    const prodLower = p.name.toLowerCase();
    if (prodLower.includes("m8") && rfqLower.includes("m10")) {
      return "Spec Warning: Buyer requested M10 bolt. Your selected catalog product is for M8 bolt. You may still quote, but ensure sizes align.";
    }
    return null;
  }, [selectedProductId, rfq.item, products]);

  // Live order preview calculation using the same engine
  const preview = useMemo(() => {
    const numPrice = typeof packPrice === "number" ? packPrice : 0;
    const numSize = typeof packSize === "number" ? packSize : 1;
    const numFreight = typeof freight === "number" ? freight : 0;
    const numMoq = typeof moq === "number" ? moq : 1;

    if (numSize <= 0) return null;

    const res = order(
      {
        id: "preview",
        supplier: "Self",
        item: rfq.item,
        packPrice: numPrice,
        packSize: numSize,
        freight: numFreight,
        leadDays: typeof leadDays === "number" ? leadDays : 3,
        moq: numMoq,
        raw: "",
        channel: "Portal",
      },
      rfq.qty
    );

    return res;
  }, [packPrice, packSize, freight, moq, leadDays, rfq.item, rfq.qty]);

  const isValid =
    typeof packPrice === "number" &&
    packPrice > 0 &&
    typeof packSize === "number" &&
    packSize > 0 &&
    typeof freight === "number" &&
    freight >= 0 &&
    typeof leadDays === "number" &&
    leadDays > 0;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!isValid) return;

    onSubmit({
      packPrice: Number(packPrice),
      packSize: Number(packSize),
      freight: Number(freight),
      leadDays: Number(leadDays),
      moq: typeof moq === "number" ? moq : undefined,
      maxQty: typeof maxQty === "number" ? maxQty : undefined,
      taxRate: typeof taxRate === "number" ? taxRate : undefined,
      priceIncludesTax,
      notes: notes.trim() || undefined,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* Quick Catalog Autofill */}
      {products.length > 0 && (
        <div className="rounded-xl border border-line bg-raised/40 p-3.5">
          <div className="flex items-center justify-between mb-2">
            <span className="label text-muted flex items-center gap-1.5">
              <Sparkles size={12} className="text-signal" />
              Autofill from Catalog
            </span>
            <span className="text-[11px] text-muted">Optional</span>
          </div>

          <div className="flex flex-wrap gap-2">
            {products.map((p) => (
              <button
                type="button"
                key={p.id}
                onClick={() => handleSelectProduct(p.id)}
                className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-[12px] text-left transition-all ${
                  selectedProductId === p.id
                    ? "border-signal bg-signal/15 text-signal font-medium ring-1 ring-signal/30"
                    : "border-line bg-surface text-muted hover:border-line/80 hover:text-bone"
                }`}
              >
                <Package size={13} className="shrink-0" />
                <span className="truncate max-w-[180px]">{p.name}</span>
                <span className="num text-[11px] text-muted">(₹{p.packPrice}/{p.unit})</span>
              </button>
            ))}
          </div>

          {/* AI Item match warning badge */}
          {itemMismatchWarning && (
            <div className="mt-2.5 flex items-start gap-2 rounded-lg border border-warn/40 bg-warn/10 p-2.5 text-[12px] text-warn">
              <AlertTriangle size={15} className="shrink-0 mt-0.5" />
              <span>{itemMismatchWarning}</span>
            </div>
          )}
        </div>
      )}

      {/* 4 Required Core Fields */}
      <div className="grid grid-cols-2 gap-4">
        {/* Pack Price */}
        <div>
          <label className="label mb-1.5 block text-bone">
            Pack Price (₹) <span className="text-signal">*</span>
          </label>
          <div className="relative">
            <span className="num absolute left-3 top-1/2 -translate-y-1/2 text-muted text-[14px]">₹</span>
            <input
              type="number"
              min="0.1"
              step="any"
              required
              value={packPrice}
              onChange={(e) => setPackPrice(e.target.value === "" ? "" : Number(e.target.value))}
              placeholder="10"
              className="num w-full rounded-lg border border-line bg-surface pl-7 pr-3 py-2 text-[14px] text-bone placeholder:text-muted/40 focus:border-signal focus:outline-none"
            />
          </div>
          <span className="text-[11px] text-muted mt-1 block">Per package / piece</span>
        </div>

        {/* Units per pack */}
        <div>
          <label className="label mb-1.5 block text-bone">
            Units Per Pack <span className="text-signal">*</span>
          </label>
          <div className="relative">
            <Package size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
            <input
              type="number"
              min="1"
              step="1"
              required
              value={packSize}
              onChange={(e) => setPackSize(e.target.value === "" ? "" : Number(e.target.value))}
              placeholder="1"
              className="num w-full rounded-lg border border-line bg-surface pl-8 pr-3 py-2 text-[14px] text-bone placeholder:text-muted/40 focus:border-signal focus:outline-none"
            />
          </div>
          <span className="text-[11px] text-muted mt-1 block">1 for loose units, 50 for box</span>
        </div>

        {/* Freight */}
        <div>
          <label className="label mb-1.5 block text-bone">
            Freight / Shipping (₹) <span className="text-signal">*</span>
          </label>
          <div className="relative">
            <Truck size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
            <input
              type="number"
              min="0"
              step="any"
              required
              value={freight}
              onChange={(e) => setFreight(e.target.value === "" ? "" : Number(e.target.value))}
              placeholder="150"
              className="num w-full rounded-lg border border-line bg-surface pl-8 pr-3 py-2 text-[14px] text-bone placeholder:text-muted/40 focus:border-signal focus:outline-none"
            />
          </div>
          <span className="text-[11px] text-muted mt-1 block">0 for free delivery</span>
        </div>

        {/* Lead time in days */}
        <div>
          <label className="label mb-1.5 block text-bone">
            Lead Time (Days) <span className="text-signal">*</span>
          </label>
          <div className="relative">
            <Calendar size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
            <input
              type="number"
              min="1"
              max="30"
              step="1"
              required
              value={leadDays}
              onChange={(e) => setLeadDays(e.target.value === "" ? "" : Number(e.target.value))}
              placeholder="3"
              className="num w-full rounded-lg border border-line bg-surface pl-8 pr-3 py-2 text-[14px] text-bone placeholder:text-muted/40 focus:border-signal focus:outline-none"
            />
          </div>
          <span className="text-[11px] text-muted mt-1 block">
            Buyer needs in {rfq.needInDays} days
          </span>
        </div>
      </div>

      {/* Folded Optional Fields Accordion */}
      <div className="border-t border-line/60 pt-3">
        <button
          type="button"
          onClick={() => setShowOptional((s) => !s)}
          className="flex items-center justify-between w-full text-[12px] font-medium text-muted hover:text-bone transition-colors"
        >
          <span>Advanced terms: MOQ, Capacity, Tax, Notes</span>
          {showOptional ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>

        {showOptional && (
          <div className="mt-3.5 space-y-4 rounded-xl border border-line/80 bg-raised/20 p-4">
            <div className="grid grid-cols-2 gap-4">
              {/* MOQ */}
              <div>
                <label className="label mb-1 block text-muted">Min Order Qty (MOQ)</label>
                <input
                  type="number"
                  min="1"
                  value={moq}
                  onChange={(e) => setMoq(e.target.value === "" ? "" : Number(e.target.value))}
                  placeholder="1"
                  className="num w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-[13px] text-bone"
                />
              </div>

              {/* Max Capacity */}
              <div>
                <label className="label mb-1 block text-muted">Max Capacity Cap</label>
                <input
                  type="number"
                  min="1"
                  value={maxQty}
                  onChange={(e) => setMaxQty(e.target.value === "" ? "" : Number(e.target.value))}
                  placeholder="Unlimited"
                  className="num w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-[13px] text-bone"
                />
              </div>
            </div>

            {/* GST Details */}
            <div className="flex items-center justify-between border-t border-line/40 pt-3">
              <div>
                <span className="text-[13px] text-bone font-medium">GST Rate (%) & Inclusive</span>
                <p className="text-[11px] text-muted">Applicable tax rate and pricing basis</p>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1">
                  <input
                    type="number"
                    min="0"
                    max="28"
                    value={taxRate}
                    onChange={(e) => setTaxRate(e.target.value === "" ? "" : Number(e.target.value))}
                    className="num w-14 rounded border border-line bg-surface px-2 py-1 text-[12px] text-bone text-center"
                  />
                  <span className="text-[12px] text-muted">%</span>
                </div>
                <label className="flex items-center gap-1.5 text-[12px] text-muted cursor-pointer">
                  <input
                    type="checkbox"
                    checked={priceIncludesTax}
                    onChange={(e) => setPriceIncludesTax(e.target.checked)}
                    className="h-4 w-4 rounded accent-signal"
                  />
                  <span>Inclusive</span>
                </label>
              </div>
            </div>

            {/* Quote Note */}
            <div>
              <label className="label mb-1 block text-muted">Notes / Terms to Buyer</label>
              <input
                type="text"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="e.g. Ready stock in Pune depot; dispatched via BlueDart"
                className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-[13px] text-bone"
              />
            </div>
          </div>
        )}
      </div>

      {/* Live Preview Line (PDF Page 3 requirement) */}
      <div className="rounded-xl border border-line bg-surface/90 p-4 shadow-sm">
        <div className="flex items-center gap-2">
          <Calculator size={15} className="text-signal" />
          <span className="label text-muted">Engine Live Preview</span>
        </div>

        {preview ? (
          <div className="mt-2 text-[14px] text-bone leading-relaxed">
            For <strong className="num font-bold text-bone">{rfq.qty} units</strong>, you will dispatch{" "}
            <strong className="num text-signal font-bold">{preview.packs} packs</strong> ({preview.units} bolts total).{" "}
            Total landed cost: <Money amount={preview.landed} className="font-bold text-signal text-base" />.
            {preview.overbuy > 0 && (
              <span className="block text-[12px] text-warn mt-1">
                ℹ Pack rounding leaves {preview.overbuy} extra bolt inventory for the buyer.
              </span>
            )}
          </div>
        ) : (
          <p className="mt-2 text-[13px] text-error">
            Enter valid pack price and pack size to preview order calculation.
          </p>
        )}
      </div>

      {/* Submit Button */}
      <button
        type="submit"
        disabled={!isValid || isSubmitting}
        className="flex w-full items-center justify-center gap-2 rounded-full bg-signal py-3 px-6 font-medium text-ink shadow-md transition-all hover:opacity-95 active:scale-98 disabled:opacity-40 disabled:cursor-not-allowed"
      >
        <Send size={15} />
        <span>
          {isSubmitting
            ? "Submitting Quote..."
            : versionNumber > 1
            ? `Submit Revised Quote (v${versionNumber})`
            : "Send Quote to Buyer"}
        </span>
      </button>
    </form>
  );
}
