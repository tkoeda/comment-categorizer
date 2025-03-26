import json
import os
import time

import numpy as np
import pandas as pd
from app.common.constants import REVIEW_FOLDER_PATHS


def get_unique_filename(
    base_dir: str,
    review_type: str,
    stage: str = "",
    industry_name: str = "",
    extension: str = ".xlsx",
    timestamp: str = None,
) -> str:
    """
    Create a unique filename based on:
      - base directory
      - type_label (e.g., "new", "past")
      - stage (e.g., "combined", "cleaned", "processed")
      - industry (optional, e.g. "hotel")
      - current timestamp

    Returns a full file path that includes all of these segments.
    """
    os.makedirs(base_dir, exist_ok=True)
    if timestamp is None:
        timestamp = time.strftime("%Y%m%d_%H%M%S")

    segments = []
    if industry_name:
        segments.append(industry_name)
    if review_type:
        segments.append(review_type)
    segments.append(timestamp)
    if stage:
        segments.append(stage)

    base_name = "_".join(segments)
    filename = f"{base_name}{extension}"

    return os.path.join(base_dir, filename)


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
    industry_name,
    embeddings_model=None,
    new_combined_path="",
    new_cleaned_path="",
):
    """
    Save review classification results and token usage details to an Excel file.
    The final Excel file will merge:
      - Original reviews (from the intermediate file),
      - Cleaned reviews (from the processed file), and
      - Categorized results (classification output).
    """
    final_dir = os.path.join(
        REVIEW_FOLDER_PATHS.get("final", {}).get("processed", ""), industry_name
    )
    os.makedirs(final_dir, exist_ok=True)
    output_path = get_unique_filename(
        final_dir, review_type="new", extension=".xlsx"
    )

    all_data = []
    for res in results:
        all_data.append(
            {
                "id": res.get("id", "N/A"),
                "Categories": ", ".join(res.get("categories", ["N/A"])),
            }
        )
    df_results = pd.DataFrame(all_data)

    try:
        df_original = pd.read_excel(new_combined_path)
    except Exception as e:
        raise Exception(f"Error reading original file '{new_combined_path}': {e}")

    final_df = pd.merge(df_original, df_results, on="id", how="left")
    df_tokens = pd.DataFrame(
        [
            {
                "Embeddings Model": embeddings_model if embeddings_model else "N/A",
                "Model": model,
                "Total Prompt Tokens Used": token_info.get("total_prompt_tokens", 0),
                "Total Completion Tokens Used": token_info.get(
                    "total_completion_tokens", 0
                ),
                "Prompt Cost ($)": token_info.get("prompt_cost", 0),
                "Completion Cost ($)": token_info.get("completion_cost", 0),
                "Total Cost ($)": token_info.get("total_cost", 0),
                "Total Reviews Processed": token_info.get("total_reviews", 0),
                "Past Reviews Path": token_info.get("past_reviews_path", "N/A"),
                "New Reviews Path": token_info.get("new_reviews_path", "N/A"),
            }
        ]
    )
    df_times = pd.DataFrame(
        list(section_times.items()), columns=["Section", "Duration (seconds)"]
    )

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        final_df.to_excel(writer, sheet_name="Final Results", index=False)
        df_tokens.to_excel(writer, sheet_name="Token Usage", index=False)
        df_times.to_excel(writer, sheet_name="Processing Times", index=False)

    print(f"Results saved to {output_path}")
    return output_path


def save_results_to_json(
    results,
    token_info,
    section_times,
    model,
    embeddings_model=None,
    output_dir="output",
    raw_or_processed="raw",
):
    """
    Save review classification results and token usage details to a JSON file.

    - `model`: Name of the model used (e.g., "pkshatech/GLuCoSE-base-ja-v2").
    """

    output_subdir = os.path.join(
        output_dir, raw_or_processed, embeddings_model or "no_embeddings"
    )
    os.makedirs(output_subdir, exist_ok=True)

    output_path = get_unique_filename(
        os.path.join(output_subdir, type="new", extension=".json")
    )

    results_with_tokens = {
        "embeddings_model": embeddings_model if embeddings_model else "N/A",
        "model": model,
        "past_reviews_path": token_info.get("past_reviews_path", "N/A"),
        "new_reviews_path": token_info.get("new_reviews_path", "N/A"),
        "total_reviews": token_info.get("total_reviews", 0),
        "token_usage": {
            "prompt_tokens": token_info.get("total_prompt_tokens", 0),
            "total_completion_tokens": token_info.get("total_completion_tokens", 0),
            "prompt_cost": token_info.get("total_prompt_cost", 0),
            "completion_cost": token_info.get("total_completion_cost", 0),
            "total_cost": token_info.get("total_cost", 0),
        },
        "processing_times": section_times,
        "reviews": results,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            results_with_tokens, f, ensure_ascii=False, indent=4, cls=NumpyEncoder
        )

    print(f"Results saved to {output_path}")
