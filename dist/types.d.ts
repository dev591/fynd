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
    pan_masked?: string;
    verification: VerificationStatus;
    buyer?: BuyerProfile;
    supplier?: SupplierProfile;
}
/**
 * Category options for buyer/supplier selection
 */
export declare const CATEGORIES: readonly ["fasteners", "packaging", "metals", "plastics", "electricals", "chemicals", "tools", "other"];
export type Category = typeof CATEGORIES[number];
/**
 * Indian states with their codes for GSTIN validation
 */
export declare const INDIAN_STATES: Record<string, string>;
/**
 * Valid state codes for GSTIN
 */
export declare const VALID_STATE_CODES: string[];
//# sourceMappingURL=types.d.ts.map