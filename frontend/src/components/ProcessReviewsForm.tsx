import {
    Alert,
    Anchor,
    Button,
    Checkbox,
    Group,
    Select,
    Stack,
    Text,
    Title
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import React, { useEffect, useState } from "react";

import { IconAlertCircle, IconDownload, IconInfoCircle } from "@tabler/icons-react";
import api from "../api/api";
import { Industry, ReviewLists } from "../types.ts";
import { loadFileLists } from "../utils";
interface ProcessReviewsFormProps {
    industries: Industry[]; 
}

const ProcessReviewsForm: React.FC<ProcessReviewsFormProps> = ({ industries }) => {
    const [industryId, setIndustryId] = useState<number | null>(null);
    const [fileLists, setFileLists] = useState<ReviewLists | null>(null);
    const [selectedNewCleanedReviewId, setSelectedNewCleanedReviewId] = useState<number | null>(null);
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
                    const data: ReviewLists = await loadFileLists(
                        industryId,
                    );
                    setFileLists(data);
                    try {
                        const indexResponse = await api.get(
                            `/reviews/index_status/${industryId}`
                        );
                        setIndexStatus(indexResponse.data);
                        console.log(indexResponse.data)
                    } catch (error) {
                        console.error("Error loading index status", error);
                        setIndexStatus({exists: false, count: 0, lastUpdated: ""});
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
    }, [industryId]);  

    const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        if (isSubmitting) return; 
        
        setIsSubmitting(true);
        
        const formData = new FormData();
        formData.append("industry_id", industryId!.toString());
        formData.append("new_cleaned_id", selectedNewCleanedReviewId!.toString());
        formData.append("use_past_reviews", usePastReviews.toString());
        console.log(usePastReviews)
        
        try {
            const response = await api.post(
                "/reviews/process_reviews",
                formData,
                {
                    responseType: "blob",
                    headers: { "Content-Type": "multipart/form-data" },
                }
            );
            
            const blob = new Blob([response.data], {
                type: response.headers["content-type"],
            });
            const url = window.URL.createObjectURL(blob);
            notifications.show({
                title: "成功",
                message: (
                    <>
                        <Text>処理が正常に完了しました！</Text>
                        <Anchor
                            href={url}
                            download="categorized_reviews.xlsx"
                            mt="xs"
                        >
                            処理済みファイルをダウンロード
                        </Anchor>
                    </>
                ),
                color: "green",
                icon: <IconDownload />,
                autoClose: false,
            });
        } catch (error: any) {
            notifications.show({
                title: "エラー",
                message: error.response?.data?.detail || error.message,
                color: "red",
                icon: <IconAlertCircle />,
            });
        } finally {
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
                ステップ3: 保存したレビューをChatGPTに投げる
            </Title>

            <Stack gap="md">
                <Select
                    label="業界"
                    placeholder="業界を選択"
                    data={industries.map((ind) => ({
                        value: ind.id.toString(),
                        label: ind.name,
                    }))}
                    value={industryId ? industryId.toString() : ""}
                    onChange={(value) => setIndustryId(value ? Number(value) : null)}
                    required
                    searchable
                    disabled={isSubmitting}
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
                    data={fileLists?.new?.cleaned.map((file) => ({
                        value: file.id.toString(),
                        label: file.display_name,
                    }))}
                    value={selectedNewCleanedReviewId?.toString()}
                    onChange={(value) =>
                        setSelectedNewCleanedReviewId(value ? Number(value) : null)
                    }
                    disabled={fileLists?.new?.cleaned.length === 0 || isSubmitting}
                    required
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
