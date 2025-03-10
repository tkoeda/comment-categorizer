
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
}

export interface ReviewLists {
    new: {
        cleaned: ReviewItem[];
        combined: ReviewItem[];
        [stage: string]: ReviewItem[];
    };
    past: {
        cleaned: ReviewItem[];
        combined: ReviewItem[];
        [stage: string]: ReviewItem[];
    };
    final: ReviewItem[];
}
