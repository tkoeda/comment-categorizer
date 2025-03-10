import api from "./api/api";

export const submitForm = async (endpoint: string, formData: FormData) => {
    const response = await api.request({
        url: endpoint,
        method: "POST",
        data: formData,
        headers: { "Content-Type": "multipart/form-data" },
    });
    return response.data;
};

export const loadFileLists = async (industryId: number, reviewType?: string) => {
    const response = await api.get("/reviews/list/", {
        params: { industry_id: industryId, review_type: reviewType },
    });
    return response.data;
};

export const getIndustries = async () => {
    const response = await api.get("/industries/");
    return response.data;
};

export const deleteFile = async (review_id: number) => {
    const response = await api.delete(`/reviews/${review_id}`);
    return response.data;
};

export const addIndustry = async (name: string, categories: string[]) => {
    const response = await api.post("/industries/", { industry_name: name, categories });
    return response.data;
};

export const deleteIndustry = async (industry_id: number) => {
    const response = await api.delete(
        `/industries/${industry_id}`
    );
    return response.data;
};
