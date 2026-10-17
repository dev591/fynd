/**
 * Profile Contract for FYND Wizard
 * Defines the complete user profile structure for buyer/supplier onboarding
 */

export type Role = "buyer" | "supplier";

export type BusinessType = "manufacturer" | "trader" | "distributor" | "other";

export type SpendBand = "under_5L" | "5L_to_20L" | "20L_to_1Cr" | "above_1Cr";

export type RegistryVerification = "none" | "demo" | "live";

export interface VerificationStatus {
  email: boolean;
  tax_ids_consistent: boolean;
  registry: RegistryVerification;
}

export interface BuyerProfile {
  gst_claimable: boolean;
  spend_band: SpendBand;
  need_by_buffer_days: number;
}

export interface SupplierProfile {
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
  categories: string[];
  gstin?: string;
  pan_masked?: string; // Never return the full PAN
  verification: VerificationStatus;
  buyer?: BuyerProfile;
  supplier?: SupplierProfile;
}

/**
 * Category options for buyer/supplier selection
 */
export const CATEGORIES = [
  "fasteners",
  "packaging",
  "metals",
  "plastics",
  "electricals",
  "chemicals",
  "tools",
  "other"
] as const;

export type Category = typeof CATEGORIES[number];

/**
 * Indian states with their codes for GSTIN validation
 */
export const INDIAN_STATES: Record<string, string> = {
  "01": "Jammu and Kashmir",
  "02": "Himachal Pradesh",
  "03": "Punjab",
  "04": "Chandigarh",
  "05": "Uttarakhand",
  "06": "Haryana",
  "07": "Delhi",
  "08": "Rajasthan",
  "09": "Uttar Pradesh",
  "10": "Bihar",
  "11": "Sikkim",
  "12": "Arunachal Pradesh",
  "13": "Nagaland",
  "14": "Manipur",
  "15": "Mizoram",
  "16": "Tripura",
  "17": "Meghalaya",
  "18": "Assam",
  "19": "West Bengal",
  "20": "Jharkhand",
  "21": "Odisha",
  "22": "Chhattisgarh",
  "23": "Madhya Pradesh",
  "24": "Gujarat",
  "25": "Daman and Diu",
  "26": "Dadra and Nagar Haveli",
  "27": "Maharashtra",
  "28": "Andhra Pradesh (Before Telangana)",
  "29": "Karnataka",
  "30": "Goa",
  "31": "Lakshadweep",
  "32": "Kerala",
  "33": "Tamil Nadu",
  "34": "Puducherry",
  "35": "Andaman and Nicobar Islands",
  "36": "Telangana",
  "37": "Andhra Pradesh",
  "38": "Ladakh",
  "39": "Other Territory",
  "97": "Other Territory"
};

/**
 * Valid state codes for GSTIN
 */
export const VALID_STATE_CODES = Object.keys(INDIAN_STATES);