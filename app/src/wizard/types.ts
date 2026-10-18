export type Role = "buyer" | "supplier";

export type BusinessType = "manufacturer" | "trader" | "distributor" | "other";

export type Category =
  | "fasteners"
  | "packaging"
  | "metals"
  | "plastics"
  | "electricals"
  | "chemicals"
  | "tools"
  | "other";

export interface Verification {
  email: boolean;
  tax_ids_consistent: boolean;
  registry: "none" | "demo" | "live";
}

export interface BuyerSetup {
  gst_claimable: boolean;
  spend_band: string;
  need_by_buffer_days: number;
}

export interface SupplierSetup {
  default_lead_days: number;
  gst_inclusive_default: boolean;
  regions: string[];
}

export interface Profile {
  id: string;
  role: Role;
  full_name: string;
  email: string;
  phone: string;
  company: string;
  business_type: BusinessType;
  state: string;
  city: string;
  pincode?: string;
  address?: string;
  categories: string[];
  gstin?: string;
  pan_masked?: string; // never return the full PAN
  verification: Verification;
  buyer?: BuyerSetup;
  supplier?: SupplierSetup;
}

export interface WizardDraft {
  step: number;
  role: Role | null;
  // Screen 1: Account
  full_name: string;
  email: string;
  phone: string;
  password?: string;
  email_verified: boolean;
  // Screen 2: Business
  company: string;
  business_type: BusinessType;
  state: string;
  city: string;
  pincode: string;
  address: string;
  categories: Category[];
  // Screen 3: Tax IDs
  gstin: string;
  pan: string;
  registry_verified: boolean;
  skipped_tax: boolean;
  // Screen 4: Role Setup
  buyer: BuyerSetup;
  supplier: SupplierSetup;
}
