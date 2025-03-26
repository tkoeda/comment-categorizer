import {
    Alert,
    Button,
    Card,
    Divider,
    Group,
    List,
    Modal,
    Progress,
    Radio,
    Select,
    Stack,
    Text,
    Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconAlertCircle, IconDatabase, IconRefresh } from "@tabler/icons-react";
import React, { useEffect, useState } from "react";
import api from "../../../api/api";
import { apiVersionPath, myBaseUrl } from "../../../constants";
import { Industry, ReviewItem } from "../../../types/types";
import { loadFileLists } from "../../../utils/utils";
interface IndexJobStatus {
    job_id: string;
    status: "pending" | "processing" | "completed" | "failed" | "cancelled";
    created_at: string;
    updated_at: string;
    reviews_included?: number;
    error?: string;
}

interface PastReviewsIndexManagementProps {
    industries: Industry[];
    refreshFlag: boolean;
}

const PastReviewsIndexManagement: React.FC<PastReviewsIndexManagementProps> = ({
    industries,
    refreshFlag,
}) => {
    const [industryId, setIndustryId] = useState<number | null>(null);
    const [fileLists, setFileLists] = useState<ReviewItem[] | null>(null);
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

    // Job status tracking
    const [jobStatus, setJobStatus] = useState<IndexJobStatus | null>(null);
    const [socket, setSocket] = useState<WebSocket | null>(null);
    const pollingTimeoutRef = React.useRef<NodeJS.Timeout | null>(null);
    const [confirmModalOpen, setConfirmModalOpen] = useState(false);

    const isCancelButtonDisabled = () => {
        return !jobStatus || !["pending", "processing"].includes(jobStatus.status);
    };
    // Load file lists and index status when industry changes
    useEffect(() => {
        const fetchData = async () => {
            if (industryId) {
                try {
                    const data: ReviewItem[] = await loadFileLists(
                        industryId,
                        "past",
                        "cleaned"
                    );
                    console.log("Received data:", data);
                    setFileLists(data);

                    await fetchIndexStatus();
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
                setFileLists(null);
                setIndexStatus(null);
            }
        };

        fetchData();
    }, [industryId, refreshFlag]);

    // Log when job status updates (for debugging)
    useEffect(() => {
        if (jobStatus && jobStatus.status === "pending" && !socket) {
            console.log("Initializing WebSocket for job:", jobStatus.job_id);
            connectWebSocket(jobStatus.job_id);
        }
    }, [jobStatus, socket]);
    // Clean up WebSocket on component unmount
    useEffect(() => {
        return () => {
            if (socket) {
                console.log("Closing WebSocket connection");
                socket.close();
                setSocket(null);
            }

            if (pollingTimeoutRef.current) {
                clearTimeout(pollingTimeoutRef.current);
                pollingTimeoutRef.current = null;
            }
        };
    }, []);

    useEffect(() => {
        const fetchActiveJob = async () => {
            try {
                const response = await api.get("/index/active_index_job");
                if (response.data && response.data.job_id) {
                    setJobStatus(response.data);
                    if (["pending", "processing"].includes(response.data.status)) {
                        connectWebSocket(response.data.job_id);
                    }
                } else {
                    setJobStatus(null);
                }
            } catch (error) {
                console.error("Error fetching active job", error);
                setJobStatus(null);
            }
        };

        fetchActiveJob();
    }, []);

    const resetForm = () => {
        setSelectedPastCleanedId(null);
        setJobStatus(null);
        setIndustryId(null);
        setIsProcessing(false);
    };

    const fetchIndexStatus = async () => {
        if (!industryId) return;

        try {
            console.log("Fetching index status for industry:", industryId);
            const indexResponse = await api.get(`/index/status/${industryId}`);
            console.log("Received index status:", indexResponse.data);
            setIndexStatus(indexResponse.data);
        } catch (error) {
            console.error("Error loading index status", error);
            setIndexStatus(null);
        }
    };

    const handleCancelProcess = async () => {
        if (!jobStatus) return;
        try {
            console.log("Canceling index job:", jobStatus.job_id);
            const response = await api.post(
                `/index/cancel_index_job/${jobStatus.job_id}`
            );
            console.log("Cancel response:", response.data);
            notifications.show({
                title: "キャンセル要求",
                message: "プロセスのキャンセルが要求されました。",
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

    // Connect to WebSocket for real-time status updates
    const connectWebSocket = (id: string) => {
        // Ensure protocol matches (ws:// for http, wss:// for https)
        const baseUrl = myBaseUrl;
        const backendUrl = new URL(import.meta.env.VITE_API_URL_LOCAL);

        const wsProtocol = baseUrl.startsWith("https") ? "wss:" : "ws:";
        const wsHost = new URL(baseUrl).host;

        // Construct the WebSocket URL using apiVersionPath
        const wsUrl = `${wsProtocol}//${wsHost}${apiVersionPath}/ws/index_job/${id}`;

        console.log("Connecting to:", wsUrl);
        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            console.log("WebSocket connected");
        };

        ws.onmessage = (event) => {
            console.log("WebSocket message received:", event.data);
            try {
                const data = JSON.parse(event.data);
                setJobStatus(data);

                if (data.status === "completed") {
                    notifications.show({
                        title: "完了",
                        message: "インデックスの更新が正常に完了しました",
                        color: "green",
                    });
                    resetForm();
                } else if (data.status === "failed") {
                    notifications.show({
                        title: "失敗",
                        message: `処理に失敗しました: ${
                            data.error || "不明なエラー"
                        }`,
                        color: "red",
                    });
                    resetForm();
                } else if (data.status === "cancelled") {
                    notifications.show({
                        title: "キャンセル",
                        message: "インデックスの更新がキャンセルされました",
                        color: "orange",
                    });
                    resetForm();
                }
            } catch (error) {
                console.error("Error parsing WebSocket message:", error);
            } finally {
                fetchIndexStatus();
            }
        };

        ws.onerror = (error) => {
            console.error("WebSocket error:", error);
            // Fall back to polling if WebSocket fails
            pollJobStatus(id);
        };

        ws.onclose = () => {
            console.log("WebSocket disconnected");
            setSocket(null);
        };

        setSocket(ws);
    };

    // Fallback method: poll job status
    const pollJobStatus = async (id: string) => {
        if (pollingTimeoutRef.current) {
            clearTimeout(pollingTimeoutRef.current);
            pollingTimeoutRef.current = null;
        }
        if (socket && socket.readyState === WebSocket.OPEN) {
            console.log("Skipping polling");
            return;
        }
        try {
            // Match the backend endpoint
            const response = await api.get(`/index/index_job_status/${id}`);
            setJobStatus(response.data);

            // Continue polling if job is still in progress
            if (
                response.data.status !== "completed" &&
                response.data.status !== "failed"
            ) {
                pollingTimeoutRef.current = setTimeout(
                    () => pollJobStatus(id),
                    2000
                );
            } else {
                fetchIndexStatus(); // Refresh the index status after completion

                // Show notification based on status
                notifications.show({
                    title: response.data.status === "completed" ? "完了" : "失敗",
                    message:
                        response.data.status === "completed"
                            ? "インデックスの更新が正常に完了しました"
                            : `処理に失敗しました: ${
                                  response.data.error || "不明なエラー"
                              }`,
                    color: response.data.status === "completed" ? "green" : "red",
                });
                resetForm();
            }
        } catch {
            pollingTimeoutRef.current = setTimeout(() => pollJobStatus(id), 5000);
        }
    };

    const handleUpdateIndex = async () => {
        if (isProcessing || !selectedPastCleanedId || !industryId) return;
        if (pollingTimeoutRef.current) {
            clearTimeout(pollingTimeoutRef.current);
            pollingTimeoutRef.current = null;
        }
        setIsProcessing(true);
        setJobStatus(null);

        const payload = {
            industry_id: industryId,
            past_cleaned_id: selectedPastCleanedId,
            mode: uploadMode,
        };

        try {
            const response = await api.post(
                "/index/update_past_reviews_index",
                payload,
                {
                    headers: { "Content-Type": "application/json" },
                }
            );

            console.log("Job started response:", response.data);

            // Set initial status
            setJobStatus({
                job_id: response.data.job_id,
                status: response.data.status,
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
            });

            // Connect to WebSocket for real-time updates
            try {
                console.log("Attempting WebSocket connection");
                connectWebSocket(response.data.job_id);
            } catch (error) {
                console.log(
                    "WebSocket connection failed, falling back to polling:",
                    error
                );
                pollJobStatus(response.data.job_id);
            }
            notifications.show({
                title: "処理開始",
                message: "インデックス更新ジョブが開始されました",
                color: "blue",
            });
        } catch (error: any) {
            console.error("Error starting index job:", error);
            resetForm();
            notifications.show({
                title: "Error",
                message: error.response?.data?.detail || error.message,
                color: "red",
                icon: <IconAlertCircle />,
            });
        }
    };

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
            default:
                return "gray";
        }
    };

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

    const onSubmit = () => {
        if (isProcessing) return;
        if (uploadMode === "replace") {
            setConfirmModalOpen(true);
        } else {
            handleUpdateIndex();
        }
    };

    return (
        <>
            <Modal
                opened={confirmModalOpen}
                onClose={() => setConfirmModalOpen(false)}
                title="確認: インデックスの再作成"
                centered
            >
                <Text>
                    既存のインデックスが削除され、新しいインデックスが作成されます。本当によろしいですか？
                </Text>
                <Group justify="apart" mt="md">
                    <Button
                        variant="outline"
                        onClick={() => setConfirmModalOpen(false)}
                    >
                        キャンセル
                    </Button>
                    <Button
                        onClick={() => {
                            setConfirmModalOpen(false);
                            handleUpdateIndex();
                        }}
                        color="orange"
                    >
                        確認する
                    </Button>
                </Group>
            </Modal>
            <Title order={2} mb="md">
                過去のレビューインデックス管理
            </Title>

            <Stack gap="lg">
                <Select
                    label="業界"
                    placeholder=""
                    data={industries.map((ind) => ({
                        value: ind.id.toString(),
                        label: ind.name,
                    }))}
                    value={industryId ? industryId.toString() : null}
                    onChange={(value) => {
                        setIndustryId(value ? Number(value) : null);
                        setSelectedPastCleanedId(null);
                    }}
                    required
                    searchable
                    clearable
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
                            fileLists?.map((file) => ({
                                value: file.id.toString(),
                                label: file.display_name,
                            })) || []
                        }
                        value={
                            selectedPastCleanedId
                                ? selectedPastCleanedId.toString()
                                : null
                        }
                        onChange={(value) =>
                            setSelectedPastCleanedId(value ? Number(value) : null)
                        }
                        disabled={
                            !fileLists?.length ||
                            isProcessing ||
                            jobStatus?.status === "processing" ||
                            jobStatus?.status === "pending"
                        }
                        required
                        clearable
                    />

                    <Radio.Group
                        label="インデックス更新モード"
                        value={uploadMode}
                        onChange={(value) =>
                            setUploadMode(value as "add" | "replace")
                        }
                    >
                        <Group mt="xs">
                            <Radio
                                value="add"
                                label="既存のインデックスに追加"
                                disabled={isProcessing}
                            />
                            <Radio
                                value="replace"
                                label="インデックスの再作成"
                                disabled={isProcessing}
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

                    <Group>
                        <Button
                            onClick={onSubmit}
                            leftSection={
                                uploadMode === "add" ? (
                                    <IconDatabase size={14} />
                                ) : (
                                    <IconRefresh size={14} />
                                )
                            }
                            loading={isProcessing && !jobStatus}
                            disabled={!selectedPastCleanedId || isProcessing}
                            color={uploadMode === "replace" ? "orange" : "blue"}
                        >
                            {uploadMode === "add"
                                ? "インデックスに追加"
                                : "インデックスを置き換え"}
                        </Button>

                        {jobStatus && (
                            <Button
                                onClick={resetForm}
                                variant="subtle"
                                disabled={isProcessing}
                            >
                                ステータス表示をクリア
                            </Button>
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

                {/* Job Status Section */}
                {jobStatus && (
                    <Card withBorder p="md" radius="md">
                        <Title order={3} size="h4" mb="md">
                            ジョブステータス
                        </Title>

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

                            {jobStatus.status === "processing" && (
                                <Progress
                                    animated
                                    value={jobStatus.reviews_included ? 50 : 25}
                                    color={getStatusColor(jobStatus.status)}
                                />
                            )}

                            <Group>
                                <Text fw={500}>更新日時:</Text>
                                <Text>
                                    {new Date(jobStatus.updated_at).toLocaleString()}
                                </Text>
                            </Group>

                            {jobStatus.reviews_included !== undefined && (
                                <Group>
                                    <Text fw={500}>処理済みレビュー数:</Text>
                                    <Text>{jobStatus.reviews_included}</Text>
                                </Group>
                            )}

                            {jobStatus.error && (
                                <Alert color="red" title="エラー">
                                    {jobStatus.error}
                                </Alert>
                            )}

                            {jobStatus.status === "completed" && (
                                <Alert color="green" title="処理完了">
                                    インデックスの更新が正常に完了しました。
                                </Alert>
                            )}
                        </Stack>
                    </Card>
                )}
            </Stack>
        </>
    );
};

export default PastReviewsIndexManagement;
