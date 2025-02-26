import React, { useState, useEffect } from "react";
import api from "../api/api";
import { loadIndustries, loadFileLists } from "../utils";

interface FileListResponse {
    combined_new: string[];
    cleaned_new: string[];
}

const ProcessReviewsForm: React.FC = () => {
    const [industry, setIndustry] = useState<string>("");
    const [industries, setIndustries] = useState<string[]>([]);
    const [combinedFiles, setCombinedFiles] = useState<string[]>([]);
    const [cleanedFiles, setCleanedFiles] = useState<string[]>([]);
    const [selectedCombinedFile, setSelectedCombinedFile] =
        useState<string>("");
    const [selectedCleanedFile, setSelectedCleanedFile] = useState<string>("");
    const [message, setMessage] = useState<string>("");
    const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

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

    const handleIndustryChange = async (
        e: React.ChangeEvent<HTMLSelectElement>
    ) => {
        const selectedIndustry = e.target.value;
        setIndustry(selectedIndustry);
        try {
            const data: FileListResponse = await loadFileLists(
                selectedIndustry,
                "new"
            );
            setCombinedFiles(data.combined_new);
            setCleanedFiles(data.cleaned_new);
        } catch (error) {
            console.error("Error loading file lists", error);
        }
    };

    const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        if (isSubmitting) return; 
        setIsSubmitting(true);
        const formData = new FormData();
        formData.append("industry", industry);
        formData.append("combined_file", selectedCombinedFile);
        formData.append("cleaned_file", selectedCleanedFile);
        try {
            const response = await api.post(
                "/process_reviews_saved",
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
            setMessage(
                `Success! Download your file <a href="${url}" download="categorized_reviews.xlsx">here</a>.`
            );
        } catch (error: any) {
            setMessage(
                `Error: ${error.response?.data?.detail || error.message}`
            );
        }
    };

    return (
        <form onSubmit={handleSubmit}>
            <h2>Step 3: Process Saved Reviews</h2>
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
                Select Combined File:
                <select
                    value={selectedCombinedFile}
                    onChange={(e) => setSelectedCombinedFile(e.target.value)}
                    required
                >
                    <option value="" disabled>
                        Select Combined File
                    </option>
                    {combinedFiles.map((file) => (
                        <option key={file} value={file}>
                            {file}
                        </option>
                    ))}
                </select>
            </label>
            <br />
            <label>
                Select Cleaned File:
                <select
                    value={selectedCleanedFile}
                    onChange={(e) => setSelectedCleanedFile(e.target.value)}
                    required
                >
                    <option value="" disabled>
                        Select Cleaned File
                    </option>
                    {cleanedFiles.map((file) => (
                        <option key={file} value={file}>
                            {file}
                        </option>
                    ))}
                </select>
            </label>
            <br />
            <button type="submit">Process Reviews</button>
            {message && <p dangerouslySetInnerHTML={{ __html: message }} />}
        </form>
    );
};

export default ProcessReviewsForm;
