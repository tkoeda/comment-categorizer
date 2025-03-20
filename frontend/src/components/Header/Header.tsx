import { ActionIcon, Button, Group } from "@mantine/core";
import { IconLogout, IconUser } from "@tabler/icons-react";
import React from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";

import BackButton from "../Buttons/BackButton/BackButton";

interface NavButtonProps {
    to?: string;
    onClick?: () => void;
    label?: string;
    icon?: React.ReactNode;
    variant?: string;
}

function Header() {
    const { isLoggedIn, logout } = useAuth();

    const handleLogout = () => {
        logout();
    };

    const NavButton: React.FC<NavButtonProps> = ({
        to,
        onClick,
        label,
        icon,
        variant = "ghost",
    }) => {
        if (!label) {
            if (onClick) {
                return (
                    <ActionIcon onClick={onClick} variant={variant} size="lg">
                        {icon}
                    </ActionIcon>
                );
            }
            return (
                <ActionIcon component={Link} to={to!} variant={variant} size="lg">
                    {icon}
                </ActionIcon>
            );
        }

        if (onClick) {
            return (
                <Button onClick={onClick} variant={variant} leftSection={icon}>
                    {label}
                </Button>
            );
        }

        return (
            <Button component={Link} to={to!} variant={variant} leftSection={icon}>
                {label}
            </Button>
        );
    };

    const navItems = (
        <>
            {isLoggedIn ? (
                <NavButton
                    onClick={handleLogout}
                    label="ログアウト"
                    icon={<IconLogout />}
                    variant="transparent"
                />
            ) : (
                <>
                    <NavButton to="/login" label="ログイン" />
                    <NavButton
                        to="/register"
                        label="サインアップ"
                        variant="default"
                    />
                </>
            )}

            <>{isLoggedIn && <NavButton to="/settings" icon={<IconUser />} />}</>
        </>
    );

    return (
        <>
            <Group justify="space-between" h="100%">
                <Group>
                    {isLoggedIn && (
                        <NavButton to="/dashboard" label="ダッシュボード" />
                    )}
                </Group>
                <Group>{navItems}</Group>
            </Group>
            <BackButton />
        </>
    );
}

export default Header;
