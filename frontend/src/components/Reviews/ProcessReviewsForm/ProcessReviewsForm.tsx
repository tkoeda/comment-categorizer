import {
    Alert,
    Anchor,
    Button,
    Card,
    Checkbox,
    Group,
    LoadingOverlay,
    Modal,
    Progress,
    Select,
    Stack,
    Text,
    Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconAlertCircle } from "@tabler/icons-react";
import React, { useEffect, useState } from "react";
import api from "../../../api/api";
import { apiVersionPath, myBaseUrl } from "../../../constants";
import { Industry, ReviewItem } from "../../../types/types";
import { loadFileLists } from "../../../utils/utils";

interface JobStatus {
    job_id: string;
    status: "pending" | "processing" | "completed" | "failed" | "cancelled";
    progress?: number;
    final_review_id?: number;
    error?: string;
    created_at: string;
    updated_at: string;
}

interface ProcessReviewsProps {
    industries: Industry[];
    refreshFlag: boolean;
    onSuccess: (finalReviewId: number) => void;
}

const ProcessReviewsComponent: React.FC<ProcessReviewsProps> = ({
    industries,
    refreshFlag,
    onSuccess,
}) => {
    // Form state
    const [industryId, setIndustryId] = useState<number | null>(null);
    const [fileLists, setFileLists] = useState<ReviewItem[]>([]);
    const [selectedReviewId, setSelectedReviewId] = useState<number | null>(null);
    const [usePastReviews, setUsePastReviews] = useState<boolean>(false);
    const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

    // Job status state
    const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
    const [showJobModal, setShowJobModal] = useState<boolean>(false);

    // WebSocket state
    const [socket, setSocket] = useState<WebSocket | null>(null);
    const pollingTimeoutRef = React.useRef<NodeJS.Timeout | null>(null);

    const isCancelButtonDisabled = () => {
        return !jobStatus || !["pending", "processing"].includes(jobStatus.status);
    };

    // Load file lists and check for active review job when industry changes
    useEffect(() => {
        const fetchData = async () => {
            if (industryId) {
                try {
                    const data: ReviewItem[] = await loadFileLists(
                        industryId,
                        "new",
                        "cleaned"
                    );
                    setFileLists(data);
                    // Check for any active review job for this industry
                    fetchActiveJob();
                } catch (error: any) {
                    console.error("Error loading data", error);
                    notifications.show({
                        title: "Error",
                        message:
                            error.response?.data?.detail ||
                            "予期しないエラーが発生しました。",
                        color: "red",
                    });
                }
            } else {
                setFileLists([]);
                setJobStatus(null);
            }
        };

        fetchData();
    }, [industryId, refreshFlag]);

    const fetchActiveJob = async () => {
        try {
            const response = await api.get("/jobs/active_review_job");
            if (response.data && response.data.job_id) {
                setJobStatus(response.data);
                if (["pending", "processing"].includes(response.data.status)) {
                    connectWebSocket(response.data.job_id);
                    setShowJobModal(true);
                }
            } else {
                setJobStatus(null);
            }
        } catch (error) {
            console.error("Error fetching active job", error);
            setJobStatus(null);
        }
    };

    // Connect to WebSocket for real-time updates
    const connectWebSocket = (id: string) => {
        // Close existing socket if any
        if (socket) {
            socket.close();
            setSocket(null);
        }

        // Construct the WebSocket URL
        const baseUrl = myBaseUrl;
        const wsProtocol = baseUrl.startsWith("https") ? "wss:" : "ws:";
        const wsHost = new URL(baseUrl).host;
        const wsUrl = `${wsProtocol}//${wsHost}${apiVersionPath}/ws/review_job/${id}`;

        console.log("Connecting to WebSocket:", wsUrl);

        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            console.log(`WebSocket connected for job ${id}`);
        };

        ws.onmessage = (event) => {
            console.log("WebSocket message received:", event.data);
            try {
                const data = JSON.parse(event.data);
                setJobStatus(data);

                // Handle callbacks on completion or failure
                if (data.status === "completed" && data.final_review_id) {
                    notifications.show({
                        title: "完了",
                        message: "レビューの処理が正常に完了しました。",
                        color: "green",
                    });
                    onSuccess(data.final_review_id);
                    resetForm();
                } else if (data.status === "failed" && data.error) {
                    notifications.show({
                        title: "失敗",
                        message: data.error,
                        color: "red",
                    });
                    resetForm();
                } else if (data.status === "cancelled") {
                    notifications.show({
                        title: "キャンセル",
                        message: "レビューの処理がキャンセルされました。",
                        color: "orange",
                    });
                    resetForm();
                }
            } catch (error) {
                console.error("Error parsing WebSocket message:", error);
            }
        };

        ws.onerror = (error) => {
            console.error("WebSocket error:", error);
            notifications.show({
                title: "WebSocket接続エラー",
                message: "更新情報を受信できません。",
                color: "red",
            });
        };

        ws.onclose = () => {
            console.log(`WebSocket closed for job ${id}`);
            setSocket(null);
        };

        setSocket(ws);
    };

    // Effect for WebSocket connection management
    useEffect(() => {
        if (jobStatus && jobStatus.status === "pending" && !socket) {
            console.log("Initializing WebSocket for job:", jobStatus.job_id);
            connectWebSocket(jobStatus.job_id);
        }

        // Clean up function
        return () => {
            if (socket) {
                console.log("Closing WebSocket connection on cleanup");
                socket.close();
                setSocket(null);
            }

            if (pollingTimeoutRef.current) {
                clearTimeout(pollingTimeoutRef.current);
                pollingTimeoutRef.current = null;
            }
        };
    }, []);

    // Fetch active job on component mount
    useEffect(() => {
        fetchActiveJob();
    }, []);

    // Form submission handler: create a review processing job
    const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        if (isSubmitting || !industryId || !selectedReviewId) return;

        if (pollingTimeoutRef.current) {
            clearTimeout(pollingTimeoutRef.current);
            pollingTimeoutRef.current = null;
        }

        setIsSubmitting(true);
        setJobStatus(null);

        const payload = {
            industry_id: industryId,
            new_cleaned_id: selectedReviewId,
            use_past_reviews: usePastReviews,
        };
        try {
            const response = await api.post("/jobs/review_jobs", payload, {
                headers: { "Content-Type": "application/json" },
            });

            console.log("Job started response:", response.data);

            // Set initial status
            setJobStatus({
                job_id: response.data.job_id,
                status: response.data.status,
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
            });

            setShowJobModal(true);

            // Connect to WebSocket for real-time updates
            try {
                console.log("Attempting WebSocket connection");
                connectWebSocket(response.data.job_id);
            } catch (error) {
                console.log("WebSocket connection failed:", error);
            }

            notifications.show({
                title: "処理開始",
                message: "レビュー処理ジョブが開始されました",
                color: "blue",
            });
        } catch (error: any) {
            console.error("Error starting job", error);
            resetForm();
            notifications.show({
                title: "エラー",
                message:
                    error.response?.data?.detail ||
                    "処理の開始中にエラーが発生しました。",
                color: "red",
                icon: <IconAlertCircle />,
            });
        } finally {
            setIsSubmitting(false);
        }
    };

    // Job cancellation handler
    const handleCancelProcess = async () => {
        if (!jobStatus) return;
        try {
            console.log("Canceling job:", jobStatus.job_id);
            const response = await api.post(
                `/jobs/review_jobs/${jobStatus.job_id}/cancel`
            );
            console.log("Cancel response:", response.data);
            notifications.show({
                title: "キャンセル要求",
                message: "ジョブのキャンセルを要求しました。",
                color: "orange",
            });
        } catch (error: any) {
            notifications.show({
                title: "キャンセルエラー",
                message: error.response?.data?.detail || error.message,
                color: "red",
            });
        }
    };

    // Reset form and job state
    const resetForm = () => {
        setSelectedReviewId(null);
        setJobStatus(null);
        setShowJobModal(false);
        setUsePastReviews(false);
        setIsSubmitting(false);

        // Close WebSocket if open
        if (socket) {
            socket.close();
            setSocket(null);
        }
    };

    // Helper function for status color
    const getStatusColor = (status: string) => {
        switch (status) {
            case "pending":
                return "yellow";
            case "processing":
                return "blue";
            case "completed":
                return "green";
            case "failed":
                return "red";
            case "cancelled":
                return "orange";
            default:
                return "gray";
        }
    };

    // Helper function for status text
    const getStatusText = (status: string) => {
        switch (status) {
            case "pending":
                return "待機中";
            case "processing":
                return "処理中";
            case "completed":
                return "完了";
            case "failed":
                return "失敗";
            case "cancelled":
                return "キャンセル済み";
            default:
                return "不明";
        }
    };

    return (
        <>
            <form onSubmit={handleSubmit}>
                <Title order={2} mb="md">
                    レビュー処理＆インデックス管理
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
                        onChange={(value) => {
                            setIndustryId(value ? Number(value) : null);
                            setSelectedReviewId(null);
                        }}
                        required
                        searchable
                        clearable
                        disabled={isSubmitting}
                    />

                    <Checkbox
                        label="分類精度向上のために過去のレビューを使用する"
                        checked={usePastReviews}
                        onChange={(e) => setUsePastReviews(e.currentTarget.checked)}
                        disabled={isSubmitting}
                    />

                    <Select
                        label="クリーニング済みファイルを選択"
                        placeholder="クリーニング済みファイルを選択"
                        data={
                            fileLists.map((file) => ({
                                value: file.id.toString(),
                                label: file.display_name,
                            })) || []
                        }
                        value={selectedReviewId ? selectedReviewId.toString() : null}
                        onChange={(value) =>
                            setSelectedReviewId(value ? Number(value) : null)
                        }
                        required
                        clearable
                        disabled={isSubmitting || fileLists.length === 0}
                    />

                    <Group>
                        <Button
                            type="submit"
                            loading={isSubmitting && !jobStatus}
                            disabled={!selectedReviewId || isSubmitting}
                        >
                            レビュー処理を実行
                        </Button>

                        {jobStatus && (
                            <Button
                                onClick={resetForm}
                                variant="subtle"
                                disabled={isSubmitting}
                            >
                                ステータス表示をクリア
                            </Button>
                        )}
                    </Group>
                </Stack>
            </form>

            {/* Modal for displaying job status */}
            <Modal
                opened={showJobModal}
                onClose={() => setShowJobModal(false)}
                title="ジョブステータス"
                size="lg"
                closeOnClickOutside={false}
                closeOnEscape={false}
            >
                {jobStatus ? (
                    <Card withBorder p="md" radius="md">
                        <Stack gap="md">
                            <Group>
                                <Text fw={500}>ジョブID:</Text>
                                <Text>{jobStatus.job_id}</Text>
                            </Group>

                            <Group>
                                <Text fw={500}>ステータス:</Text>
                                <Text c={getStatusColor(jobStatus.status)}>
                                    {getStatusText(jobStatus.status)}
                                </Text>
                            </Group>

                            <Progress
                                value={Math.round(
                                    jobStatus.progress ||
                                        jobStatus.status === "processing"
                                        ? 50
                                        : jobStatus.status === "completed"
                                        ? 100
                                        : jobStatus.status === "pending"
                                        ? 25
                                        : 0
                                )}
                                size="md"
                                radius="xl"
                                striped={jobStatus.status === "processing"}
                                animated={jobStatus.status === "processing"}
                                color={getStatusColor(jobStatus.status)}
                            />

                            <Group>
                                <Text fw={500}>更新日時:</Text>
                                <Text>
                                    {new Date(jobStatus.updated_at).toLocaleString()}
                                </Text>
                            </Group>

                            {jobStatus.final_review_id !== undefined && (
                                <Group>
                                    <Text fw={500}>最終レビューID:</Text>
                                    <Text>{jobStatus.final_review_id}</Text>
                                </Group>
                            )}

                            {jobStatus.error && (
                                <Alert color="red" title="エラー">
                                    {jobStatus.error}
                                </Alert>
                            )}

                            {jobStatus.status === "completed" && (
                                <Alert color="green" title="処理完了">
                                    レビューの処理が正常に完了しました。
                                </Alert>
                            )}

                            <Group mt="md" justify="center">
                                {jobStatus.status === "completed" &&
                                    jobStatus.final_review_id && (
                                        <Anchor
                                            href={`/reviews/${jobStatus.final_review_id}`}
                                        >
                                            <Button color="green">結果を表示</Button>
                                        </Anchor>
                                    )}

                                <Button
                                    onClick={handleCancelProcess}
                                    variant="outline"
                                    disabled={isCancelButtonDisabled()}
                                    color="red"
                                >
                                    プロセスをキャンセル
                                </Button>
                            </Group>
                        </Stack>
                    </Card>
                ) : (
                    <Card withBorder p="md" radius="md">
                        <LoadingOverlay visible={true} />
                    </Card>
                )}
            </Modal>
        </>
    );
};

export default ProcessReviewsComponent;
