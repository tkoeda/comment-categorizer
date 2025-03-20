import {
    ActionIcon,
    Box,
    Button,
    Group,
    Modal,
    Paper,
    Stack,
    Table,
    Text,
    TextInput,
    Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconCheck, IconTrash, IconX } from "@tabler/icons-react";
import React, { useState } from "react";
import { Industry } from "../types.ts";
import { addIndustry, deleteIndustry } from "../utils";

interface ManageIndustriesProps {
    industries: Industry[];
    fetchIndustries: () => void;
}

const ManageIndustries: React.FC<ManageIndustriesProps> = ({ industries, fetchIndustries }) => {
    const [industryName, setIndustryName] = useState<string>("");
    const [categoriesInput, setCategoriesInput] = useState<string>("");
    const [industryToDelete, setIndustryToDelete] = useState<number | null>(null);
    const [deleteModalOpen, setDeleteModalOpen] = useState<boolean>(false);
   
    const handleAddIndustry = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        const categories = categoriesInput
            .split(",")
            .map((cat) => cat.trim())
            .filter((cat) => cat !== "");

        try {
            const response = await addIndustry(industryName, categories);
            notifications.show({
                title: "成功",
                message: response.message,
                color: "teal",
                icon: <IconCheck size={20} />,
            });
            setIndustryName("");
            setCategoriesInput("");
            fetchIndustries();
        } catch (error: any) {
            notifications.show({
                title: "エラー",
                message: error.response?.data?.detail || error.message,
                color: "red",
                icon: <IconX size={20} />,
            });
        }
    };

    const openDeleteModal = (industry_id: number) => {
        setIndustryToDelete(industry_id);
        setDeleteModalOpen(true);
    };

    const handleDeleteIndustry = async () => {
        setDeleteModalOpen(false);

        try {
            const response = await deleteIndustry(industryToDelete!);
            notifications.show({
                title: "All good!",
                message: response.message,
                color: "teal",
                icon: <IconCheck size={20} />,
            });
            fetchIndustries();
        } catch (error: any) {
            notifications.show({
                title: "エラーが発生しました！",
                message: error.response?.data?.detail || error.message,
                color: "red",
                icon: <IconX size={20} />,
            });
        }
    };

    return (
        <Box>
            <Title order={2} mb="md">
                業界を管理する
            </Title>
            {/* Inline Notification */}
            <Stack gap="md">
                <Paper p="md" withBorder>
                    <form onSubmit={handleAddIndustry}>
                        <Stack gap="md">
                            <TextInput
                                label="業界名"
                                placeholder="業界名を入力してください"
                                value={industryName}
                                onChange={(e) => setIndustryName(e.target.value)}
                                required
                            />

                            <TextInput
                                label="カテゴリー（カンマ区切り)"
                                placeholder="カテゴリー1, カテゴリー2, カテゴリー3"
                                value={categoriesInput}
                                onChange={(e) => setCategoriesInput(e.target.value)}
                                required
                            />

                            <Group justify="center">
                                <Button
                                    type="submit"
                                    disabled={!categoriesInput || !industryName}
                                >
                                    追加
                                </Button>
                            </Group>
                        </Stack>
                    </form>
                </Paper>

                <Title order={3} mt="md">
                    現在の業界
                </Title>

                {industries.length > 0 ? (
                    <Table verticalSpacing="md">
                        <Table.Thead>
                            <Table.Tr>
                                <Table.Th ta="center">業界</Table.Th>
                                <Table.Th ta="center">カテゴリー</Table.Th>
                                <Table.Th ta="center">アクション</Table.Th>
                            </Table.Tr>
                        </Table.Thead>

                        <Table.Tbody>
                            {industries.map((industry) => (
                                <Table.Tr key={industry.id}>
                                    <Table.Td>{industry.name}</Table.Td>
                                    <Table.Td>
                                        {Array.isArray(industry.categories)
                                            ? industry.categories.join(", ")
                                            : String(industry.categories)}
                                    </Table.Td>
                                    <Table.Td>
                                        <ActionIcon
                                            color="red"
                                            onClick={() =>
                                                openDeleteModal(industry.id)
                                            }
                                        >
                                            <IconTrash size={18} />
                                        </ActionIcon>
                                    </Table.Td>
                                </Table.Tr>
                            ))}
                        </Table.Tbody>
                    </Table>
                ) : (
                    <Text c="dimmed">まだ業界が追加されていません</Text>
                )}
            </Stack>

            <Modal
                opened={deleteModalOpen}
                onClose={() => setDeleteModalOpen(false)}
                title="削除の確認"
                centered
            >
                <Text mb="md">
                    本当に業界 "{industryToDelete}" を削除しますか？
                    この操作は元に戻せません。
                </Text>
                <Group justify="right">
                    <Button
                        variant="outline"
                        onClick={() => setDeleteModalOpen(false)}
                    >
                        キャンセル
                    </Button>
                    <Button color="red" onClick={handleDeleteIndustry}>
                        削除
                    </Button>
                </Group>
            </Modal>
        </Box>
    );
};

export default ManageIndustries;
