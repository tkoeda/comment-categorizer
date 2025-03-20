import { ActionIcon } from "@mantine/core";
import { IconChevronLeft } from "@tabler/icons-react";
import { useLocation, useNavigate } from "react-router-dom";

import styles from "./BackButton.module.css";

function BackButton() {
    const navigate = useNavigate();
    const location = useLocation();

    // Don't show back button on these routes
    const hideBackButtonRoutes = ["/", "/login", "/register", "/logout"];

    // Show back button on these paths and their sub-paths
    const showBackButtonPaths = ["/mypage"];

    const shouldShowBackButton = () => {
        // Don't show on specific routes
        if (hideBackButtonRoutes.includes(location.pathname)) {
            return false;
        }

        // Show if the current path starts with any of the showBackButtonPaths
        return showBackButtonPaths.some((path) =>
            location.pathname.startsWith(path)
        );
    };

    if (!shouldShowBackButton()) {
        return null;
    }

    return (
        <ActionIcon
            variant="subtle"
            onClick={() => navigate(-1)}
            className={styles.backButton}
        >
            <IconChevronLeft size={18} />
        </ActionIcon>
    );
}

export default BackButton;
