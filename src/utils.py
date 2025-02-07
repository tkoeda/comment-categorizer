import json
import os
import time

import numpy as np
import pandas as pd


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


def save_results_to_excel(results, token_info, model, output_dir="output"):
    """
    Save review classification results and token usage details to an Excel file.

    - `results`: List of dictionaries containing review classifications.
    - `token_info`: Dictionary with token usage details (prompt tokens, completion tokens, and cost).
    - `output_dir`: Directory where the Excel file will be saved.
    """

    os.makedirs(output_dir, exist_ok=True)
    output_path = get_unique_filename(os.path.join(output_dir, "results"), ".xlsx")

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
                "Model": model,
                "Prompt Tokens Used": token_info.get("prompt_tokens", 0),
                "Completion Tokens Used": token_info.get("completion_tokens", 0),
                "Prompt Cost ($)": token_info.get("prompt_cost", 0),
                "Completion Cost ($)": token_info.get("completion_cost", 0),
                "Total Cost ($)": token_info.get("total_cost", 0),
                "Total Reviews Processed": token_info.get("total_reviews", 0),
            }
        ]
    )

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df_reviews.to_excel(writer, sheet_name="Reviews", index=False)
        df_tokens.to_excel(writer, sheet_name="Token Usage", index=False)

    print(f"Results saved to {output_path}")


def save_results_to_json(results, token_info, model, output_dir="output"):
    """
    Save review classification results and token usage details to a JSON file.

    - `results`: List of dictionaries containing review classifications.
    - `token_info`: Dictionary with token usage details (prompt tokens, completion tokens, and cost).
    - `output_dir`: Directory where the JSON file will be saved.
    """

    os.makedirs(output_dir, exist_ok=True)
    output_path = get_unique_filename(os.path.join(output_dir, "result"), ".json")

    results_with_tokens = {
        "model": model,
        "total_reviews": token_info.get("total_reviews", 0),
        "token_usage": {
            "prompt_tokens": token_info.get("prompt_tokens", 0),
            "completion_tokens": token_info.get("completion_tokens", 0),
            "prompt_cost": token_info.get("prompt_cost", 0),
            "completion_cost": token_info.get("completion_cost", 0),
            "total_cost": token_info.get("total_cost", 0),
        },
        "reviews": results,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results_with_tokens, f, ensure_ascii=False, indent=4, cls=NumpyEncoder)

    print(f"Results saved to {output_path}")
