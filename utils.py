import json
import os
import time

import numpy as np
import pandas as pd


def get_unique_filename(base_path, extension):
    """
    Generate a unique filename by appending a timestamp or incremental number if the file exists.
    """
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    return f"{base_path}_{timestamp}{extension}"


# Custom JSON encoder to handle NumPy types if needed.
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        elif isinstance(obj, (np.floating,)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)


def save_results_to_excel(results, total_tokens, output_dir="output/results.xlsx"):
    # Here, results is assumed to be a list of dictionaries.

    os.makedirs(output_dir, exist_ok=True)
    output_path = get_unique_filename(os.path.join(output_dir, "results"), ".xlsx")

    all_data = []
    for res in results:
        all_data.append(
            {
                "NO": res.get("NO", "N/A"),
                "Comment": res.get("new_review", ""),
                "Similar Reviews": res.get("similar_reviews", ""),
                "Categories": ", ".join(res.get("categories", ["N/A"])),
            }
        )

    df = pd.DataFrame(all_data)

    # Save DataFrame to an Excel file using `openpyxl` instead of `xlsxwriter`
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Reviews", index=False)

        # Save the total token count in a separate sheet
        token_df = pd.DataFrame([{"total_tokens_used": total_tokens}])
        token_df.to_excel(writer, sheet_name="Token Usage", index=False)

    print(f"Results saved to {output_path}")


def save_results_to_json(results, total_tokens, output_dir="output/result.json"):
    os.makedirs(output_dir, exist_ok=True)
    output_path = get_unique_filename(os.path.join(output_dir, "result"), ".json")

    # Add total tokens to results
    results_with_tokens = {"total_tokens_used": total_tokens, "reviews": results}

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results_with_tokens, f, ensure_ascii=False, indent=4)

    print(f"Results saved to {output_path}")
