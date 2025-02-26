import React, { useState, useEffect } from "react";
import api from "../api/api";
import { loadIndustries, loadFileLists } from "../utils";

interface FileListResponse {
    combined_new: string[];
    combined_past: string[];
}

const CleanReviewsForm: React.FC = () => {
    const [industry, setIndustry] = useState<string>("");
    const [industries, setIndustries] = useState<string[]>([]);
    const [type, setType] = useState<"new" | "past" | undefined>(undefined);
    const [combinedFiles, setCombinedFiles] = useState<string[]>([]);
    const [selectedFile, setSelectedFile] = useState<string>("");
    const [message, setMessage] = useState<string>("");
    const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

    // Load industries on mount.
    useEffect(() => {
        const fetchIndustries = async () => {
            try {
                const data = await loadIndustries();
                setIndustries(Object.keys(data));
            } catch (error) {
                console.error("Error loading industries", error);
            }
        };
        fetchIndustries();
    }, []);

    // Reload file lists whenever industry or type changes.
    useEffect(() => {
        const fetchFileLists = async () => {
            if (industry && type) {
                try {
                    const data: FileListResponse = await loadFileLists(
                        industry,
                        type
                    );
                    const fileKey =
                        `combined_${type}` as keyof FileListResponse;
                    if (fileKey in data) {
                        setCombinedFiles(data[fileKey]);
                    } else {
                        setCombinedFiles([]);
                    }
                } catch (error) {
                    console.error("Error loading file lists", error);
                }
            }
        };
        fetchFileLists();
    }, [industry, type]);

    const handleIndustryChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
        setIndustry(e.target.value);
    };

    const handleTypeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
        const selectedType = e.target.value;
        if (selectedType === "new" || selectedType === "past") {
            setType(selectedType);
        } else {
            setType(undefined);
        }
    };

    const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        if (isSubmitting) return; 
        setIsSubmitting(true);
        const formData = new FormData();
        formData.append("industry", industry);
        if (!type) {
            setMessage("Please select a type.");
            return;
        }
        formData.append("type", type);
        formData.append("selected_file", selectedFile);
        try {
            const response = await api.post("/clean_reviews", formData, {
                headers: { "Content-Type": "multipart/form-data" },
            });
            setMessage(`Success: ${response.data.message}`);
        } catch (error: any) {
            setMessage(
                `Error: ${error.response?.data?.detail || error.message}`
            );
        }
    };

    return (
        <form onSubmit={handleSubmit}>
            <h2>Step 2: Clean Combined Reviews</h2>
            <label>
                Industry:
                <select
                    value={industry}
                    onChange={handleIndustryChange}
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
                <select value={type || ""} onChange={handleTypeChange} required>
                    <option value="" disabled>
                        Select Type
                    </option>
                    <option value="new">New</option>
                    <option value="past">Past</option>
                </select>
            </label>
            <br />
            <label>
                Select Combined File:
                <select
                    value={selectedFile}
                    onChange={(e) => setSelectedFile(e.target.value)}
                    required
                >
                    <option value="" disabled>
                        Select File
                    </option>
                    {combinedFiles.map((file) => (
                        <option key={file} value={file}>
                            {file}
                        </option>
                    ))}
                </select>
            </label>
            <br />
            <button type="submit">Clean Reviews</button>
            {message && <p>{message}</p>}
        </form>
    );
};

export default CleanReviewsForm;
