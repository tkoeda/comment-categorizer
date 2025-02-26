import api from "./api/api";

// Submit a form with FormData to the specified endpoint.
export const submitForm = async (endpoint: string, formData: FormData) => {
    const response = await api.request({
        url: endpoint,
        method: "POST",
        data: formData,
        headers: { "Content-Type": "multipart/form-data" },
    });
    return response.data;
};

// Load file lists for a given industry and type.
export const loadFileLists = async (industry: string, type: string) => {
    const response = await api.get("/list_files/", {
        params: { industry, type },
    });
    return response.data;
};

// Load industries.
export const loadIndustries = async () => {
    const response = await api.get("/industries/");
    return response.data;
};

// Delete a file by sending a DELETE request with FormData.
export interface DeleteFileParams {
    folder: string;
    filename: string;
}

export const deleteFile = async ({
    folder,
    filename,
}: DeleteFileParams): Promise<any> => {
    const formData = new FormData();
    formData.append("folder", folder);
    formData.append("filename", filename);
    const response = await api.delete("/delete_file", { data: formData });
    return response.data;
};

// Add an industry.
export const addIndustry = async (name: string, categories: string[]) => {
    const response = await api.post("/industries/", { name, categories });
    return response.data;
};

// Delete an industry.
export const deleteIndustry = async (name: string) => {
    const response = await api.delete(
        `/industries/${encodeURIComponent(name)}`
    );
    return response.data;
};
