import { Container, Paper, Space, Tabs, Title } from "@mantine/core";
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

            {/* 
        Mantine Tabs 
        defaultValue sets the initially active tab 
        adjust the values (e.g. "combine", "past", "process", etc.) as you prefer 
      */}
            <Tabs defaultValue="combine">
                <Tabs.List>
                    <Tabs.Tab value="combine">レビュー結合・クリーニング</Tabs.Tab>
                    <Tabs.Tab value="past">過去レビューインデックス管理</Tabs.Tab>
                    <Tabs.Tab value="process">新規レビューの処理</Tabs.Tab>
                    <Tabs.Tab value="manage">業界管理</Tabs.Tab>
                    <Tabs.Tab value="delete">ファイル削除</Tabs.Tab>
                </Tabs.List>

                <Tabs.Panel value="combine" pt="md">
                    <Paper shadow="sm" p="md" withBorder>
                        <CombineAndCleanReviewsForm
                            industries={industries}
                            onSuccess={triggerRefresh}
                        />
                    </Paper>
                </Tabs.Panel>

                <Tabs.Panel value="past" pt="md">
                    <Paper shadow="sm" p="md" withBorder>
                        <PastReviewsIndexManagement
                            industries={industries}
                            refreshFlag={refreshFlag}
                        />
                    </Paper>
                </Tabs.Panel>

                <Tabs.Panel value="process" pt="md">
                    <Paper shadow="sm" p="md" withBorder>
                        <ProcessReviewsForm
                            industries={industries}
                            onSuccess={triggerRefresh}
                            refreshFlag={refreshFlag}
                        />
                    </Paper>
                </Tabs.Panel>

                <Tabs.Panel value="manage" pt="md">
                    <Paper shadow="sm" p="md" withBorder>
                        <ManageIndustries
                            industries={industries}
                            fetchIndustries={fetchIndustries}
                        />
                    </Paper>
                </Tabs.Panel>

                <Tabs.Panel value="delete" pt="md">
                    <Paper shadow="sm" p="md" withBorder>
                        <DeleteFileForm
                            industries={industries}
                            onSuccess={triggerRefresh}
                            refreshFlag={refreshFlag}
                        />
                    </Paper>
                </Tabs.Panel>
            </Tabs>

            <Space h="xl" />
        </Container>
    );
}

export default Dashboard;
