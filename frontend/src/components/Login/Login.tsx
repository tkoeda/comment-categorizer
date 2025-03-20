import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";

import AuthForm from "../AuthForm/AuthForm";
function Login() {
    const { isLoggedIn } = useAuth();
    const navigate = useNavigate();

    useEffect(() => {
        if (isLoggedIn) {
            navigate("/dashboard");
        }
    }, []);
    return <AuthForm route="/auth/login/" method="login" />;
}

export default Login;
