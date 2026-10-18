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
import type { PriceBreakDTO, ShippingEstimate, SupplierProductDTO } from "../../api/client";

interface QuoteFormProps {
  rfq: { item: string; qty: number; needInDays: number };
  products?: SupplierProductDTO[];
  initialValues?: {
    packPrice?: number;
    packSize?: number;
    freight?: number;
    leadDays?: number;
    priceBreaks?: PriceBreakDTO[];
    freeFreightAbove?: number;
    perUnitFreight?: number;
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
    shipping?: "own" | "delhivery";
    shippingBasis?: "delhivery" | "rate_card";
    priceBreaks?: PriceBreakDTO[];
    freeFreightAbove?: number;
    perUnitFreight?: number;
  }) => void;
  /** Freight and delivery days from the pincodes saved at sign-up. Rejects when none can be worked out. */
  onEstimate?: (weightKg: number) => Promise<ShippingEstimate>;
  isSubmitting?: boolean;
  versionNumber?: number;
  /** Fires on every edit; the page uses the first one to tell the buyer the seller is quoting. */
  onEdit?: () => void;
  /** Warn-only item check for a picked catalog product. Resolves null when no check is available. */
  onCheckItem?: (productId: string) => Promise<{ verdict: string; reason: string } | null>;
}

export function QuoteForm({
  rfq,
  products = [],
  initialValues,
  onSubmit,
  onEstimate,
  isSubmitting = false,
  versionNumber = 1,
  onEdit,
  onCheckItem,
}: QuoteFormProps) {
  // Required fields
  const [packPrice, setPackPrice] = useState<number | "">(initialValues?.packPrice ?? 10);
  const [packSize, setPackSize] = useState<number | "">(initialValues?.packSize ?? 1);
  const [freight, setFreight] = useState<number | "">(initialValues?.freight ?? 150);
  const [leadDays, setLeadDays] = useState<number | "">(initialValues?.leadDays ?? 3);

  // Folded optional fields — open automatically when prefilled data lives there
  const [showOptional, setShowOptional] = useState(
    !!initialValues?.notes || !!initialValues?.freeFreightAbove || !!initialValues?.perUnitFreight || (initialValues?.priceBreaks ?? []).length > 0,
  );
  const [moq, setMoq] = useState<number | "">(initialValues?.moq ?? 1);
  const [maxQty, setMaxQty] = useState<number | "">(initialValues?.maxQty ?? "");
  // GST basis: never assumed for the seller. "Not stated" is sent as nothing, and the buyer sees it flagged.
  type Basis = "unstated" | "excl" | "incl";
  const [basis, setBasis] = useState<Basis>(
    initialValues?.priceIncludesTax === undefined ? "unstated" : initialValues.priceIncludesTax ? "incl" : "excl");
  const [taxRate, setTaxRate] = useState<number | "">(initialValues?.taxRate ?? 18);
  const [notes, setNotes] = useState(initialValues?.notes ?? "");

  // Volume pricing from the catalog travels with the quote. Typing a different price overrides it, so it is dropped.
  const [tiers, setTiers] = useState<PriceBreakDTO[]>(initialValues?.priceBreaks ?? []);
  const [tiersDropped, setTiersDropped] = useState(false);
  const [freeAbove, setFreeAbove] = useState<number | "">(initialValues?.freeFreightAbove ?? "");
  const [perUnitFreight, setPerUnitFreight] = useState<number | "">(initialValues?.perUnitFreight ?? "");

  // Shipping: own shipment, or Delhivery. The estimate only reaches the quote when the seller presses "Use this".
  const [shipping, setShipping] = useState<"own" | "delhivery">("own");
  const [weight, setWeight] = useState<number | "">("");
  const [est, setEst] = useState<ShippingEstimate | null>(null);
  const [estBusy, setEstBusy] = useState(false);
  const [estError, setEstError] = useState<string | null>(null);
  const [applied, setApplied] = useState<ShippingEstimate | null>(null);
  const canEstimate = !!onEstimate && typeof weight === "number" && weight > 0;
  const getEstimate = async () => {
    if (!canEstimate) return;
    setEstBusy(true); setEstError(null); setEst(null);
    try { setEst(await onEstimate!(Number(weight))); }
    catch { setEstError("No estimate for this request. Enter freight and lead time yourself."); }
    finally { setEstBusy(false); }
  };
  const useEstimate = () => {
    if (!est) return;
    setFreight(est.freight); setLeadDays(est.lead_days); setApplied(est);
  };

  // Catalog item picker & item match check
  const [selectedProductId, setSelectedProductId] = useState<string>("");

  const handleSelectProduct = (prodId: string) => {
    setSelectedProductId(prodId);
    const p = products.find((x) => x.id === prodId);
    if (!p) return;
    setItemWarning(null);
    onCheckItem?.(prodId).then(r => {
      if (r && r.verdict === "different") setItemWarning(`Item check: ${r.reason} You can still quote, but make sure it is the same item.`);
    });
    setPackPrice(p.pack_price);
    setPackSize(p.pack_size);
    setMoq(p.moq);
    setLeadDays(p.usual_lead_days);
    if (p.freight) setFreight(p.freight);
    setMaxQty(p.stock ?? p.capacity_cap ?? "");
    if (p.stock != null || p.capacity_cap != null) setShowOptional(true);
  };

  const [itemWarning, setItemWarning] = useState<string | null>(null);

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
        priceBreaks: tiers.map(t => ({ minQty: t.min_qty, packPrice: t.pack_price })),
        freeFreightAbove: typeof freeAbove === "number" && freeAbove > 0 ? freeAbove : undefined,
        perUnitFreight: typeof perUnitFreight === "number" && perUnitFreight > 0 ? perUnitFreight : undefined,
        raw: "",
        channel: "Portal",
      },
      rfq.qty
    );

    return res;
  }, [packPrice, packSize, freight, moq, leadDays, rfq.item, rfq.qty, tiers, freeAbove, perUnitFreight]);

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
      taxRate: basis !== "unstated" && typeof taxRate === "number" ? taxRate : undefined,
      priceIncludesTax: basis === "unstated" || typeof taxRate !== "number" ? undefined : basis === "incl",
      notes: notes.trim() || undefined,
      priceBreaks: tiers.length ? tiers : undefined,
      freeFreightAbove: typeof freeAbove === "number" && freeAbove > 0 ? freeAbove : undefined,
      perUnitFreight: typeof perUnitFreight === "number" && perUnitFreight > 0 ? perUnitFreight : undefined,
      shipping,
      shippingBasis: shipping === "delhivery" && applied ? applied.basis : undefined,
    });
  };

  return (
    <form onSubmit={handleSubmit} onChange={onEdit} className="space-y-5">
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
                <span className="num text-[11px] text-muted">(₹{p.pack_price}/{p.unit})</span>
              </button>
            ))}
          </div>

          {/* Item match warning badge (warn only) */}
          {itemWarning && (
            <div className="mt-2.5 flex items-start gap-2 rounded-lg border border-warn/40 bg-warn/10 p-2.5 text-[12px] text-warn">
              <AlertTriangle size={15} className="shrink-0 mt-0.5" />
              <span>{itemWarning}</span>
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
              onChange={(e) => { if (tiers.length) { setTiers([]); setTiersDropped(true); } setPackPrice(e.target.value === "" ? "" : Number(e.target.value)); }}
              placeholder="10"
              className="num w-full rounded-lg border border-line bg-surface pl-7 pr-3 py-2 text-[14px] text-bone placeholder:text-muted/40 focus:border-signal focus:outline-none"
            />
          </div>
          <span className="text-[11px] text-muted mt-1 block">Per package / piece</span>
          {tiers.length > 1 && (
            <span className="text-[11px] text-muted mt-1 block">
              Volume pricing from your catalog: {tiers.map(t => `${t.min_qty}+ ₹${t.pack_price}`).join(" · ")}. Changing the price removes it.
            </span>
          )}
          {tiersDropped && <span className="text-[11px] text-warn mt-1 block">Volume pricing removed because you changed the price.</span>}
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
              onChange={(e) => { setApplied(null); setFreight(e.target.value === "" ? "" : Number(e.target.value)); }}
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
              min="0"
              max="365"
              step="1"
              required
              value={leadDays}
              onChange={(e) => { setApplied(null); setLeadDays(e.target.value === "" ? "" : Number(e.target.value)); }}
              placeholder="3"
              className="num w-full rounded-lg border border-line bg-surface pl-8 pr-3 py-2 text-[14px] text-bone placeholder:text-muted/40 focus:border-signal focus:outline-none"
            />
          </div>
          <span className="text-[11px] text-muted mt-1 block">
            Buyer needs in {rfq.needInDays} days
          </span>
        </div>
      </div>

      {/* How will you ship this? */}
      <fieldset className="rounded-xl border border-line bg-raised/40 p-4 space-y-3">
        <legend className="label px-1 text-bone">How will you ship it?</legend>
        <div className="flex flex-wrap gap-2">
          {([["own", "My own shipment"], ["delhivery", "Delhivery"]] as const).map(([v, label]) => (
            <label key={v} className={`cursor-pointer rounded-full border px-4 py-1.5 text-[13px] ${shipping === v ? "border-signal bg-signal/10 text-bone" : "border-line text-muted hover:text-bone"}`}>
              <input type="radio" name="shipping" value={v} checked={shipping === v} onChange={() => setShipping(v)} className="sr-only" />
              {label}
            </label>
          ))}
        </div>
        {shipping === "delhivery" && (
          <div className="space-y-3">
            <label className="block max-w-[12rem] text-[12px] text-muted">Parcel weight (kg)
              <input type="number" min="0" step="any" value={weight} onChange={(e) => { setWeight(e.target.value === "" ? "" : Number(e.target.value)); setEst(null); }} placeholder="20"
                className="num mt-1 w-full rounded-lg border border-line bg-surface px-3 py-2 text-[14px] text-bone focus:border-signal focus:outline-none" />
            </label>
            <button type="button" onClick={getEstimate} disabled={!canEstimate || estBusy}
              className="rounded-full border border-line bg-surface px-4 py-1.5 text-[13px] font-medium text-bone hover:border-signal/60 disabled:opacity-40">
              {estBusy ? "Estimating…" : "Estimate freight and delivery time"}
            </button>
            {estError && <p className="text-[12px] text-error">{estError}</p>}
            {est && (
              <div className="rounded-lg border border-line bg-surface p-3 text-[13px]">
                <p className="text-bone"><span className="num font-semibold">₹{est.freight.toLocaleString("en-IN")}</span> freight · <span className="num font-semibold">{est.lead_days} days</span> to the buyer</p>
                <p className="mt-0.5 text-[11px] text-muted">{est.label}. It goes into your quote only if you press the button, and you can still edit it.</p>
                <button type="button" onClick={useEstimate} className="mt-2 rounded-full bg-signal px-4 py-1.5 text-[12px] font-semibold text-ink hover:opacity-95">
                  {applied ? "Applied to your quote" : "Use this in my quote"}
                </button>
              </div>
            )}
          </div>
        )}
      </fieldset>

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
                <label className="label mb-1 block text-muted">Max Capacity Cap (stock snapshot, not reserved)</label>
                <input
                  type="number"
                  min="1"
                  value={maxQty}
                  onChange={(e) => setMaxQty(e.target.value === "" ? "" : Number(e.target.value))}
                  placeholder="Unlimited"
                  className="num w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-[13px] text-bone"
                />
              </div>

              {/* Free delivery above */}
              <div>
                <label className="label mb-1 block text-muted">Free delivery above (₹ of goods, optional)</label>
                <input
                  type="number"
                  min="1"
                  value={freeAbove}
                  onChange={(e) => setFreeAbove(e.target.value === "" ? "" : Number(e.target.value))}
                  placeholder="e.g. 5000"
                  className="num w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-[13px] text-bone"
                />
                <span className="mt-1 block text-[11px] text-muted">Same GST basis as your price. Freight is waived when the order reaches it.</span>
              </div>

              {/* Per-unit freight */}
              <div>
                <label className="label mb-1 block text-muted">Per-unit freight (₹/unit, optional)</label>
                <input
                  type="number"
                  min="0.01"
                  step="any"
                  value={perUnitFreight}
                  onChange={(e) => setPerUnitFreight(e.target.value === "" ? "" : Number(e.target.value))}
                  placeholder="e.g. 2"
                  className="num w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-[13px] text-bone"
                />
                <span className="mt-1 block text-[11px] text-muted">Added to flat freight: total freight = flat + this × units dispatched.</span>
              </div>
            </div>

            {/* GST basis */}
            <div className="border-t border-line/40 pt-3 space-y-2">
              <div>
                <span className="text-[13px] text-bone font-medium">GST on your price</span>
                <p className="text-[11px] text-muted">
                  Say whether the pack price includes GST so buyers compare like with like. If you leave it unstated,
                  the buyer sees it flagged and it is treated as excluding GST.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <select value={basis} onChange={(e) => setBasis(e.target.value as Basis)}
                  className="rounded-lg border border-line bg-surface px-2.5 py-1.5 text-[12px] text-bone">
                  <option value="unstated">Not stated</option>
                  <option value="excl">Price excludes GST</option>
                  <option value="incl">Price includes GST</option>
                </select>
                {basis !== "unstated" && (
                  <div className="flex items-center gap-1">
                    <input type="number" min="0" max="28" value={taxRate}
                      onChange={(e) => setTaxRate(e.target.value === "" ? "" : Number(e.target.value))}
                      className="num w-16 rounded border border-line bg-surface px-2 py-1 text-[12px] text-bone text-center" />
                    <span className="text-[12px] text-muted">% GST</span>
                  </div>
                )}
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
