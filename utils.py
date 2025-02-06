import json
import os

import pandas as pd


def save_results_to_excel(results, output_path="output/results.xlsx"):
    all_data = []

    for industry, reviews in results.items():
        for res in reviews:
            all_data.append(
                {
                    "NO": res.get("NO", "N/A"),
                    "Comment": res.get("new_review", ""),
                    "Similar Reviews": res.get("similar_reviews", ""),
                    "Categories": ", ".join(res.get("categories", ["N/A"])),
                }
            )

    df = pd.DataFrame(all_data)

    df.to_excel(output_path, index=False)

    print(f"Results have been saved to {output_path}")


def save_results_to_json(results, output_path="output/result.json"):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)

    print(f"Results have been saved to {output_path}")
