import { ReactNode, useEffect } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";

interface ProtectedRouteProps {
    children: ReactNode;
}
function ProtectedRoute({ children }: ProtectedRouteProps) {
    const { isLoggedIn, isLoading } = useAuth();
    const location = useLocation();
    const navigate = useNavigate();
    useEffect(() => {
        if (!isLoading && !isLoggedIn) {
            navigate("/login", {
                replace: true,
                state: { from: location.pathname },
            });
        }
    }, [isLoggedIn, isLoading, navigate, location]);
    if (isLoading) {
        return <div>Loading...</div>;
    }

    return isLoggedIn ? (
        children
    ) : (
        <Navigate to="/login" state={{ from: location.pathname }} replace />
    );
}

export default ProtectedRoute;
