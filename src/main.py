import argparse
import asyncio
import logging
import os
import time

from rich.console import Console
from rich.table import Table

from data_loader import fetch_new_reviews_from_excel
from indexer import FaissRetriever
from review_processing import OpenAILLM, process_reviews_in_batches_async
from utils import save_results_to_excel, save_results_to_json

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

os.environ["TOKENIZERS_PARALLELISM"] = "false"


gpt4o_cost = {
    "prompt": 0.15,
    "completion": 0.60,
}

gpt3_turbo_cost = {
    "prompt": 0.5,
    "completion": 1.5,
}

industry_categories = {
    "hotel": ["部屋", "食事", "施設", "スタッフ", "フロント", "サービス", "その他"],
    "restaurant": ["料理の質", "サービス", "雰囲気"],
}

INDEX_DIR_PREFIX = "faiss_index_"


console = Console()

def main():
    section_times = {}  # Store elapsed times for each section
    total_start = time.time()

    parser = argparse.ArgumentParser(
        description="Process Excel reviews and classify them."
    )
    parser.add_argument("--industry", required=True, help="Industry for the reviews")
    parser.add_argument("--past", required=True, help="Path to past reviews Excel")
    parser.add_argument("--new", required=True, help="Path to new reviews Excel")
    args = parser.parse_args()
    
    past_excel_path = os.path.abspath(args.past)
    new_excel_path = os.path.abspath(args.new)
    
    print("Using past Excel file at:", past_excel_path)
    print("Using new Excel file at:", new_excel_path)

    console.print(f"[bold green]Processing reviews for industry: {args.industry}[/bold green]")

    # Initialize FAISS retriever
    section_start = time.time()
    faiss_retriever = FaissRetriever(
        past_excel_path=past_excel_path,  # Excel file with past reviews
        industry=args.industry,
    )
    section_end = time.time()
    section_times["faiss_retriever"] = section_end - section_start

    llm = OpenAILLM(model="gpt-4o-mini-2024-07-18", temperature=0)

    # Load new reviews
    section_start = time.time()
    new_reviews = fetch_new_reviews_from_excel(
        excel_path=new_excel_path, default_industry=args.industry
    )
    section_end = time.time()
    section_times["fetch_new_reviews_from_excel"] = section_end - section_start

    # Process reviews asynchronously
    section_start = time.time()
    review_results, (prompt_tokens, completion_tokens) = asyncio.run(
        process_reviews_in_batches_async(new_reviews, faiss_retriever, llm, industry_categories)
    )
    section_end = time.time()
    section_times["process_reviews_in_batches_async"] = section_end - section_start

    # Compute total reviews processed and print it
    total_reviews = len(review_results)
    console.print(f"[bold blue]Total reviews processed: {total_reviews}[/bold blue]")

    # Compute cost based on the model used
    if llm.model.startswith("gpt-4o-mini"):
        prompt_cost = (prompt_tokens / 1_000_000) * gpt4o_cost["prompt"]
        completion_cost = (completion_tokens / 1_000_000) * gpt4o_cost["completion"]
    elif llm.model.startswith("gpt-3.5-turbo"):
        prompt_cost = (prompt_tokens / 1_000_000) * gpt3_turbo_cost["prompt"]
        completion_cost = (completion_tokens / 1_000_000) * gpt3_turbo_cost["completion"]
    else:
        prompt_cost = 0.0
        completion_cost = 0.0

    total_cost = prompt_cost + completion_cost

    # Create a table for token usage and cost details
    cost_table = Table(title="Token and Cost Details", title_style="bold magenta")
    cost_table.add_column("Prompt Tokens", justify="right")
    cost_table.add_column("Completion Tokens", justify="right")
    cost_table.add_column("Prompt Cost ($)", justify="right")
    cost_table.add_column("Completion Cost ($)", justify="right")
    cost_table.add_column("Total Cost ($)", justify="right")
    cost_table.add_row(
       f"{prompt_tokens}",
       f"{completion_tokens}",
       f"${prompt_cost:.6f}",
       f"${completion_cost:.6f}",
       f"${total_cost:.6f}"
    )
    console.print(cost_table)

    # Prepare metadata to send to save functions, including total_reviews
    token_info = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "prompt_cost": prompt_cost,
        "completion_cost": completion_cost,
        "total_cost": total_cost,
        "total_reviews": total_reviews,
    }

    # Save results including token info and cost details
    section_start = time.time()
    save_results_to_json(review_results, token_info, model=llm.model, output_dir="output")
    save_results_to_excel(review_results, token_info, model=llm.model, output_dir="output")
    section_end = time.time()
    section_times["save_results"] = section_end - section_start

    console.print("[bold green]Processing completed.[/bold green]")
    total_end = time.time()
    total_time = total_end - total_start

    # Create a table for section timings
    timing_table = Table(title="Section Timings", title_style="bold cyan")
    timing_table.add_column("Section", justify="left")
    timing_table.add_column("Duration (seconds)", justify="right")
    for section, duration in section_times.items():
        timing_table.add_row(section, f"{duration:.2f}")
    console.print(timing_table)

    console.print(f"[bold magenta]Script total runtime: {total_time:.2f} seconds[/bold magenta]")
    console.print("[bold green]Script completed.[/bold green]")


if __name__ == "__main__":
    main()
