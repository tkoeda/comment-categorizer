import { useEffect } from "react";
import { useAuth } from "../../context/AuthContext";

function LogoutPage() {
    const { logout } = useAuth();

    useEffect(() => {
        logout();
    }, [logout]);

    return null;
}

export default LogoutPage;
