import {
    Alert,
    Badge,
    Box,
    Button,
    Card,
    Group,
    LoadingOverlay,
    Progress,
    Stack,
    Table,
    Text,
    Title,
} from "@mantine/core";
import {
    IconAlertCircle,
    IconCheck,
    IconFileSpreadsheet,
    IconPlayerStop,
    IconRefresh,
    IconX,
} from "@tabler/icons-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../../api/api";

interface WebSocketMessage {
    job_id: number;
    status: string;
    progress: number;
    reviews_processed?: number;
    total_reviews?: number;
    final_review_id?: number;
    error?: string;
    updated_at: string;
}

interface ReviewJobTrackerProps {
    jobId: number;
    onComplete?: (finalReviewId: number) => void;
    onError?: (error: string) => void;
    showNavigateButton?: boolean;
}

/**
 * Component for tracking review job progress and status
 * Supports WebSocket connection for real-time updates
 */
const ReviewJobTracker: React.FC<ReviewJobTrackerProps> = ({
    jobId,
    onComplete,
    onError,
    showNavigateButton = true,
}) => {
    const [job, setJob] = useState<ReviewJob | null>(null);
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    const [wsConnected, setWsConnected] = useState<boolean>(false);
    const wsRef = useRef<WebSocket | null>(null);
    const navigate = useNavigate();

    // Initial job data loading
    useEffect(() => {
        if (!jobId) return;

        const fetchJobStatus = async (): Promise<void> => {
            try {
                setLoading(true);
                const response = await api.get(`/review_job/${jobId}`);
                setJob(response.data);
                setError(null);

                // Don't connect to WebSocket if job is already in a final state
                if (
                    ["completed", "failed", "cancelled"].includes(
                        response.data.status
                    )
                ) {
                    if (
                        response.data.status === "completed" &&
                        onComplete &&
                        response.data.final_review_id
                    ) {
                        onComplete(response.data.final_review_id);
                    } else if (
                        response.data.status === "failed" &&
                        onError &&
                        response.data.error
                    ) {
                        onError(response.data.error);
                    }
                } else {
                    connectWebSocket();
                }
            } catch (err: any) {
                console.error("Error fetching job status:", err);
                setError(
                    err.response?.data?.detail || "ジョブの取得に失敗しました。"
                );
            } finally {
                setLoading(false);
            }
        };

        fetchJobStatus();

        // Cleanup function
        return () => {
            if (wsRef.current) {
                wsRef.current.close();
            }
        };
    }, [jobId, onComplete, onError]);

    // Connect to WebSocket for real-time updates
    const connectWebSocket = (): void => {
        const protocol = window.location.protocol === "https:" ? "wss" : "ws";
        const wsUrl = `${protocol}://${window.location.host}/api/review_job/${jobId}`;

        if (wsRef.current) {
            wsRef.current.close();
        }

        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
            console.log(`WebSocket connected for job ${jobId}`);
            setWsConnected(true);
        };

        ws.onmessage = (event: MessageEvent) => {
            const data = JSON.parse(event.data) as WebSocketMessage;
            console.log("WebSocket message:", data);

            if (data.error) {
                setError(data.error);
                return;
            }

            setJob(data as unknown as ReviewJob);

            // Handle job completion or failure
            if (data.status === "completed" && onComplete && data.final_review_id) {
                onComplete(data.final_review_id);
            } else if (data.status === "failed" && onError && data.error) {
                onError(data.error);
            }
        };

        ws.onclose = () => {
            console.log(`WebSocket closed for job ${jobId}`);
            setWsConnected(false);
        };

        ws.onerror = (error: Event) => {
            console.error("WebSocket error:", error);
            setWsConnected(false);
            setError("WebSocket接続エラー");
        };
    };

    // Handle cancel job button
    const handleCancel = async (): Promise<void> => {
        try {
            await api.post(`/cancel_review_job/${jobId}`);
            // WebSocket will update the status
        } catch (err: any) {
            setError(
                err.response?.data?.detail || "ジョブのキャンセルに失敗しました。"
            );
        }
    };

    // Handle navigate to result
    const handleNavigateToResult = (): void => {
        if (job?.final_review_id) {
            navigate(`/reviews/${job.final_review_id}`);
        }
    };

    // Get status badge based on job status
    const getStatusBadge = (status: string): React.ReactNode => {
        switch (status) {
            case "pending":
                return <Badge color="blue">待機中</Badge>;
            case "processing":
                return (
                    <Badge color="indigo" leftSection={<IconRefresh size={14} />}>
                        処理中
                    </Badge>
                );
            case "completed":
                return (
                    <Badge color="green" leftSection={<IconCheck size={14} />}>
                        完了
                    </Badge>
                );
            case "failed":
                return (
                    <Badge color="red" leftSection={<IconX size={14} />}>
                        失敗
                    </Badge>
                );
            case "cancelled":
                return (
                    <Badge color="gray" leftSection={<IconPlayerStop size={14} />}>
                        キャンセル
                    </Badge>
                );
            default:
                return <Badge>{status}</Badge>;
        }
    };

    // Progress color based on status
    const getProgressColor = (status: string): string => {
        switch (status) {
            case "completed":
                return "green";
            case "failed":
                return "red";
            case "cancelled":
                return "gray";
            default:
                return "blue";
        }
    };

    if (loading) {
        return (
            <Card shadow="sm" p="lg" radius="md" withBorder>
                <LoadingOverlay visible={true} />
                <Box style={{ height: 200 }} />
            </Card>
        );
    }

    if (error) {
        return (
            <Card shadow="sm" p="lg" radius="md" withBorder>
                <Alert
                    icon={<IconAlertCircle size={16} />}
                    title="エラー"
                    color="red"
                >
                    {error}
                </Alert>
            </Card>
        );
    }

    if (!job) {
        return (
            <Card shadow="sm" p="lg" radius="md" withBorder>
                <Alert
                    icon={<IconAlertCircle size={16} />}
                    title="ジョブが見つかりません"
                    color="yellow"
                >
                    指定されたジョブが見つかりませんでした。
                </Alert>
            </Card>
        );
    }

    return (
        <Card shadow="sm" p="lg" radius="md" withBorder>
            <Card.Section withBorder inheritPadding py="xs">
                <Group justify="apart">
                    <Title order={4}>レビューの処理ステータス</Title>
                    {getStatusBadge(job.status)}
                </Group>
            </Card.Section>

            <Stack gap="md" mt="md">
                <Table>
                    <tbody>
                        {job.reviews_processed !== null &&
                            job.total_reviews !== null && (
                                <tr>
                                    <td>
                                        <Text fw={500}>進捗</Text>
                                    </td>
                                    <td>
                                        {job.reviews_processed} / {job.total_reviews}{" "}
                                        レビュー処理済み
                                    </td>
                                </tr>
                            )}
                        <tr>
                            <td>
                                <Text fw={500}>作成日時</Text>
                            </td>
                            <td>{new Date(job.created_at).toLocaleString()}</td>
                        </tr>
                        <tr>
                            <td>
                                <Text fw={500}>更新日時</Text>
                            </td>
                            <td>{new Date(job.updated_at).toLocaleString()}</td>
                        </tr>
                        {job.error && (
                            <tr>
                                <td>
                                    <Text fw={500}>エラー</Text>
                                </td>
                                <td>
                                    <Text c="red">{job.error}</Text>
                                </td>
                            </tr>
                        )}
                    </tbody>
                </Table>

                <Progress
                    value={Math.round(job.progress || 0)}
                    color={getProgressColor(job.status)}
                    size="md"
                    radius="xl"
                    striped={job.status === "processing"}
                    animated={job.status === "processing"}
                />

                <Group>
                    {["pending", "processing"].includes(job.status) && (
                        <Button
                            color="red"
                            onClick={handleCancel}
                            leftSection={<IconPlayerStop size={16} />}
                        >
                            処理をキャンセル
                        </Button>
                    )}

                    {job.status === "completed" &&
                        job.final_review_id &&
                        showNavigateButton && (
                            <Button
                                color="blue"
                                onClick={handleNavigateToResult}
                                leftSection={<IconFileSpreadsheet size={16} />}
                            >
                                結果を表示
                            </Button>
                        )}
                </Group>

                {!wsConnected && ["pending", "processing"].includes(job.status) && (
                    <Alert
                        icon={<IconAlertCircle size={16} />}
                        title="リアルタイム更新の接続が切断されました"
                        color="yellow"
                    >
                        更新を受信するために再読み込みしてください。
                    </Alert>
                )}
            </Stack>
        </Card>
    );
};

export default ReviewJobTracker;
