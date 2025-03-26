export interface Industry {
    id: number;
    name: string;
    categories: string[];
}

export interface ReviewItem {
    id: number;
    display_name: string;
    file_path: string;
    stage: string;
    review_type: string;
    created_at: string;
    parent_id: number | null;
}

export interface ReviewNode {
    review: ReviewItem;
    children: ReviewNode[];
}
