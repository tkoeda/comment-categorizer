import { MantineProvider } from "@mantine/core";
import "@mantine/core/styles.css";
import { Notifications } from "@mantine/notifications";
import "@mantine/notifications/styles.css";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import "./App.css";
import Dashboard from "./components/Dashboard/Dashboard";
import Login from "./components/Login/Login";
import LogoutPage from "./components/LogoutPage/LogoutPage";
import Navbar from "./components/Navbar/Navbar";
import ProtectedRoute from "./components/ProtectedRoute/ProtectedRoute";
import Register from "./components/Register/Register";
import SettingsPage from "./components/SettingsPage/SettingsPage";
import { AuthProvider } from "./context/AuthContext";

function RegisterAndLogout() {
    localStorage.clear();
    return <Register />;
}
function App() {
    return (
        <MantineProvider>
            <Notifications />
            <BrowserRouter>
                <AuthProvider>
                    <Navbar>
                        <Routes>
                            <Route
                                path="/dashboard"
                                element={
                                    <ProtectedRoute>
                                        <Dashboard />
                                    </ProtectedRoute>
                                }
                            />
                            <Route
                                path="/settings"
                                element={
                                    <ProtectedRoute>
                                        <SettingsPage />
                                    </ProtectedRoute>
                                }
                            />
                            <Route path="/login" element={<Login />} />
                            <Route path="/" element={<Login />} />
                            <Route path="/logout" element={<LogoutPage />} />
                            <Route
                                path="/register"
                                element={<RegisterAndLogout />}
                            />
                        </Routes>
                    </Navbar>
                </AuthProvider>
            </BrowserRouter>
        </MantineProvider>
    );
}

export default App;
