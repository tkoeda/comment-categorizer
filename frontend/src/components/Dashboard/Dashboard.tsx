import { Container, Paper, Space, Stack, Title } from "@mantine/core";
import React, { useEffect, useState } from "react";
import { Industry } from "../../types/types";
import { getIndustries } from "../../utils/utils";
import DeleteFileForm from "../DeleteFileForm/DeleteFileForm";
import ManageIndustries from "../Industries/ManageIndustries";
import CombineAndCleanReviewsForm from "../Reviews/CombineAndCleanReviewsForm/CombineAndCleanReviewsForm";
import PastReviewsIndexManagement from "../Reviews/PastReviewsIndexManagement/PastReviewsIndexManagement";
import ProcessReviewsForm from "../Reviews/ProcessReviewsForm/ProcessReviewsForm";
function Dashboard(): React.ReactNode {
    const [industries, setIndustries] = useState<Industry[]>([]);
    const [refreshFlag, setRefreshFlag] = useState<boolean>(false);
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

    const triggerRefresh = () => {
        setRefreshFlag((prev) => !prev);
    };

    return (
        <Container size="lg" py="xl">
            <Title order={1} mb="xl">
                ダッシュボード
            </Title>
            <Stack gap="xl">
                <Paper shadow="sm" p="md" withBorder>
                    <CombineAndCleanReviewsForm
                        industries={industries}
                        onSuccess={triggerRefresh}
                    />
                </Paper>
                <Paper shadow="sm" p="md" withBorder mt="xl">
                    <PastReviewsIndexManagement
                        industries={industries}
                        refreshFlag={refreshFlag}
                    />
                </Paper>
                <Paper shadow="sm" p="md" withBorder>
                    <ProcessReviewsForm
                        industries={industries}
                        onSuccess={triggerRefresh}
                        refreshFlag={refreshFlag}
                    />
                </Paper>
                <Paper shadow="sm" p="md" withBorder>
                    <ManageIndustries
                        industries={industries}
                        fetchIndustries={fetchIndustries}
                    />
                </Paper>
                <Paper shadow="sm" p="md" withBorder>
                    <DeleteFileForm
                        industries={industries}
                        onSuccess={triggerRefresh}
                        refreshFlag={refreshFlag}
                    />
                </Paper>
            </Stack>
            <Space h="xl" />
        </Container>
    );
}

export default Dashboard;
