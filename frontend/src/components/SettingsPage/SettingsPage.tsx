import {
    Button,
    Container,
    Group,
    Modal,
    Paper,
    Space,
    Text,
    TextInput,
    Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconCheck, IconTrash, IconX } from "@tabler/icons-react";
import React, { useState } from "react";
import api from "../../api/api";
import { useAuth } from "../../context/AuthContext";
function SettingsPage() {
    const [apiKey, setApiKey] = useState<string>("");
    const [deleteModalOpen, setDeleteModalOpen] = useState<boolean>(false);
    const { logout } = useAuth();
    const handleUpdateApiKey = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            const response = await api.put("users/me/openai-api-key", {
                api_key: apiKey,
            });
            const data = response.data;
            if (response.status === 200) {
                notifications.show({
                    title: "Success",
                    message: data.message,
                    color: "green",
                    icon: <IconCheck size={16} />,
                });
            } else {
                notifications.show({
                    title: "エラー",
                    message: data.detail || "Failed to update API key.",
                    color: "red",
                    icon: <IconX size={16} />,
                });
            }
        } catch (error: any) {
            console.log(error);
            notifications.show({
                title: "エラー",
                message: error.response.data.detail || "Failed to update API key.",
                color: "red",
                icon: <IconX size={16} />,
            });
        } finally {
            setApiKey("");
        }
    };

    // Remove the OpenAI API key
    const handleDeleteApiKey = async () => {
        try {
            const response = await api.delete("users/me/openai-api-key");
            if (response.status === 200) {
                notifications.show({
                    title: "Success",
                    message: "API key removed successfully.",
                    color: "green",
                    icon: <IconCheck size={16} />,
                });
            }
        } catch (error: any) {
            notifications.show({
                title: "エラー",
                message:
                    error.response.data.detail || "予期しないエラーが発生しました。",
                color: "red",
                icon: <IconX size={16} />,
            });
        }
    };

    // Delete the current user's account
    const handleDeleteAccount = async () => {
        try {
            const response = await api.delete("users/me");
            if (response.status === 204) {
                notifications.show({
                    title: "Success",
                    message: "Account deleted successfully.",
                    color: "green",
                    icon: <IconCheck size={16} />,
                });
                setDeleteModalOpen(false);
                logout();
            }
        } catch (error: any) {
            notifications.show({
                title: "エラー",
                message:
                    error.response?.data?.detail ||
                    "予期しないエラーが発生しました。",
                color: "red",
                icon: <IconX size={16} />,
            });
            setDeleteModalOpen(false);
        }
    };

    return (
        <Container size="sm" py="md">
            <Title order={1}>Account Settings</Title>

            <Paper shadow="xs" p="md" mt="md">
                <Title order={2}>Update OpenAI API Key</Title>
                <form onSubmit={handleUpdateApiKey}>
                    <TextInput
                        placeholder="Enter your new API key"
                        label="API Key"
                        value={apiKey}
                        onChange={(e) => setApiKey(e.currentTarget.value)}
                        required
                    />
                    <Space h="sm" />
                    <Group>
                        <Button type="submit">Update API Key</Button>
                        <Button variant="outline" onClick={handleDeleteApiKey}>
                            Remove API Key
                        </Button>
                    </Group>
                </form>
            </Paper>

            <Paper shadow="xs" p="md" mt="md">
                <Title order={2}>Delete Account</Title>
                <Button
                    color="red"
                    leftSection={<IconTrash size={16} />}
                    onClick={() => setDeleteModalOpen(true)}
                >
                    Delete My Account
                </Button>
            </Paper>
            <Modal
                opened={deleteModalOpen}
                onClose={() => setDeleteModalOpen(false)}
                title="Delete Account"
                centered
            >
                <Text>
                    Are you sure you want to delete your account? This action cannot
                    be undone.
                </Text>
                <Space h="md" />
                <Group justify="right">
                    <Button
                        variant="outline"
                        onClick={() => setDeleteModalOpen(false)}
                    >
                        Cancel
                    </Button>
                    <Button color="red" onClick={handleDeleteAccount}>
                        Delete Account
                    </Button>
                </Group>
            </Modal>
        </Container>
    );
}

export default SettingsPage;
