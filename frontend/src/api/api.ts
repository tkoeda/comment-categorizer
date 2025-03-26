import axios from "axios";
import { ACCESS_TOKEN, apiUrl } from "../constants";

const api = axios.create({
    baseURL: apiUrl,
    withCredentials: true,
});

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

api.interceptors.request.use((config) => {
    if (config.data instanceof FormData) {
        let containsFiles = false;
        for (const value of config.data.values()) {
            if (value instanceof File) {
                containsFiles = true;
                break;
            }
        }

        if (!containsFiles) {
            const urlSearchParams = new URLSearchParams();
            for (const [key, value] of config.data.entries()) {
                urlSearchParams.append(key, value.toString());
            }
            config.data = urlSearchParams.toString();

            if (config.headers) {
                config.headers["Content-Type"] = "application/x-www-form-urlencoded";
            }
        } else {
            if (config.headers && config.headers["Content-Type"]) {
                delete config.headers["Content-Type"];
            }
        }
    }

    return config;
});

export default api;
