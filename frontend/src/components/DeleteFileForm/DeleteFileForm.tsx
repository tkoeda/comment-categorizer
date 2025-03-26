import {
    ActionIcon,
    Anchor,
    Box,
    Button,
    Group,
    Loader,
    Modal,
    Select,
    Stack,
    Table,
    Text,
    Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconDownload, IconTrash } from "@tabler/icons-react";
import React, { useEffect, useState } from "react";
import api from "../../api/api";
import { Industry, ReviewItem } from "../../types/types";
import { deleteFile, loadFileLists } from "../../utils/utils";

interface DeleteFileFormProps {
    industries: Industry[];
    onSuccess: () => void;
    refreshFlag: boolean;
}

const DeleteFileForm: React.FC<DeleteFileFormProps> = ({
    industries,
    onSuccess,
    refreshFlag,
}) => {
    const [industryId, setIndustryId] = useState<number | null>(null);
    const [fileLists, setFileLists] = useState<ReviewItem[] | null>(null);
    const [deleteModalOpen, setDeleteModalOpen] = useState<boolean>(false);
    const [fileToDelete, setFileToDelete] = useState<ReviewItem | null>(null);
    const [isDeleting, setIsDeleting] = useState<boolean>(false);

    // Fetch reviews whenever industry or refreshFlag changes
    useEffect(() => {
        const fetchFileLists = async () => {
            if (industryId) {
                try {
                    // loadFileLists returns an array of ReviewItem
                    const data = await loadFileLists(industryId);
                    setFileLists(data);
                } catch (error) {
                    console.error("ファイルリスト読み込みエラー:", error);
                }
            } else {
                // If no industry selected, clear the list
                setFileLists(null);
            }
        };
        fetchFileLists();
    }, [industryId, refreshFlag]);

    // Open confirmation modal
    const openDeleteModal = (file: ReviewItem) => {
        setFileToDelete(file);
        setDeleteModalOpen(true);
    };

    // Perform deletion
    const handleDelete = async () => {
        if (!fileToDelete) return;

        setIsDeleting(true);
        setDeleteModalOpen(false);

        try {
            const data = await deleteFile(fileToDelete.id);
            onSuccess(); // trigger parent refresh if needed
            notifications.show({
                title: "成功",
                message: data.message,
                color: "green",
            });
        } catch (error: any) {
            notifications.show({
                title: "エラー",
                message: error.response?.data?.detail || error.message,
                color: "red",
            });
        } finally {
            setIsDeleting(false);
        }
    };

    // Handle file download
    const handleDownload = async (reviewId: number, displayName: string) => {
        try {
            const notificationId = notifications.show({
                title: "ダウンロード中",
                message: "ファイルを準備しています...",
                loading: true,
                autoClose: false,
            });

            const response = await api.get(`/reviews/download/${reviewId}`, {
                responseType: "blob",
            });

            const blob = new Blob([response.data], {
                type: response.headers["content-type"],
            });
            const url = window.URL.createObjectURL(blob);

            notifications.update({
                id: notificationId,
                title: "成功",
                message: (
                    <>
                        <Text>ファイルが準備できました</Text>
                        <Anchor href={url} download={displayName} mt="xs">
                            {displayName} をダウンロード
                        </Anchor>
                    </>
                ),
                color: "green",
                icon: <IconDownload />,
                autoClose: false,
                loading: false,
            });
        } catch (error) {
            console.error("Download error:", error);
            notifications.show({
                title: "エラー",
                message: "ファイルのダウンロードに失敗しました",
                color: "red",
            });
        }
    };

    // Optionally filter out only final reviews or cleaned
    const finalReviews =
        fileLists?.filter(
            (file) => file.stage === "final" || file.stage === "cleaned"
        ) || [];

    return (
        <Box>
            <Title order={2} mb="md">
                カテゴリ別レビューの表示
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
                />

                <Box mt="md">
                    <Title order={4} mb="sm">
                        最終レビューファイル:
                    </Title>
                    {finalReviews.length > 0 ? (
                        <Table verticalSpacing="md">
                            <thead>
                                <tr>
                                    <th>Review Name</th>
                                    <th>Stage</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {finalReviews.map((review) => (
                                    <tr key={review.id}>
                                        <td>
                                            <Anchor
                                                onClick={() =>
                                                    handleDownload(
                                                        review.id,
                                                        review.display_name ??
                                                            "untitled"
                                                    )
                                                }
                                                style={{ cursor: "pointer" }}
                                            >
                                                {review.display_name || "(No Name)"}
                                            </Anchor>
                                        </td>
                                        <td>{review.stage}</td>
                                        <td>
                                            <ActionIcon
                                                color="red"
                                                onClick={() =>
                                                    openDeleteModal(review)
                                                }
                                            >
                                                <IconTrash size={18} />
                                            </ActionIcon>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </Table>
                    ) : (
                        <Text>利用可能なファイルがありません。</Text>
                    )}
                </Box>
            </Stack>

            <Modal
                opened={deleteModalOpen}
                onClose={() => setDeleteModalOpen(false)}
                title="Confirm Deletion"
            >
                <Text mb="md">
                    ファイル「{fileToDelete?.display_name}
                    」を削除してもよろしいですか？
                </Text>
                <Text mb="md" fw={700} c="red">
                    これにより、処理チェーン内のすべての親ファイルも削除されます。
                </Text>
                <Text mb="md">This action cannot be undone.</Text>
                <Group justify="right">
                    <Button
                        variant="outline"
                        onClick={() => setDeleteModalOpen(false)}
                    >
                        キャンセル
                    </Button>
                    <Button color="red" onClick={handleDelete} disabled={isDeleting}>
                        {isDeleting ? <Loader size={18} /> : "削除"}
                    </Button>
                </Group>
            </Modal>
        </Box>
    );
};

export default DeleteFileForm;
