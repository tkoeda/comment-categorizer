import json
import os
import time

import numpy as np
import pandas as pd


def calculate_average_time(durations):
    """Return the average of a list of durations or 0 if empty."""
    return sum(durations) / len(durations) if durations else 0


def get_unique_filename(base_path, extension):
    """
    Generate a unique filename by appending a timestamp.
    """
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    return f"{base_path}_{timestamp}{extension}"


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        elif isinstance(obj, (np.floating,)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)


def save_results_to_excel(
    results,
    token_info,
    section_times,
    model,
    embeddings_model=None,
    output_dir="output",
    use_rag=False,
    raw_or_cleaned="raw",
    average_similar_review_length=None,
):
    """
    Save review classification results and token usage details to an Excel file.

    - `model`: Name of the model used (e.g., "pkshatech/GLuCoSE-base-ja-v2").
    - `use_rag`: Boolean indicating whether RAG was used.
    """

    method = "with_rag" if use_rag else "no_rag"

    output_subdir = os.path.join(output_dir, raw_or_cleaned, embeddings_model or "no_embeddings", method)
    os.makedirs(output_subdir, exist_ok=True)

    output_path = get_unique_filename(os.path.join(output_subdir, "results"), ".xlsx")

    all_data = []
    for res in results:
        all_data.append(
            {
                "NO": res.get("NO", "N/A"),
                "Comment": res.get("new_review", ""),
                "Similar Reviews": "\n".join(res.get("similar_reviews", [])),
                "Categories": ", ".join(res.get("categories", ["N/A"])),
            }
        )

    df_reviews = pd.DataFrame(all_data)

    df_tokens = pd.DataFrame(
        [
            {
                "Embeddings Model": embeddings_model if embeddings_model else "N/A",
                "Model": model,
                "average_similar_review_length": average_similar_review_length,
                "average_api_call_duration": token_info.get("avg_api_call_duration", 0),
                "average_faiss_retrieval_duration": token_info.get("avg_faiss_retrieval_duration", 0),
                "Prompt Tokens Used": token_info.get("prompt_tokens", 0),
                "Completion Tokens Used": token_info.get("completion_tokens", 0),
                "Prompt Cost ($)": token_info.get("prompt_cost", 0),
                "Completion Cost ($)": token_info.get("completion_cost", 0),
                "Total Cost ($)": token_info.get("total_cost", 0),
                "Total Reviews Processed": token_info.get("total_reviews", 0),
                "Past Reviews Path": token_info.get("past_reviews_path", "N/A"),
                "New Reviews Path": token_info.get("new_reviews_path", "N/A"),
            }
        ]
    )

    df_times = pd.DataFrame(section_times.items(), columns=["Section", "Duration (seconds)"])

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df_reviews.to_excel(writer, sheet_name="Reviews", index=False)
        df_tokens.to_excel(writer, sheet_name="Token Usage", index=False)
        df_times.to_excel(writer, sheet_name="Processing Times", index=False)

    print(f"Results saved to {output_path}")


def save_results_to_json(
    results,
    token_info,
    section_times,
    model,
    embeddings_model=None,
    output_dir="output",
    use_rag=False,
    raw_or_cleaned="raw",
    average_similar_review_length=None,
):
    """
    Save review classification results and token usage details to a JSON file.

    - `model`: Name of the model used (e.g., "pkshatech/GLuCoSE-base-ja-v2").
    - `use_rag`: Boolean indicating whether RAG was used.
    """

    method = "with_rag" if use_rag else "no_rag"

    output_subdir = os.path.join(output_dir, raw_or_cleaned, embeddings_model or "no_embeddings", method)
    os.makedirs(output_subdir, exist_ok=True)

    output_path = get_unique_filename(os.path.join(output_subdir, "results"), ".json")

    results_with_tokens = {
        "embeddings_model": embeddings_model if embeddings_model else "N/A",
        "model": model,
        "average_similar_review_length": average_similar_review_length,
        "past_reviews_path": token_info.get("past_reviews_path", "N/A"),
        "new_reviews_path": token_info.get("new_reviews_path", "N/A"),
        "total_reviews": token_info.get("total_reviews", 0),
        "token_usage": {
            "prompt_tokens": token_info.get("prompt_tokens", 0),
            "completion_tokens": token_info.get("completion_tokens", 0),
            "prompt_cost": token_info.get("prompt_cost", 0),
            "completion_cost": token_info.get("completion_cost", 0),
            "total_cost": token_info.get("total_cost", 0),
        },
        "processing_times": section_times,
        "reviews": results,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results_with_tokens, f, ensure_ascii=False, indent=4, cls=NumpyEncoder)

    print(f"Results saved to {output_path}")
