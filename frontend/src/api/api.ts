import axios from "axios";
import { ACCESS_TOKEN } from "../constants";

// const isDevelopment = import.meta.env.MODE === "development";
const myBaseUrl = import.meta.env.VITE_API_URL_LOCAL;

const api = axios.create({
    baseURL: myBaseUrl,
    withCredentials: true,
});

// Add authorization token to requests
api.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem(ACCESS_TOKEN);
        if (token) {
            config.headers["Authorization"] = `Bearer ${token}`;
        }
        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

// Add request transformer for FormData
api.interceptors.request.use((config) => {
    // Check if the data is FormData
    if (config.data instanceof FormData) {
        // Check if the FormData contains any File objects
        let containsFiles = false;
        for (const value of config.data.values()) {
            if (value instanceof File) {
                containsFiles = true;
                break;
            }
        }

        // Only transform FormData to URLSearchParams if it DOESN'T contain files
        if (!containsFiles) {
            // Convert FormData to URLSearchParams for FastAPI OAuth2
            const urlSearchParams = new URLSearchParams();
            for (const [key, value] of config.data.entries()) {
                urlSearchParams.append(key, value.toString());
            }
            config.data = urlSearchParams.toString();

            // Set content type to url-encoded for non-file FormData
            if (config.headers) {
                config.headers["Content-Type"] = "application/x-www-form-urlencoded";
            }
        } else {
            // For FormData with files, don't transform and don't set Content-Type
            // Let the browser set the correct multipart/form-data with boundary
            if (config.headers && config.headers["Content-Type"]) {
                delete config.headers["Content-Type"];
            }
        }
    }

    return config;
});

export default api;
