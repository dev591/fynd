/**
 * Validation utilities for Profile fields
 */

import {
  Role,
  BusinessType,
  Profile,
  INDIAN_STATES,
  VALID_STATE_CODES,
  CATEGORIES,
  Category
} from "../types";

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
export function validatePhone(phone: string): ValidationResult {
  if (!phone || phone.trim().length === 0) {
    return { isValid: false, error: "Phone number is required" };
  }

  const cleaned = phone.replace(/\D/g, "");

  if (cleaned.length !== 10) {
    return { isValid: false, error: "Phone number must be exactly 10 digits" };
  }

  if (!/^[6-9]/.test(cleaned)) {
    return { isValid: false, error: "Phone number must start with 6, 7, 8, or 9" };
  }

  return { isValid: true };
}

/**
 * Validates email format
 */
export function validateEmail(email: string): ValidationResult {
  if (!email || email.trim().length === 0) {
    return { isValid: false, error: "Email is required" };
  }

  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(email)) {
    return { isValid: false, error: "Invalid email format" };
  }

  return { isValid: true };
}

/**
 * Validates GSTIN (Goods and Services Tax Identification Number)
 * Format: 2 digits (state code) + 10 chars (PAN) + 1 digit + 1 alphanumeric + Z
 * Total: 15 characters
 */
export function validateGSTIN(gstin: string): ValidationResult {
  if (!gstin || gstin.trim().length === 0) {
    return { isValid: false, error: "GSTIN is required" };
  }

  const upperGstin = gstin.toUpperCase().replace(/\s/g, "");

  if (upperGstin.length !== 15) {
    return { isValid: false, error: "GSTIN must be exactly 15 characters" };
  }

  // Extract state code from first 2 digits
  const stateCode = upperGstin.substring(0, 2);
  if (!VALID_STATE_CODES.includes(stateCode)) {
    return { isValid: false, error: "Invalid state code in GSTIN" };
  }

  // GSTIN structure: 2-digit state + 13 alphanumeric + Z = 15
  // Validate that it ends with Z and the first 14 chars have correct pattern
  if (!upperGstin.endsWith("Z")) {
    return { isValid: false, error: "Invalid GSTIN format" };
  }

  // First 14 chars: 2 digits + 12 alphanumeric
  const gstinPattern = /^[0-9]{2}[A-Z0-9]{12}Z$/;
  if (!gstinPattern.test(upperGstin)) {
    return { isValid: false, error: "Invalid GSTIN format" };
  }

  return { isValid: true };
}

/**
 * Validates PAN (Permanent Account Number)
 * Format: 5 uppercase letters + 4 digits + 1 uppercase letter
 */
export function validatePAN(pan: string): ValidationResult {
  if (!pan || pan.trim().length === 0) {
    return { isValid: false, error: "PAN is required" };
  }

  const upperPan = pan.toUpperCase().replace(/\s/g, "");

  if (upperPan.length !== 10) {
    return { isValid: false, error: "PAN must be exactly 10 characters" };
  }

  // PAN format: 5 letters + 4 digits + 1 letter
  const panPattern = /^[A-Z]{5}[0-9]{4}[A-Z]{1}$/;
  if (!panPattern.test(upperPan)) {
    return { isValid: false, error: "Invalid PAN format (5 letters + 4 digits + 1 letter)" };
  }

  return { isValid: true };
}

/**
 * Validates that GSTIN and PAN are consistent
 * The first 5 characters of GSTIN should match the PAN (minus check digit)
 */
export function validateGSTINPANConsistency(gstin: string, pan: string): ValidationResult {
  const gstinValidation = validateGSTIN(gstin);
  if (!gstinValidation.isValid) {
    return { isValid: false, error: "Invalid GSTIN format" };
  }

  const panValidation = validatePAN(pan);
  if (!panValidation.isValid) {
    return { isValid: false, error: "Invalid PAN format" };
  }

  const upperGstin = gstin.toUpperCase().replace(/\s/g, "");
  const upperPan = pan.toUpperCase().replace(/\s/g, "");

  // GSTIN structure: SS(state 2 chars) + PAN(10 chars) + checkdigit(1) + entity(1) + Z(1)
  // Extract the 10-character PAN portion from GSTIN (positions 2-12)
  const gstinPanPart = upperGstin.substring(2, 12);
  // PAN is 10 characters
  const panFull = upperPan;

  if (gstinPanPart !== panFull) {
    return { isValid: false, error: "PAN and GSTIN are inconsistent (PAN portion must match exactly)" };
  }

  return { isValid: true };
}

/**
 * Validates state selection
 */
export function validateState(state: string): ValidationResult {
  if (!state || state.trim().length === 0) {
    return { isValid: false, error: "State is required" };
  }

  // Check if it's a state code
  if (VALID_STATE_CODES.includes(state)) {
    return { isValid: true };
  }

  // Check if it's a state name (case-insensitive)
  const stateName = Object.values(INDIAN_STATES).find(
    (name) => name.toLowerCase() === state.toLowerCase()
  );

  if (stateName) {
    return { isValid: true };
  }

  return {
    isValid: false,
    error: "Invalid state. Please select from the dropdown."
  };
}

/**
 * Gets state code from GSTIN
 */
export function getStateCodeFromGSTIN(gstin: string): string | null {
  const upperGstin = gstin.toUpperCase().replace(/\s/g, "");
  if (upperGstin.length !== 15) {
    return null;
  }
  return upperGstin.substring(0, 2);
}

/**
 * Validates business type
 */
export function validateBusinessType(type: string): ValidationResult {
  const validTypes: BusinessType[] = ["manufacturer", "trader", "distributor", "other"];

  if (!type || type.trim().length === 0) {
    return { isValid: false, error: "Business type is required" };
  }

  if (!validTypes.includes(type as BusinessType)) {
    return { isValid: false, error: "Invalid business type" };
  }

  return { isValid: true };
}

/**
 * Validates categories selection
 */
export function validateCategories(categories: string[]): ValidationResult {
  if (!categories || categories.length === 0) {
    return { isValid: false, error: "At least one category is required" };
  }

  const invalidCategories = categories.filter(
    (cat) => !CATEGORIES.includes(cat as Category)
  );

  if (invalidCategories.length > 0) {
    return { isValid: false, error: `Invalid categories: ${invalidCategories.join(", ")}` };
  }

  return { isValid: true };
}

/**
 * Validates buyer-specific fields
 */
export function validateBuyerFields(fields: Partial<Profile["buyer"]>): ValidationResult {
  if (fields.gst_claimable === undefined) {
    return { isValid: false, error: "GST claimable option is required" };
  }

  if (!fields.spend_band || fields.spend_band.trim().length === 0) {
    return { isValid: false, error: "Spend band is required" };
  }

  const validSpendBands = ["under_5L", "5L_to_20L", "20L_to_1Cr", "above_1Cr"];
  if (!validSpendBands.includes(fields.spend_band)) {
    return { isValid: false, error: "Invalid spend band" };
  }

  if (fields.need_by_buffer_days === undefined || fields.need_by_buffer_days < 0) {
    return { isValid: false, error: "Valid need-by buffer days is required" };
  }

  return { isValid: true };
}

/**
 * Validates supplier-specific fields
 */
export function validateSupplierFields(fields: Partial<Profile["supplier"]>): ValidationResult {
  if (fields.default_lead_days === undefined || fields.default_lead_days < 0) {
    return { isValid: false, error: "Valid default lead days is required" };
  }

  if (fields.gst_inclusive_default === undefined) {
    return { isValid: false, error: "GST inclusive default option is required" };
  }

  if (!fields.regions || fields.regions.length === 0) {
    return { isValid: false, error: "At least one region is required" };
  }

  // Validate each region
  for (const region of fields.regions) {
    const regionValidation = validateState(region);
    if (!regionValidation.isValid) {
      return { isValid: false, error: `Invalid region: ${region}` };
    }
  }

  return { isValid: true };
}

/**
 * Validates full name
 */
export function validateFullName(name: string): ValidationResult {
  if (!name || name.trim().length === 0) {
    return { isValid: false, error: "Full name is required" };
  }

  const trimmed = name.trim();
  if (trimmed.length < 2) {
    return { isValid: false, error: "Full name must be at least 2 characters" };
  }

  // Allow letters, spaces, hyphens, apostrophes
  if (!/^[a-zA-Z\s\-']+$/.test(trimmed)) {
    return { isValid: false, error: "Full name can only contain letters, spaces, hyphens, and apostrophes" };
  }

  return { isValid: true };
}

/**
 * Validates company name
 */
export function validateCompanyName(name: string): ValidationResult {
  if (!name || name.trim().length === 0) {
    return { isValid: false, error: "Company name is required" };
  }

  const trimmed = name.trim();
  if (trimmed.length < 2) {
    return { isValid: false, error: "Company name must be at least 2 characters" };
  }

  return { isValid: true };
}

/**
 * Validates city name
 */
export function validateCity(city: string): ValidationResult {
  if (!city || city.trim().length === 0) {
    return { isValid: false, error: "City is required" };
  }

  return { isValid: true };
}

/**
 * Validates password (basic validation, Supabase handles complexity)
 */
export function validatePassword(password: string): ValidationResult {
  if (!password || password.length === 0) {
    // Password is optional when using magic link
    return { isValid: true };
  }

  if (password.length < 8) {
    return { isValid: false, error: "Password must be at least 8 characters" };
  }

  return { isValid: true };
}

/**
 * Validates complete profile (for final submission)
 */
export function validateProfile(profile: Partial<Profile>): ValidationResult {
  // Required common fields
  if (!profile.full_name) {
    return { isValid: false, error: "Full name is required" };
  }

  const nameValidation = validateFullName(profile.full_name);
  if (!nameValidation.isValid) {
    return nameValidation;
  }

  if (!profile.email) {
    return { isValid: false, error: "Email is required" };
  }

  const emailValidation = validateEmail(profile.email);
  if (!emailValidation.isValid) {
    return emailValidation;
  }

  if (!profile.phone) {
    return { isValid: false, error: "Phone is required" };
  }

  const phoneValidation = validatePhone(profile.phone);
  if (!phoneValidation.isValid) {
    return phoneValidation;
  }

  if (!profile.company) {
    return { isValid: false, error: "Company name is required" };
  }

  const companyValidation = validateCompanyName(profile.company);
  if (!companyValidation.isValid) {
    return companyValidation;
  }

  if (!profile.business_type) {
    return { isValid: false, error: "Business type is required" };
  }

  if (!profile.state) {
    return { isValid: false, error: "State is required" };
  }

  const stateValidation = validateState(profile.state);
  if (!stateValidation.isValid) {
    return stateValidation;
  }

  if (!profile.city) {
    return { isValid: false, error: "City is required" };
  }

  if (!profile.categories || profile.categories.length === 0) {
    return { isValid: false, error: "At least one category is required" };
  }

  const categoryValidation = validateCategories(profile.categories);
  if (!categoryValidation.isValid) {
    return categoryValidation;
  }

  // Role-specific validation
  if (profile.role === "buyer") {
    if (!profile.buyer) {
      return { isValid: false, error: "Buyer details are required" };
    }
    const buyerValidation = validateBuyerFields(profile.buyer);
    if (!buyerValidation.isValid) {
      return buyerValidation;
    }
  }

  if (profile.role === "supplier") {
    if (!profile.supplier) {
      return { isValid: false, error: "Supplier details are required" };
    }
    const supplierValidation = validateSupplierFields(profile.supplier);
    if (!supplierValidation.isValid) {
      return supplierValidation;
    }
  }

  return { isValid: true };
}