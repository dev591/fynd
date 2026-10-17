/**
 * Validation utilities for Profile fields
 */
import { Profile } from "../types";
/**
 * Validation result interface
 */
export interface ValidationResult {
    isValid: boolean;
    error?: string;
}
/**
 * Validates Indian mobile phone number
 * Rules: 10 digits, starts with 6-9
 */
export declare function validatePhone(phone: string): ValidationResult;
/**
 * Validates email format
 */
export declare function validateEmail(email: string): ValidationResult;
/**
 * Validates GSTIN (Goods and Services Tax Identification Number)
 * Format: 2 digits (state code) + 10 chars (PAN) + 1 digit + 1 alphanumeric + Z
 * Total: 15 characters
 */
export declare function validateGSTIN(gstin: string): ValidationResult;
/**
 * Validates PAN (Permanent Account Number)
 * Format: 5 uppercase letters + 4 digits + 1 uppercase letter
 */
export declare function validatePAN(pan: string): ValidationResult;
/**
 * Validates that GSTIN and PAN are consistent
 * The first 5 characters of GSTIN should match the PAN (minus check digit)
 */
export declare function validateGSTINPANConsistency(gstin: string, pan: string): ValidationResult;
/**
 * Validates state selection
 */
export declare function validateState(state: string): ValidationResult;
/**
 * Gets state code from GSTIN
 */
export declare function getStateCodeFromGSTIN(gstin: string): string | null;
/**
 * Validates business type
 */
export declare function validateBusinessType(type: string): ValidationResult;
/**
 * Validates categories selection
 */
export declare function validateCategories(categories: string[]): ValidationResult;
/**
 * Validates buyer-specific fields
 */
export declare function validateBuyerFields(fields: Partial<Profile["buyer"]>): ValidationResult;
/**
 * Validates supplier-specific fields
 */
export declare function validateSupplierFields(fields: Partial<Profile["supplier"]>): ValidationResult;
/**
 * Validates full name
 */
export declare function validateFullName(name: string): ValidationResult;
/**
 * Validates company name
 */
export declare function validateCompanyName(name: string): ValidationResult;
/**
 * Validates city name
 */
export declare function validateCity(city: string): ValidationResult;
/**
 * Validates password (basic validation, Supabase handles complexity)
 */
export declare function validatePassword(password: string): ValidationResult;
/**
 * Validates complete profile (for final submission)
 */
export declare function validateProfile(profile: Partial<Profile>): ValidationResult;
//# sourceMappingURL=index.d.ts.map