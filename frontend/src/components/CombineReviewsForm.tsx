import React, { useState, useEffect } from "react";
import api from "../api/api"
import { loadIndustries } from "../utils";

const CombineReviewsForm: React.FC = () => {
    const [industry, setIndustry] = useState<string>("");
    const [industries, setIndustries] = useState<string[]>([]);
    const [type, setType] = useState<string>("");
    const [files, setFiles] = useState<FileList | null>(null);
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

    const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        if (isSubmitting) return; 
        setIsSubmitting(true);
        if (!files) return;
        const formData = new FormData();
        formData.append("industry", industry);
        formData.append("type", type);
        Array.from(files).forEach((file) => {
            formData.append("files", file);
        });
        try {
            const response = await api.post("/combine_reviews", formData, {
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
            <h2>Step 1: Combine Reviews (Optional)</h2>
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
                        Select type
                    </option>
                    <option value="new">New</option>
                    <option value="past">Past</option>
                </select>
            </label>
            <br />
            <label>
                Select Excel Files (Raw Reviews):
                <input
                    type="file"
                    multiple
                    accept=".xlsx"
                    onChange={(e) => setFiles(e.target.files)}
                    required
                />
            </label>
            <br />
            <button type="submit">Combine Reviews</button>
            {message && <p>{message}</p>}
        </form>
    );
};

export default CombineReviewsForm;
