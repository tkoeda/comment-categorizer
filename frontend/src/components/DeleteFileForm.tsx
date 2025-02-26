// src/components/DeleteFileForm.tsx
import React, { useState, useEffect } from "react";
import { loadIndustries, loadFileLists, deleteFile } from "../utils";

interface FileLists {
    [key: string]: string[];
}

const DeleteFileForm: React.FC = () => {
    const [industry, setIndustry] = useState<string>("");
    const [type, setType] = useState<string>("new"); // default to "new"
    const [industries, setIndustries] = useState<string[]>([]);
    const [folder, setFolder] = useState<string>("");
    const [fileLists, setFileLists] = useState<FileLists>({});
    const [selectedFile, setSelectedFile] = useState<string>("");
    const [message, setMessage] = useState<string>("");

    // Load available industries on component mount.
    useEffect(() => {
        const fetchIndustries = async () => {
            try {
                const data = await loadIndustries();
                setIndustries(Object.keys(data));
            } catch (error) {
                console.error("Error loading industries:", error);
            }
        };
        fetchIndustries();
    }, []);

    // Whenever industry, type, or folder changes, load the file lists.
    useEffect(() => {
        const fetchFileLists = async () => {
            if (industry && type && folder) {
                try {
                    const data = await loadFileLists(industry, type);
                    setFileLists(data);
                } catch (error) {
                    console.error("Error loading file lists:", error);
                }
            }
        };
        fetchFileLists();
    }, [industry, type, folder]);

    // Determine which file list to show based on the folder.
    const getFilesForFolder = (): string[] => {
        let key = "";
        if (folder === "raw") {
            key = "raw_new";
        } else if (folder === "combined") {
            key = "combined_new";
        } else if (folder === "cleaned") {
            key = "cleaned_new";
        } else if (folder === "final") {
            key = "final";
        }
        return fileLists[key] || [];
    };

    const handleDelete = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        if (!folder || !selectedFile) return;
        try {
            const data = await deleteFile({ folder, filename: selectedFile });
            setMessage(`Success: ${data.message}`);
            // Optionally, refresh file list after deletion:
            const updatedData = await loadFileLists(industry, type);
            setFileLists(updatedData);
        } catch (error: any) {
            setMessage(
                `Error: ${error.response?.data?.detail || error.message}`
            );
        }
    };

    return (
        <form onSubmit={handleDelete}>
            <h2>Delete File</h2>
            <label>
                Industry:
                <select
                    value={industry}
                    onChange={(e) => setIndustry(e.target.value)}
                    required
                >
                    <option value="" disabled>
                        Select Industry
                    </option>
                    {industries.map((ind) => (
                        <option key={ind} value={ind}>
                            {ind}
                        </option>
                    ))}
                </select>
            </label>
            <br />
            <label>
                Type:
                <select
                    value={type}
                    onChange={(e) => setType(e.target.value)}
                    required
                >
                    <option value="" disabled>
                        Select Type
                    </option>
                    <option value="new">New</option>
                    <option value="past">Past</option>
                </select>
            </label>
            <br />
            <label>
                Folder:
                <select
                    value={folder}
                    onChange={(e) => setFolder(e.target.value)}
                    required
                >
                    <option value="" disabled>
                        Select Folder
                    </option>
                    <option value="raw">raw</option>
                    <option value="combined">combined</option>
                    <option value="cleaned">cleaned</option>
                    <option value="final">final</option>
                </select>
            </label>
            <br />
            <label>
                File:
                <select
                    value={selectedFile}
                    onChange={(e) => setSelectedFile(e.target.value)}
                    required
                >
                    <option value="" disabled>
                        Select File
                    </option>
                    {getFilesForFolder().map((file) => (
                        <option key={file} value={file}>
                            {file}
                        </option>
                    ))}
                </select>
            </label>
            <br />
            <button type="submit">Delete File</button>
            {message && <p>{message}</p>}
        </form>
    );
};

export default DeleteFileForm;
