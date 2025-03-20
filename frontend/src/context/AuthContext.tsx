import { jwtDecode } from "jwt-decode";
import { createContext, ReactNode, useContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api/api";
import { ACCESS_TOKEN } from "../constants";

interface AuthContextType {
    isLoggedIn: boolean;
    isLoading: boolean;
    login: (accessToken: string) => void;
    logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
    children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
    const [isLoggedIn, setIsLoggedIn] = useState<boolean>(false);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const navigate = useNavigate();

    // This effect runs on initial load to check authentication status
    useEffect(() => {
        const checkAuth = async () => {
            setIsLoading(true);
            try {
                // Check if we have a token
                const token = localStorage.getItem(ACCESS_TOKEN);
                if (!token) {
                    setIsLoggedIn(false);
                    setIsLoading(false);
                    return;
                }

                // Check if token is expired
                try {
                    const decoded = jwtDecode(token);
                    const tokenExpiration = decoded.exp;
                    const now = Date.now() / 1000;

                    if (!tokenExpiration || tokenExpiration < now) {
                        // Token expired, try to refresh
                        const newToken = await refreshToken();
                        if (!newToken) {
                            setIsLoggedIn(false);
                        } else {
                            setIsLoggedIn(true);
                        }
                    } else {
                        // Valid token
                        setIsLoggedIn(true);
                    }
                } catch (decodeError) {
                    console.error("Error decoding token:", decodeError);
                    setIsLoggedIn(false);
                    localStorage.removeItem(ACCESS_TOKEN);
                }
            } catch (error) {
                console.error("Auth check error:", error);
                setIsLoggedIn(false);
            } finally {
                setIsLoading(false);
            }
        };

        checkAuth();
    }, []);

    const login = (accessToken: string) => {
        localStorage.setItem(ACCESS_TOKEN, accessToken);
        setIsLoggedIn(true);
    };

    const logout = async () => {
        try {
            // Call the backend logout endpoint
            // This will send the access token via Authorization header
            // and the refresh token via cookies due to withCredentials: true
            await api.post("/auth/logout");
        } catch (error) {
            console.error("Server logout failed:", error);
            // Continue with local logout even if server logout fails
        } finally {
            // Always clear local state regardless of server response
            localStorage.removeItem(ACCESS_TOKEN);
            setIsLoggedIn(false);
            navigate("/login", { replace: true });
        }
    };

    const refreshToken = async () => {
        try {
            const response = await api.post("/auth/refresh");
            console.log(response);
            if (response.status === 200 && response.data.access_token) {
                const { access_token } = response.data;

                localStorage.setItem(ACCESS_TOKEN, access_token);
                return access_token;
            }
            return null;
        } catch (error) {
            console.error("Error refreshing token:", error);
            localStorage.removeItem(ACCESS_TOKEN);
            return null;
        }
    };

    // Set up API interceptor to handle 401 errors
    useEffect(() => {
        const responseInterceptor = api.interceptors.response.use(
            (response) => response,
            async (error) => {
                const originalRequest = error.config;

                // If the error status is 401 and there hasn't been a retry yet
                if (error.response?.status === 401 && !originalRequest._retry) {
                    originalRequest._retry = true;

                    const newToken = await refreshToken();
                    if (newToken) {
                        originalRequest.headers.Authorization = `Bearer ${newToken}`;
                        return api(originalRequest);
                    } else {
                        logout();
                        return Promise.reject(error);
                    }
                }
                return Promise.reject(error);
            }
        );

        // Clean up interceptors when component unmounts
        return () => {
            api.interceptors.response.eject(responseInterceptor);
        };
    }, [navigate]);

    return (
        <AuthContext.Provider value={{ isLoggedIn, isLoading, login, logout }}>
            {children}
        </AuthContext.Provider>
    );
}

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error("useAuth must be used within an AuthProvider");
    }
    return context;
};
