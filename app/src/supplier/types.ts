// Frontend types that match the backend API DTOs (snake_case from the API).
// Re-exported from client.ts so there is a single source of truth.

export type {
  RFQDTO as RFQItem,
  QuoteVersionDTO as QuoteVersion,
  NegotiationTargetDTO as NegotiationTarget,
  ChatMessageDTO as ChatMessage,
  SupplierProductDTO as SupplierProduct,
  SupplierProfileDTO as SupplierProfile,
} from "../api/client";

// Derived types
export type SupplierQuoteStatus = "received" | "under_review" | "target_sent" | "won" | "not_selected" | "declined";

/** Compute supplier status from quotes + target. */
export function computeStatus(
  hasQuotes: boolean,
  targetStatus: string | null,
  rfqStatus: string,
  isWinner: boolean,
  declined = false,
): SupplierQuoteStatus {
  if (declined && !hasQuotes && rfqStatus === "Open") return "declined";
  if (rfqStatus === "Decided" || rfqStatus === "Closed") {
    return isWinner ? "won" : "not_selected";
  }
  if (targetStatus === "pending") return "target_sent";
  if (targetStatus === "accepted") return "under_review";
  if (hasQuotes) return "under_review";
  return "received";
}
