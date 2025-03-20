import { Container, Paper, Space, Stack, Title } from "@mantine/core";
import React, { useEffect, useState } from "react";
import { Industry } from "../types.ts";
import { getIndustries } from "../utils";
import CombineAndCleanReviewsForm from "./CombineAndCleanReviewsForm";
import DeleteFileForm from "./DeleteFileForm";
import ManageIndustries from "./ManageIndustries";
import PastReviewsIndexManagement from "./PastReviewsIndexManagement";
import ProcessReviewsForm from "./ProcessReviewsForm";

const Dashboard: React.FC = () => {
    const [industries, setIndustries] = useState<Industry[]>([]);

    const fetchIndustries = async () => {
        try {
            const data = await getIndustries();
            setIndustries(data);
        } catch (error) {
            console.error("Error loading industries:", error);
        }
    };

    useEffect(() => {
        fetchIndustries();
    }, []);

    return (
        <Container size="lg" py="xl">
            <Title order={1} mb="xl">
                ダッシュボード
            </Title>
            <Stack gap="xl">
                <Paper shadow="sm" p="md" withBorder>
                    <CombineAndCleanReviewsForm industries={industries} />
                </Paper>
                <Paper shadow="sm" p="md" withBorder mt="xl">
                    <PastReviewsIndexManagement industries={industries} />
                </Paper>
                <Paper shadow="sm" p="md" withBorder>
                    <ProcessReviewsForm industries={industries} />
                </Paper>
                <Paper shadow="sm" p="md" withBorder>
                    <ManageIndustries industries={industries} fetchIndustries={fetchIndustries} />
                </Paper>
                <Paper shadow="sm" p="md" withBorder>
                    <DeleteFileForm industries={industries} />
                </Paper>
            </Stack>
            <Space h="xl" />
        </Container>
    );
};

export default Dashboard;
