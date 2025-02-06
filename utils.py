import json
import os

import numpy as np
import pandas as pd


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

def save_results_to_excel(results, output_path="output/results.xlsx"):
    # Here, results is assumed to be a list of dictionaries.
    all_data = []
    for res in results:
        print(res.get("similar_reviews", ""))
        all_data.append({
            "NO": res.get("NO", "N/A"),
            "Comment": res.get("new_review", ""),
            "Similar Reviews": res.get("similar_reviews", ""),
            "Categories": ", ".join(res.get("categories", ["N/A"])),
        })
    df = pd.DataFrame(all_data)
    df.to_excel(output_path, index=False)
    print(f"Results have been saved to {output_path}")

def save_results_to_json(results, output_path="output/result.json"):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4, cls=NumpyEncoder)
    print(f"Results have been saved to {output_path}")
