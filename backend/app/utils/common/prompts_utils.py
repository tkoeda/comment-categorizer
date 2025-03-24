import json
import os
from datetime import datetime


def append_prompt_to_json(prompt, output_file="prompts.json"):
    """
    Appends a prompt (with metadata) to a JSON file.
    If the file does not exist or is empty, it creates a new structure.
    Each entry includes a timestamp.
    """
    new_entry = {
        "timestamp": datetime.now().isoformat(),
        "prompt": prompt,
    }

    if os.path.exists(output_file):
        try:
            with open(output_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            data = {"prompts": []}
    else:
        data = {"prompts": []}

    data["prompts"].append(new_entry)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
