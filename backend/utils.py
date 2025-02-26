import json
import os
import time

import re
import numpy as np
import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.progress import Progress

console = Console()


def calculate_average_time(durations):
    """Return the average of a list of durations or 0 if empty."""
    return sum(durations) / len(durations) if durations else 0


def get_unique_filename(base_dir: str, type: str, extension: str = ".xlsx") -> str:
    """
    Create a unique filename based on the base directory, type label, stage, and current timestamp.

    Parameters:
      - base_dir: The directory where the file will be saved.
      - type: A label indicating the type (e.g., "new", "past").
      - stage: The processing stage (e.g., "raw", "intermediate", "processed", "final").
      - extension: File extension (default ".xlsx").

    Returns:
      A full file path that includes a timestamp and the type label.
    """
    os.makedirs(base_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"{type}_{timestamp}{extension}"
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
    embeddings_model=None,
    output_dir="output",
    raw_or_processed="processed",
    # These paths are where the original (combined) and cleaned data are stored.
    original_file="data/new_intermediate/new_intermediate.xlsx",
    cleaned_file="data/new_processed/new_processed.xlsx",
):
    """
    Save review classification results and token usage details to an Excel file.
    The final Excel file will merge:
      - Original reviews (from the intermediate file),
      - Cleaned reviews (from the processed file), and
      - Categorized results (classification output).
    """
    output_subdir = os.path.join(output_dir, raw_or_processed, embeddings_model or "no_embeddings")
    os.makedirs(output_subdir, exist_ok=True)
    output_path = get_unique_filename(output_subdir, type="new", extension=".xlsx")

    # Build classification results as a DataFrame (we assume each result has an "id" and "categories")
    all_data = []
    for res in results:
        all_data.append(
            {
                "id": res.get("id", "N/A"),
                "Categories": ", ".join(res.get("categories", ["N/A"])),
            }
        )
    df_results = pd.DataFrame(all_data)

    # Read the original (combined) reviews.
    try:
        df_original = pd.read_excel(original_file)
    except Exception as e:
        raise Exception(f"Error reading original file '{original_file}': {e}")

    # Read the cleaned reviews.
    try:
        df_cleaned = pd.read_excel(cleaned_file)
    except Exception as e:
        raise Exception(f"Error reading cleaned file '{cleaned_file}': {e}")

    # For clarity, rename the review columns:
    # We assume that the original file has a column (e.g., "コメント") for the raw review.
    # And the cleaned file has that same column (or a cleaned version) which we rename.
    df_original = df_original.rename(columns={"コメント": "Original Review"})
    df_cleaned = df_cleaned.rename(columns={"コメント": "Cleaned Review"})

    # Merge the original and cleaned reviews on "id".
    df_combined = pd.merge(df_original, df_cleaned, on="id", how="left")
    # Merge the classification results (which contain categories) on "id".
    final_df = pd.merge(df_combined, df_results, on="id", how="left")

    # Create additional sheets for token usage and processing times.
    df_tokens = pd.DataFrame(
        [
            {
                "Embeddings Model": embeddings_model if embeddings_model else "N/A",
                "Model": model,
                "Total Prompt Tokens Used": token_info.get("total_prompt_tokens", 0),
                "Total Completion Tokens Used": token_info.get("total_completion_tokens", 0),
                "Prompt Cost ($)": token_info.get("prompt_cost", 0),
                "Completion Cost ($)": token_info.get("completion_cost", 0),
                "Total Cost ($)": token_info.get("total_cost", 0),
                "Total Reviews Processed": token_info.get("total_reviews", 0),
                "Past Reviews Path": token_info.get("past_reviews_path", "N/A"),
                "New Reviews Path": token_info.get("new_reviews_path", "N/A"),
            }
        ]
    )
    df_times = pd.DataFrame(list(section_times.items()), columns=["Section", "Duration (seconds)"])

    # Write all data to Excel (multiple sheets).
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

    output_subdir = os.path.join(output_dir, raw_or_processed, embeddings_model or "no_embeddings")
    os.makedirs(output_subdir, exist_ok=True)

    output_path = get_unique_filename(os.path.join(output_subdir, type="new", extension=".json"))

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
        json.dump(results_with_tokens, f, ensure_ascii=False, indent=4, cls=NumpyEncoder)

    print(f"Results saved to {output_path}")


def print_rate_limit_info(response):
    headers = response.headers

    # Create a rich table
    table = Table(title="Rate Limit Information", show_header=True, header_style="bold magenta")

    # Define columns
    table.add_column("Field", style="bold cyan")
    table.add_column("Value", style="bold yellow")
    table.add_column("Description", style="dim white")

    # Add rows with rate limit information and explanations
    table.add_row(
        "openai-processing-ms",
        headers.get("openai-processing-ms", "N/A") + "ms",
        "openai-processing-ms",
    )
    table.add_row(
        "x-ratelimit-limit-requests",
        headers.get("x-ratelimit-limit-requests", "N/A"),
        "The max number of requests allowed before hitting the rate limit.",
    )
    table.add_row(
        "x-ratelimit-limit-tokens",
        headers.get("x-ratelimit-limit-tokens", "N/A"),
        "The max number of tokens allowed before hitting the rate limit.",
    )
    table.add_row(
        "x-ratelimit-remaining-requests",
        headers.get("x-ratelimit-remaining-requests", "N/A"),
        "The number of requests you have left before hitting the limit.",
    )
    table.add_row(
        "x-ratelimit-remaining-tokens",
        headers.get("x-ratelimit-remaining-tokens", "N/A"),
        "The number of tokens you have left before hitting the limit.",
    )
    table.add_row(
        "x-ratelimit-reset-requests",
        headers.get("x-ratelimit-reset-requests", "N/A"),
        "Time until request limit resets (e.g., 1s means 1 second).",
    )
    table.add_row(
        "x-ratelimit-reset-tokens",
        headers.get("x-ratelimit-reset-tokens", "N/A"),
        "Time until token limit resets (e.g., 6m0s means 6 minutes).",
    )

    # Print the table
    console.print(table)


def time_to_seconds(time_str):
    """
    Convert a time string like "5m33s", "599ms", or "59.548s" into seconds (float).
    """
    match = re.match(r"(?:(\d+)m)?(?:(\d+(?:\.\d+)?)s)?(?:(\d+)ms)?", time_str)
    if not match:
        raise ValueError(f"Invalid time format: {time_str}")

    minutes = int(match.group(1)) * 60 if match.group(1) else 0
    seconds = float(match.group(2)) if match.group(2) else 0
    milliseconds = int(match.group(3)) / 1000 if match.group(3) else 0

    return minutes + seconds + milliseconds


def display_rate_limit_progress(headers):
    """
    Displays rate limit progress bars for remaining tokens and requests.
    """
    total_requests = int(headers.get("x-ratelimit-limit-requests", 10000))
    remaining_requests = int(headers.get("x-ratelimit-remaining-requests", 10000))

    total_tokens = int(headers.get("x-ratelimit-limit-tokens", 200000))
    remaining_tokens = int(headers.get("x-ratelimit-remaining-tokens", 200000))

    console.clear()  # Clear old progress before showing new

    with Progress() as progress:
        req_task = progress.add_task("[cyan]Remaining Requests...", total=total_requests)
        tok_task = progress.add_task("[green]Remaining Tokens...", total=total_tokens)

        # Update progress bars
        progress.update(req_task, completed=remaining_requests)
        progress.update(tok_task, completed=remaining_tokens)

        # console.print(f"[yellow]Remaining Requests: {remaining_requests}/{total_requests}[/yellow]")


def print_status_tracker(status_tracker):
    console = Console()
    table = Table(title="Batch Processing Status Tracker", title_style="bold blue")

    table.add_column("Metric", style="cyan", justify="left")
    table.add_column("Value", style="magenta", justify="right")

    table.add_row("Batches Started", str(status_tracker.num_batches_started))
    table.add_row("Batches Succeeded", str(status_tracker.num_batches_succeeded))
    table.add_row("Batches Failed", str(status_tracker.num_batches_failed))

    console.print(table)
