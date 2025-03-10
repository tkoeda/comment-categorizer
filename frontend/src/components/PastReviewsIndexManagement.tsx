import {
    Alert,
    Button,
    Card,
    Divider,
    Group,
    List,
    Radio,
    Select,
    Stack,
    Text,
    Title
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import {
    IconAlertCircle,
    IconDatabase,
    IconRefresh
} from "@tabler/icons-react";
import React, { useEffect, useState } from "react";
import api from "../api/api";
import { Industry, ReviewLists } from "../types.ts";
import { loadFileLists } from "../utils";

interface PastReviewsIndexManagementProps {
    industries: Industry[];
}

const PastReviewsIndexManagement: React.FC<PastReviewsIndexManagementProps> = ({
    industries,
}) => {
    const [industryId, setIndustryId] = useState<number | null>(null);
    const [fileLists, setFileLists] = useState<ReviewLists | null>(null);
    const [selectedPastCleanedId, setSelectedPastCleanedId] = useState<
        number | null
    >(null);
    const [uploadMode, setUploadMode] = useState<"add" | "replace">("add");
    const [isProcessing, setIsProcessing] = useState<boolean>(false);
    const [indexStatus, setIndexStatus] = useState<{
        exists: boolean;
        count: number;
        lastUpdated: string;
    } | null>(null);

    useEffect(() => {
        const fetchData = async () => {
            if (industryId) {
                try {
                    const data: ReviewLists = await loadFileLists(industryId);
                    setFileLists(data);

                    await fetchIndexStatus();
                } catch (error) {
                    console.error("Error loading data", error);
                    notifications.show({
                        title: "Error",
                        message: "Failed to load data. Please try again.",
                        color: "red",
                    });
                }
            } else {
                setFileLists(null);
                setIndexStatus(null);
            }
        };

        fetchData();
    }, [industryId]);

    const fetchIndexStatus = async () => {
        if (!industryId) return;

        try {
            const indexResponse = await api.get(
                `/reviews/index_status/${industryId}`
            );
            console.log(indexResponse.data);
            setIndexStatus(indexResponse.data);
        } catch (error) {
            console.error("Error loading index status", error);
            setIndexStatus(null);
        }
    };
  
    const handleUpdateIndex = async () => {
        if (isProcessing || !selectedPastCleanedId || !industryId) return;

        setIsProcessing(true);

        const formData = new FormData();
        formData.append("industry_id", industryId.toString());
        formData.append("past_cleaned_id", selectedPastCleanedId.toString());
        formData.append("mode", uploadMode);

        try {
            const response = await api.post(
                "/reviews/update_past_reviews_index",
                formData,
                {
                    headers: { "Content-Type": "multipart/form-data" },
                }
            );

            notifications.show({
                title: "Success",
                message: response.data.message,
                color: "green",
            });

            await fetchIndexStatus();

            setSelectedPastCleanedId(null);
        } catch (error: any) {
            notifications.show({
                title: "Error",
                message: error.response?.data?.detail || error.message,
                color: "red",
                icon: <IconAlertCircle />,
            });
        } finally {
            setIsProcessing(false);
        }
    };

    return (
        <>
            <Title order={2} mb="md">
                過去のレビューインデックス管理"
            </Title>

            <Stack gap="lg">
                <Select
                    label="業界"
                    placeholder=""
                    data={industries.map((ind) => ({
                        value: ind.id.toString(),
                        label: ind.name,
                    }))}
                    value={industryId ? industryId.toString() : ""}
                    onChange={(value) => {
                        setIndustryId(value ? Number(value) : null);
                        setSelectedPastCleanedId(null);
                    }}
                    required
                    searchable
                />

                {industryId && (
                    <Card withBorder p="md" radius="md">
                        <Title order={3} size="h4">
                            インデックスステータス
                        </Title>

                        {indexStatus ? (
                            <List mt="sm">
                                <List.Item>
                                    ステータス:{" "}
                                    {indexStatus.exists ? "アクティブ" : "未作成"}
                                </List.Item>
                                {indexStatus.exists && (
                                    <>
                                        <List.Item>
                                            含まれるレビュー数: {indexStatus.count}
                                        </List.Item>
                                        <List.Item>
                                            最終更新日時:{" "}
                                            {new Date(
                                                indexStatus.lastUpdated
                                            ).toLocaleString()}
                                        </List.Item>
                                    </>
                                )}
                            </List>
                        ) : (
                            <Text c="dimmed" mt="sm">
                                インデックスのステータスを読み込み中...
                            </Text>
                        )}
                    </Card>
                )}

                <Divider label="インデックスの更新" labelPosition="center" />

                <Stack gap="md">
                    <Select
                        label="処理済み過去レビューを選択"
                        placeholder="インデックスに追加する処理済み過去レビューを選択"
                        data={
                            fileLists?.past?.cleaned.map((file) => ({
                                value: file.id.toString(),
                                label: file.display_name,
                            })) || []
                        }
                        value={
                            selectedPastCleanedId
                                ? selectedPastCleanedId.toString()
                                : ""
                        }
                        onChange={(value) =>
                            setSelectedPastCleanedId(value ? Number(value) : null)
                        }
                        disabled={!fileLists?.past?.cleaned.length || isProcessing}
                        required
                    />

                    <Radio.Group
                        label="インデックス更新モード"
                        value={uploadMode}
                        onChange={(value) =>
                            setUploadMode(value as "add" | "replace")
                        }
                    >
                        <Group mt="xs">
                            <Radio value="add" label="既存のインデックスに追加" />
                            <Radio
                                value="replace"
                                label="既存のインデックスを置き換え"
                            />
                        </Group>
                    </Radio.Group>

                    <Text size="sm" c="dimmed">
                        {uploadMode === "add"
                            ? "新しい過去レビューを既存のインデックスに追加し、以前の過去レビューをすべて保持します。"
                            : "インデックス全体をこれらの過去レビューのみに置き換えます。これにより既存のインデックスは削除されます。"}
                    </Text>

                    {uploadMode === "replace" && indexStatus?.exists && (
                        <Alert
                            color="orange"
                            title="警告：既存のインデックスを置き換えます"
                        >
                            {indexStatus.count}
                            件のレビューを含むインデックスを置き換えようとしています。
                            この操作は元に戻すことができません。
                        </Alert>
                    )}

                    <Button
                        onClick={handleUpdateIndex}
                        leftSection={
                            uploadMode === "add" ? (
                                <IconDatabase size={14} />
                            ) : (
                                <IconRefresh size={14} />
                            )
                        }
                        loading={isProcessing}
                        disabled={!selectedPastCleanedId || isProcessing}
                        color={uploadMode === "replace" ? "orange" : "blue"}
                    >
                        {uploadMode === "add"
                            ? "インデックスに追加"
                            : "インデックスを置き換え"}
                    </Button>
                </Stack>
            </Stack>
        </>
    );
};

export default PastReviewsIndexManagement;
