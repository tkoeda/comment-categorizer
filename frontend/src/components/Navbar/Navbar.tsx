import { AppShell, Container } from "@mantine/core";
import { ReactNode } from "react";
import Header from "../Header/Header";
import styles from "./Navbar.module.css";
interface NavbarProps {
    children: ReactNode;
}
function Navbar({ children }: NavbarProps) {
    return (
        <AppShell>
            <AppShell.Header className={styles.header}>
                <Header />
            </AppShell.Header>

            <AppShell.Main>
                <Container size="xl">{children}</Container>
            </AppShell.Main>
        </AppShell>
    );
}

export default Navbar;
