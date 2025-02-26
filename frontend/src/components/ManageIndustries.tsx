import React, { useState, useEffect } from "react";
import { loadIndustries, addIndustry, deleteIndustry } from "../utils";

const ManageIndustries: React.FC = () => {
    const [industries, setIndustries] = useState<Record<string, string[]>>({});
    const [name, setName] = useState<string>("");
    const [categoriesInput, setCategoriesInput] = useState<string>("");
    const [message, setMessage] = useState<string>("");

    const fetchIndustries = async () => {
        try {
            const data = await loadIndustries();
            setIndustries(data);
        } catch (error) {
            console.error("Error fetching industries:", error);
        }
    };

    useEffect(() => {
        fetchIndustries();
    }, []);

    const handleAddIndustry = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        const categories = categoriesInput
            .split(",")
            .map((cat) => cat.trim())
            .filter((cat) => cat !== "");
        try {
            const response = await addIndustry(name, categories);
            setMessage(response.message);
            setName("");
            setCategoriesInput("");
            fetchIndustries();
        } catch (error: any) {
            setMessage(error.response?.data?.detail || error.message);
        }
    };

    const handleDeleteIndustry = async (industryName: string) => {
        try {
            const response = await deleteIndustry(industryName);
            setMessage(response.message);
            fetchIndustries();
        } catch (error: any) {
            setMessage(error.response?.data?.detail || error.message);
        }
    };

    return (
        <div>
            <h2>Manage Industries</h2>
            <form onSubmit={handleAddIndustry}>
                <label>
                    Industry Name:
                    <input
                        type="text"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        required
                    />
                </label>
                <br />
                <label>
                    Categories (comma separated):
                    <input
                        type="text"
                        value={categoriesInput}
                        onChange={(e) => setCategoriesInput(e.target.value)}
                        required
                    />
                </label>
                <br />
                <button type="submit">Add Industry</button>
            </form>
            {message && <p>{message}</p>}
            <h3>Current Industries</h3>
            <ul>
                {Object.keys(industries).map((ind) => (
                    <li key={ind}>
                        {ind}:{" "}
                        {Array.isArray(industries[ind])
                            ? industries[ind].join(", ")
                            : String(industries[ind])}
                        <button onClick={() => handleDeleteIndustry(ind)}>
                            Delete
                        </button>
                    </li>
                ))}
            </ul>
        </div>
    );
};

export default ManageIndustries;
