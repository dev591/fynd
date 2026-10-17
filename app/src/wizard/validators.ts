import type { WizardDraft, Category, BusinessType } from "./types";

export interface IndianState {
  code: string;
  name: string;
}

export const INDIAN_STATES: IndianState[] = [
  { code: "01", name: "Jammu & Kashmir" },
  { code: "02", name: "Himachal Pradesh" },
  { code: "03", name: "Punjab" },
  { code: "04", name: "Chandigarh" },
  { code: "05", name: "Uttarakhand" },
  { code: "06", name: "Haryana" },
  { code: "07", name: "Delhi" },
  { code: "08", name: "Rajasthan" },
  { code: "09", name: "Uttar Pradesh" },
  { code: "10", name: "Bihar" },
  { code: "11", name: "Sikkim" },
  { code: "12", name: "Arunachal Pradesh" },
  { code: "13", name: "Nagaland" },
  { code: "14", name: "Manipur" },
  { code: "15", name: "Mizoram" },
  { code: "16", name: "Tripura" },
  { code: "17", name: "Meghalaya" },
  { code: "18", name: "Assam" },
  { code: "19", name: "West Bengal" },
  { code: "20", name: "Jharkhand" },
  { code: "21", name: "Odisha" },
  { code: "22", name: "Chhattisgarh" },
  { code: "23", name: "Madhya Pradesh" },
  { code: "24", name: "Gujarat" },
  { code: "26", name: "Dadra and Nagar Haveli and Daman and Diu" },
  { code: "27", name: "Maharashtra" },
  { code: "29", name: "Karnataka" },
  { code: "30", name: "Goa" },
  { code: "32", name: "Kerala" },
  { code: "33", name: "Tamil Nadu" },
  { code: "34", name: "Puducherry" },
  { code: "36", name: "Telangana" },
  { code: "37", name: "Andhra Pradesh" },
];

export const CATEGORIES: { id: Category; label: string }[] = [
  { id: "fasteners", label: "Fasteners & Bolts" },
  { id: "packaging", label: "Packaging Materials" },
  { id: "metals", label: "Metals & Alloys" },
  { id: "plastics", label: "Plastics & Polymers" },
  { id: "electricals", label: "Electricals & Motors" },
  { id: "chemicals", label: "Chemicals & Coatings" },
  { id: "tools", label: "Tools & Hardware" },
  { id: "other", label: "Other Industrial" },
];

export const BUSINESS_TYPES: { id: BusinessType; label: string; desc: string }[] = [
  { id: "manufacturer", label: "Manufacturer", desc: "Turns materials into finished components" },
  { id: "trader", label: "Trader", desc: "Buys and sells industrial products" },
  { id: "distributor", label: "Distributor", desc: "Stockist with local warehouse inventory" },
  { id: "other", label: "Other", desc: "Service partner, contractor, or fabricator" },
];

export const SPEND_BANDS = [
  "Under ₹5L",
  "₹5L to ₹20L",
  "₹20L to 1Cr",
  "Above ₹1Cr",
];

// Indian mobile: 10 digits starting 6, 7, 8, or 9
export function isValidIndianPhone(phone: string): boolean {
  const cleaned = phone.replace(/[\s\-+]/g, "").replace(/^91/, "");
  return /^[6-9]\d{9}$/.test(cleaned);
}

// GSTIN: 15 alphanumeric characters
export function isValidGstin(gstin: string): boolean {
  const cleaned = gstin.trim().toUpperCase();
  return /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$/.test(cleaned);
}

// PAN: 10 characters (5 letters, 4 numbers, 1 letter)
export function isValidPan(pan: string): boolean {
  const cleaned = pan.trim().toUpperCase();
  return /^[A-Z]{5}[0-9]{4}[A-Z]{1}$/.test(cleaned);
}

// PAN Masking: never return or store plain full PAN
export function maskPan(pan?: string): string | undefined {
  if (!pan) return undefined;
  const p = pan.trim().toUpperCase();
  if (p.length < 10) return undefined;
  return `${p.slice(0, 5)}XXXX${p.slice(9)}`;
}

// State cross-check against first 2 digits of GSTIN
export function getStateByGstin(gstin: string): IndianState | undefined {
  if (gstin.length < 2) return undefined;
  const code = gstin.slice(0, 2);
  return INDIAN_STATES.find((s) => s.code === code);
}

export function getStateGstCode(stateName: string): string | undefined {
  return INDIAN_STATES.find((s) => s.name === stateName)?.code;
}

export function isStateGstinMatch(stateName: string, gstin: string): boolean {
  const code = getStateGstCode(stateName);
  if (!code || gstin.length < 2) return false;
  return gstin.slice(0, 2) === code;
}

export function isPanGstinMatch(pan: string, gstin: string): boolean {
  const p = pan.trim().toUpperCase();
  const g = gstin.trim().toUpperCase();
  if (p.length !== 10 || g.length < 12) return false;
  return g.slice(2, 12) === p;
}

// Demo data for judges
export const DEMO_BUYER: WizardDraft = {
  step: 1,
  role: "buyer",
  full_name: "Ramesh Sharma",
  email: "ramesh.sharma@fanworks.in",
  phone: "9820144556",
  password: "Password@123",
  email_verified: true,
  company: "FanWorks Precision Manufacturing",
  business_type: "manufacturer",
  state: "Maharashtra",
  city: "Pune",
  categories: ["fasteners", "metals"],
  gstin: "27ABCDE1234F1Z5",
  pan: "ABCDE1234F",
  registry_verified: true,
  skipped_tax: false,
  buyer: {
    gst_claimable: true,
    spend_band: "₹20L to 1Cr",
    need_by_buffer_days: 5,
  },
  supplier: {
    default_lead_days: 3,
    gst_inclusive_default: false,
    regions: ["Maharashtra", "Gujarat"],
  },
};

export const DEMO_SUPPLIER: WizardDraft = {
  step: 1,
  role: "supplier",
  full_name: "Suresh Gupta",
  email: "suresh@boltexpress.co",
  phone: "9819022334",
  password: "Password@123",
  email_verified: true,
  company: "Bolt Express Industrial Distribution",
  business_type: "distributor",
  state: "Maharashtra",
  city: "Mumbai",
  categories: ["fasteners", "tools"],
  gstin: "27XYZAB5678C1Z2",
  pan: "XYZAB5678C",
  registry_verified: true,
  skipped_tax: false,
  buyer: {
    gst_claimable: false,
    spend_band: "₹5L to ₹20L",
    need_by_buffer_days: 3,
  },
  supplier: {
    default_lead_days: 3,
    gst_inclusive_default: false,
    regions: ["Maharashtra", "Gujarat", "Karnataka"],
  },
};
