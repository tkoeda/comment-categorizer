// ===========================
// Auth Tokens
// ===========================
export const ACCESS_TOKEN = "access_token";
export const REFRESH_TOKEN = "refresh_token";

// ===========================
// Environment Configuration
// ===========================
const isDevelopment = import.meta.env.MODE === "development";

export const myBaseUrl = isDevelopment
    ? import.meta.env.VITE_API_URL_LOCAL // e.g., http://localhost:8000
    : import.meta.env.VITE_API_URL_DEPLOY; // e.g., https://your-domain.com

// ===========================
// API Path Configuration
// ===========================
export const apiVersionPath = "/api/v1";

// Full API URL
export const apiUrl = `${myBaseUrl}${apiVersionPath}`;
