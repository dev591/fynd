export type RFQStatus = "Open" | "Decided" | "Closed";

export type SupplierQuoteStatus =
  | "received"
  | "under_review"
  | "target_sent"
  | "won"
  | "not_selected";

export interface SupplierProduct {
  id: string;
  name: string;
  category: string;
  packPrice: number;
  packSize: number;
  moq: number;
  usualLeadDays: number;
  capacityCap?: number;
  unit: string;
}

export interface NegotiationTarget {
  id: string;
  supplierId: string;
  message: string;
  cutNeeded: number;
  targetFreight?: number;
  targetPerUnit?: number;
  concessionType: "freight" | "unit_price";
  sentAt: string;
  status: "pending" | "accepted" | "declined";
}

export interface QuoteVersion {
  version: number;
  packPrice: number;
  packSize: number;
  freight: number;
  leadDays: number;
  moq?: number;
  maxQty?: number;
  taxRate?: number;
  priceIncludesTax?: boolean;
  notes?: string;
  submittedAt: string;
  landedCost: number;
  units: number;
  packs: number;
}

export interface RFQItem {
  id: string;
  item: string;
  qty: number;
  needInDays: number;
  buyerCompany: string;
  buyerName: string;
  buyerCity: string;
  buyerState: string;
  note?: string;
  createdAt: string;
  status: RFQStatus;
  winnerSupplierId?: string;
}

export interface ChatMessage {
  id: string;
  sender: "buyer" | "supplier";
  senderName: string;
  text: string;
  target?: NegotiationTarget;
  timestamp: string;
}
