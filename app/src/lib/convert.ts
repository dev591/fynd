/**
 * Convert API DTOs (snake_case) to the in-browser engine types (camelCase)
 * so the cost-curve slider can re-evaluate at different quantities instantly.
 */
import type { Quote, Need } from "../landing/engine";
import type { QuoteVersionDTO, RFQDTO } from "../api/client";

export function toEngineQuote(qv: QuoteVersionDTO, item: string): Quote {
  return {
    id: qv.supplier_id,
    supplier: qv.supplier_name,
    item: qv.item ?? item,
    // The price the server compared, on the buyer's GST basis, so the slider and the server always agree.
    packPrice: qv.compare_price ?? qv.pack_price,
    packSize: qv.pack_size,
    freight: qv.freight,
    leadDays: qv.lead_days,
    moq: qv.moq,
    maxQty: qv.max_qty ?? undefined,
    raw: `v${qv.version}: ₹${qv.pack_price}/${qv.pack_size === null ? "pack of unknown size" : qv.pack_size > 1 ? qv.pack_size + "pcs" : "pc"} + ₹${qv.freight} freight`,
    channel: "Portal",
  };
}

export function quotesFromRFQDetails(
  quotes: Record<string, QuoteVersionDTO[]>,
  item: string,
): Quote[] {
  const result: Quote[] = [];
  for (const versions of Object.values(quotes)) {
    if (versions.length > 0) {
      result.push(toEngineQuote(versions[versions.length - 1], item));
    }
  }
  return result;
}

export function needFromRFQ(rfq: RFQDTO): Need {
  return { item: rfq.item, qty: rfq.qty, needInDays: rfq.need_in_days };
}
