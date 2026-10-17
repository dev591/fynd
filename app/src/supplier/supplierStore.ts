import { useState, useEffect } from "react";
import type {
  RFQItem,
  SupplierProduct,
  QuoteVersion,
  NegotiationTarget,
  ChatMessage,
  SupplierQuoteStatus,
} from "./types";
import { order } from "../landing/engine";

const STORAGE_KEY_PREFIX = "crossover_supplier_v1";

export const DEFAULT_RFQ: RFQItem = {
  id: "rfq_c27_01",
  item: "M10 bolt",
  qty: 100,
  needInDays: 5,
  buyerCompany: "FanWorks Precision Manufacturing",
  buyerName: "Ramesh Sharma",
  buyerCity: "Pune",
  buyerState: "Maharashtra",
  note: "Need 100 high-tensile hex bolts for fan motor mountings by Friday. Standard ex-GST commercial invoicing.",
  createdAt: "2026-10-17T09:30:00Z",
  status: "Open",
};

export const DEFAULT_SUPPLIER_PRODUCTS: SupplierProduct[] = [
  {
    id: "prod_1",
    name: "M10 Hex Bolt (Grade 8.8 High-Tensile)",
    category: "fasteners",
    packPrice: 10,
    packSize: 1,
    moq: 50,
    usualLeadDays: 3,
    unit: "pc",
  },
  {
    id: "prod_2",
    name: "M10 Zinc-Plated Box Pack (Box of 50)",
    category: "fasteners",
    packPrice: 450,
    packSize: 50,
    moq: 50,
    usualLeadDays: 2,
    unit: "box",
  },
  {
    id: "prod_3",
    name: "M8 Machine Bolt (Pack of 100)",
    category: "fasteners",
    packPrice: 350,
    packSize: 100,
    moq: 100,
    usualLeadDays: 4,
    unit: "box",
  },
];

// Seed quotes representing Supplier A, B, C, D
export interface StoredQuotesData {
  quotes: Record<string, QuoteVersion[]>;
  targets: Record<string, NegotiationTarget | null>;
  messages: Record<string, ChatMessage[]>;
  supplierStatuses: Record<string, SupplierQuoteStatus>;
  rfq: RFQItem;
  products: SupplierProduct[];
}

function loadInitialState(): StoredQuotesData {
  try {
    const raw = localStorage.getItem(`${STORAGE_KEY_PREFIX}_state`);
    if (raw) return JSON.parse(raw);
  } catch {
    // fallback
  }

  // Seed default quotes for Supplier A, B, C
  const quotes: Record<string, QuoteVersion[]> = {
    A: [
      {
        version: 1,
        packPrice: 10,
        packSize: 1,
        freight: 200,
        leadDays: 3,
        moq: 1,
        notes: "Ex-warehouse Pune. Standard courier.",
        submittedAt: "2026-10-17T10:00:00Z",
        landedCost: 1200,
        units: 100,
        packs: 100,
      },
    ],
    B: [
      {
        version: 1,
        packPrice: 11,
        packSize: 1,
        freight: 50,
        leadDays: 3,
        moq: 1,
        notes: "Local depot delivery within 72 hours.",
        submittedAt: "2026-10-17T10:15:00Z",
        landedCost: 1150,
        units: 100,
        packs: 100,
      },
    ],
  };

  const messages: Record<string, ChatMessage[]> = {
    A: [
      {
        id: "m1",
        sender: "buyer",
        senderName: "Ramesh Sharma",
        text: "Hi Suresh, we received your quote of ₹10/bolt with ₹200 delivery. A competing quote lands ₹50 cheaper because of lower freight.",
        timestamp: "10:20 AM",
      },
    ],
  };

  return {
    quotes,
    targets: {
      A: {
        id: "tgt_A_1",
        supplierId: "A",
        message: "Match competitor landed cost: cut freight to ₹149 or reduce pack price.",
        cutNeeded: 51,
        targetFreight: 149,
        concessionType: "freight",
        sentAt: "10:22 AM",
        status: "pending",
      },
    },
    messages,
    supplierStatuses: {
      A: "target_sent",
      B: "won",
    },
    rfq: DEFAULT_RFQ,
    products: DEFAULT_SUPPLIER_PRODUCTS,
  };
}

class StoreEmitter extends EventTarget {
  emitChange() {
    this.dispatchEvent(new Event("change"));
  }
}

const storeEmitter = new StoreEmitter();
let memoryState: StoredQuotesData = loadInitialState();

function persistState() {
  try {
    localStorage.setItem(
      `${STORAGE_KEY_PREFIX}_state`,
      JSON.stringify(memoryState)
    );
  } catch {
    // quota fallback
  }
  storeEmitter.emitChange();
}

// Cross-tab synchronization
if (typeof window !== "undefined") {
  window.addEventListener("storage", (e) => {
    if (e.key === `${STORAGE_KEY_PREFIX}_state` && e.newValue) {
      try {
        memoryState = JSON.parse(e.newValue);
        storeEmitter.emitChange();
      } catch {
        // ignore
      }
    }
  });
}

export const supplierStore = {
  getState(): StoredQuotesData {
    return memoryState;
  },

  getRFQ(): RFQItem {
    return memoryState.rfq;
  },

  getQuotesForSupplier(supplierId: string): QuoteVersion[] {
    return memoryState.quotes[supplierId] || [];
  },

  getLatestQuote(supplierId: string): QuoteVersion | null {
    const list = memoryState.quotes[supplierId];
    if (!list || list.length === 0) return null;
    return list[list.length - 1];
  },

  getTargetForSupplier(supplierId: string): NegotiationTarget | null {
    return memoryState.targets[supplierId] || null;
  },

  getMessages(supplierId: string): ChatMessage[] {
    return memoryState.messages[supplierId] || [];
  },

  getSupplierStatus(supplierId: string): SupplierQuoteStatus {
    return memoryState.supplierStatuses[supplierId] || "received";
  },

  submitQuote(
    supplierId: string,
    data: {
      packPrice: number;
      packSize: number;
      freight: number;
      leadDays: number;
      moq?: number;
      maxQty?: number;
      taxRate?: number;
      priceIncludesTax?: boolean;
      notes?: string;
    }
  ): QuoteVersion {
    const rfq = memoryState.rfq;
    const calc = order(
      {
        id: supplierId,
        supplier: supplierId,
        item: rfq.item,
        packPrice: data.packPrice,
        packSize: data.packSize,
        freight: data.freight,
        leadDays: data.leadDays,
        moq: data.moq,
        raw: "",
        channel: "Portal",
      },
      rfq.qty
    );

    const prevList = memoryState.quotes[supplierId] || [];
    const nextVer = prevList.length + 1;

    const newQuote: QuoteVersion = {
      version: nextVer,
      packPrice: data.packPrice,
      packSize: data.packSize,
      freight: data.freight,
      leadDays: data.leadDays,
      moq: data.moq,
      maxQty: data.maxQty,
      taxRate: data.taxRate,
      priceIncludesTax: data.priceIncludesTax,
      notes: data.notes,
      submittedAt: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      landedCost: calc?.landed ?? data.packPrice * data.packSize + data.freight,
      units: calc?.units ?? rfq.qty,
      packs: calc?.packs ?? 1,
    };

    memoryState.quotes[supplierId] = [...prevList, newQuote];
    memoryState.supplierStatuses[supplierId] = "under_review";

    // If an active target was accepted by this revision, mark it
    if (memoryState.targets[supplierId]) {
      memoryState.targets[supplierId] = {
        ...memoryState.targets[supplierId]!,
        status: "accepted",
      };
    }

    persistState();
    return newQuote;
  },

  sendTarget(
    supplierId: string,
    target: {
      cutNeeded: number;
      targetFreight?: number;
      targetPerUnit?: number;
      concessionType: "freight" | "unit_price";
      message?: string;
    }
  ) {
    const newTarget: NegotiationTarget = {
      id: "tgt_" + Date.now(),
      supplierId,
      message:
        target.message ||
        (target.concessionType === "freight"
          ? `Cut freight to ₹${target.targetFreight} to win this order.`
          : `Reduce unit price by ₹${target.targetPerUnit} to win this order.`),
      cutNeeded: target.cutNeeded,
      targetFreight: target.targetFreight,
      targetPerUnit: target.targetPerUnit,
      concessionType: target.concessionType,
      sentAt: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      status: "pending",
    };

    memoryState.targets[supplierId] = newTarget;
    memoryState.supplierStatuses[supplierId] = "target_sent";

    // Add structured card into chat thread
    const chat = memoryState.messages[supplierId] || [];
    const targetChat: ChatMessage = {
      id: "msg_" + Date.now(),
      sender: "buyer",
      senderName: memoryState.rfq.buyerName,
      text: newTarget.message,
      target: newTarget,
      timestamp: newTarget.sentAt,
    };
    memoryState.messages[supplierId] = [...chat, targetChat];

    persistState();
  },

  sendMessage(supplierId: string, sender: "buyer" | "supplier", text: string, senderName: string) {
    const list = memoryState.messages[supplierId] || [];
    const msg: ChatMessage = {
      id: "msg_" + Date.now(),
      sender,
      senderName,
      text,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };
    memoryState.messages[supplierId] = [...list, msg];
    persistState();
  },

  addProduct(product: Omit<SupplierProduct, "id">) {
    const newProd: SupplierProduct = {
      ...product,
      id: "prod_" + Date.now(),
    };
    memoryState.products.push(newProd);
    persistState();
  },

  resetDemo() {
    localStorage.removeItem(`${STORAGE_KEY_PREFIX}_state`);
    memoryState = loadInitialState();
    persistState();
  },
};

/** React hook for live synced supplier & buyer data */
export function useSupplierStore() {
  const [, setTick] = useState(0);

  useEffect(() => {
    const handler = () => setTick((t) => t + 1);
    storeEmitter.addEventListener("change", handler);
    return () => storeEmitter.removeEventListener("change", handler);
  }, []);

  return supplierStore;
}
