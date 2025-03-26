import {
    Alert,
    Anchor,
    Button,
    Checkbox,
    Group,
    Select,
    Stack,
    Text,
    Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import React, { useEffect, useState } from "react";

import { IconAlertCircle, IconDownload, IconInfoCircle } from "@tabler/icons-react";
import api from "../../../api/api";
import { Industry, ReviewItem } from "../../../types/types";
import { loadFileLists } from "../../../utils/utils";
interface ProcessReviewsFormProps {
    industries: Industry[];
    onSuccess: () => void;
    refreshFlag: boolean;
}

const ProcessReviewsForm: React.FC<ProcessReviewsFormProps> = ({
    industries,
    onSuccess,
    refreshFlag,
}) => {
    const [industryId, setIndustryId] = useState<number | null>(null);
    const [fileLists, setFileLists] = useState<ReviewItem[] | null>(null);
    const [selectedNewCleanedReviewId, setSelectedNewCleanedReviewId] = useState<
        number | null
    >(null);
    const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
    const [usePastReviews, setUsePastReviews] = useState<boolean>(false);
    const [indexStatus, setIndexStatus] = useState<{
        exists: boolean;
        count: number;
        lastUpdated: string;
    }>({
        exists: false,
        count: 0,
        lastUpdated: "",
    });
    const [isLoading, setIsLoading] = useState<boolean>(false);

    useEffect(() => {
        const fetchData = async () => {
            if (industryId) {
                setIsLoading(true);
                try {
                    const data: ReviewItem[] = await loadFileLists(
                        industryId,
                        "new",
                        "cleaned"
                    );
                    setFileLists(data);
                    try {
                        const indexResponse = await api.get(
                            `/index/status/${industryId}`
                        );
                        setIndexStatus(indexResponse.data);
                    } catch (error) {
                        console.error("Error loading index status", error);
                        setIndexStatus({ exists: false, count: 0, lastUpdated: "" });
                    }
                } catch (error) {
                    console.error("Error loading file lists", error);
                } finally {
                    setIsLoading(false);
                }
            } else {
                setFileLists(null);
            }
        };

        fetchData();
    }, [industryId, refreshFlag]);

    const resetForm = () => {
        setSelectedNewCleanedReviewId(null);
    };

    const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        if (isSubmitting) return;

        setIsSubmitting(true);

        const payload = {
            industry_id: industryId,
            new_cleaned_id: selectedNewCleanedReviewId,
            use_past_reviews: usePastReviews,
        };
        try {
            const response = await api.post("/reviews/process_reviews", payload, {
                responseType: "blob",
                headers: { "Content-Type": "application/json" },
            });
            console.log("response headers:", response.headers);
            onSuccess();
            const blob = new Blob([response.data], {
                type: response.headers["content-type"],
            });
            let filename = "downloaded-file.xlsx";
            const encodedFilename = response.headers["x-filename-base64"];

            if (encodedFilename) {
                try {
                    filename = atob(encodedFilename);
                    filename = new TextDecoder("utf-8").decode(
                        new Uint8Array([...filename].map((c) => c.charCodeAt(0)))
                    );
                } catch (e) {
                    console.error("Error decoding filename:", e);
                }
            }
            const url = window.URL.createObjectURL(blob);
            notifications.show({
                title: "成功",
                message: (
                    <>
                        <Text>処理が正常に完了しました！</Text>
                        <Anchor href={url} download={filename} mt="xs">
                            処理済みファイルをダウンロード
                        </Anchor>
                    </>
                ),
                color: "green",
                icon: <IconDownload />,
                autoClose: false,
            });
        } catch (error: any) {
            console.error("Request error:", error);

            // Handle the case where error.response.data is a Blob
            if (error.response && error.response.data instanceof Blob) {
                // Read the blob as text and parse it
                const blobText = await error.response.data.text();
                try {
                    const errorJson = JSON.parse(blobText);
                    notifications.show({
                        title: "エラー",
                        message: errorJson.detail || "Unknown error occurred",
                        color: "red",
                        icon: <IconAlertCircle />,
                    });
                } catch {
                    // Fallback if JSON parsing fails
                    notifications.show({
                        title: "エラー",
                        message: "An error occurred processing your request",
                        color: "red",
                        icon: <IconAlertCircle />,
                    });
                }
            } else {
                // Handle normal error objects
                notifications.show({
                    title: "エラー",
                    message:
                        error.response?.data?.detail ||
                        error.message ||
                        "An error occurred",
                    color: "red",
                    icon: <IconAlertCircle />,
                });
            }
        } finally {
            resetForm();
            setIsSubmitting(false);
        }
    };

    const isProcessButtonDisabled = () => {
        if (isSubmitting || isLoading) return true;
        if (!industryId || !selectedNewCleanedReviewId) return true;
        if (usePastReviews && !indexStatus.exists) return true;

        return false;
    };

    return (
        <form onSubmit={handleSubmit}>
            <Title order={2} mb="md">
                保存したレビューをChatGPTに投げる
            </Title>

            <Stack gap="md">
                <Select
                    label="業界"
                    placeholder="業界を選択"
                    data={industries.map((ind) => ({
                        value: ind.id.toString(),
                        label: ind.name,
                    }))}
                    value={industryId ? industryId.toString() : null}
                    onChange={(value) => setIndustryId(value ? Number(value) : null)}
                    required
                    searchable
                    disabled={isSubmitting}
                    clearable
                />

                <Checkbox
                    label="分類精度向上のために過去のレビューを使用する"
                    checked={usePastReviews}
                    onChange={(event) =>
                        setUsePastReviews(event.currentTarget.checked)
                    }
                    disabled={isSubmitting}
                />

                {usePastReviews && (
                    <Alert
                        icon={<IconInfoCircle size="1rem" />}
                        color={indexStatus.exists ? "blue" : "yellow"}
                    >
                        {indexStatus.exists ? (
                            <>
                                <Text fw={500}>
                                    過去のインデックスが利用可能です
                                </Text>
                                <Text size="sm">
                                    {indexStatus.count}{" "}
                                    件の過去レビューがインデックス化されています。最終更新日：{" "}
                                    {new Date(
                                        indexStatus.lastUpdated
                                    ).toLocaleDateString()}
                                </Text>
                            </>
                        ) : (
                            <>
                                <Text fw={500}>
                                    過去のインデックスが見つかりません
                                </Text>
                                <Text size="sm">
                                    この業界のインデックスは存在しません。過去のレビューなしで分類を続行します。インデックスを作成するには、インデックス管理セクションを使用してください。
                                </Text>
                            </>
                        )}
                    </Alert>
                )}

                <Select
                    label="クリーニング済みファイルを選択"
                    placeholder="クリーニング済みファイルを選択"
                    data={fileLists?.map((file) => ({
                        value: file.id.toString(),
                        label: file.display_name,
                    }))}
                    value={
                        selectedNewCleanedReviewId
                            ? selectedNewCleanedReviewId.toString()
                            : null
                    }
                    onChange={(value) =>
                        setSelectedNewCleanedReviewId(value ? Number(value) : null)
                    }
                    disabled={fileLists?.length === 0 || isSubmitting}
                    required
                    clearable
                />

                <Group justify="center" mt="md">
                    <Button
                        type="submit"
                        loading={isSubmitting}
                        disabled={isProcessButtonDisabled()}
                    >
                        カテゴリ分類を実行
                    </Button>
                </Group>
            </Stack>
        </form>
    );
};

export default ProcessReviewsForm;
