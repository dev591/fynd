"use strict";
/**
 * Profile Contract for FYND Wizard
 * Defines the complete user profile structure for buyer/supplier onboarding
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.VALID_STATE_CODES = exports.INDIAN_STATES = exports.CATEGORIES = void 0;
/**
 * Category options for buyer/supplier selection
 */
exports.CATEGORIES = [
    "fasteners",
    "packaging",
    "metals",
    "plastics",
    "electricals",
    "chemicals",
    "tools",
    "other"
];
/**
 * Indian states with their codes for GSTIN validation
 */
exports.INDIAN_STATES = {
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
exports.VALID_STATE_CODES = Object.keys(exports.INDIAN_STATES);
//# sourceMappingURL=types.js.map