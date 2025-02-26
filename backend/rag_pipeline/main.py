import argparse
import asyncio
import logging
import os
import time

from rich.console import Console
from rich.table import Table

from data_loader import fetch_new_reviews_from_excel

from indexer import FaissRetriever

from rag_pipeline.indexer import FaissRetrieverV2
from constants import GPT_PRICING, INDUSTRY_CATEGORIES, MODEL
from process_reviews import process_reviews_in_batches_async
from openai_llm import OpenAILLM
from utils import save_results_to_excel, save_results_to_json, calculate_average_time, print_status_tracker

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

os.environ["TOKENIZERS_PARALLELISM"] = "false"


console = Console()


def main():
    section_times = {}
    total_start = time.time()
    parser = argparse.ArgumentParser(description="Process Excel reviews and classify them.")
    parser.add_argument("--industry", required=True, help="Industry for the reviews")
    parser.add_argument("--past", required=True, help="Path to past reviews Excel")
    parser.add_argument("--new", required=True, help="Path to new reviews Excel")
    parser.add_argument("--v2", action="store_true", help="Enable v2 version of embedding model")
    args = parser.parse_args()
    past_excel_path = os.path.abspath(args.past)
    new_excel_path = os.path.abspath(args.new)
    raw_or_processed = "processed" if "processed" in past_excel_path else "raw"
    print("Using past Excel file at:", past_excel_path)
    print("Using new Excel file at:", new_excel_path)

    console.print(f"[bold green]Processing reviews for industry: {args.industry}[/bold green]")

    section_start = time.time()
    new_reviews = fetch_new_reviews_from_excel(excel_path=new_excel_path, default_industry=args.industry)
    section_end = time.time()
    section_times["fetch_new_reviews_from_excel"] = section_end - section_start

    llm = OpenAILLM(model=MODEL, temperature=0)

    section_start = time.time()
    if args.v2:
        faiss_retriever = FaissRetrieverV2(industry=args.industry, past_excel_path=past_excel_path)
    else:
        faiss_retriever = FaissRetriever(industry=args.industry, past_excel_path=past_excel_path)
    section_end = time.time()
    section_times["faiss_retriever"] = section_end - section_start
    embeddings_model = faiss_retriever.embeddings_model_name
    section_start = time.time()
    review_results, retrieval_durations, llm, status_tracker, average_review_length = asyncio.run(
        process_reviews_in_batches_async(new_reviews, faiss_retriever, llm, INDUSTRY_CATEGORIES)
    )

    total_prompt_tokens = llm.total_prompt_tokens
    total_completion_tokens = llm.total_completion_tokens
    total_tokens = llm.total_tokens
    total_api_calls = llm.api_calls

    section_times["retrieval_processing"] = calculate_average_time(retrieval_durations)
    section_end = time.time()
    avg_faiss_retrieval_duration = calculate_average_time(retrieval_durations)
    section_times["avg_faiss_retrieval_duration"] = avg_faiss_retrieval_duration

    section_times["process_reviews"] = section_end - section_start

    total_reviews = len(review_results)
    console.print(f"[bold blue]Total reviews processed: {total_reviews}[/bold blue]")

    avg_api_call_duration_ms = calculate_average_time(llm.api_call_durations)
    section_times["avg_api_call_duration"] = avg_api_call_duration_ms / 1000

    if "gpt-4o-mini" in llm.model:
        gpt_model = "gpt-4o-mini"
    else:
        gpt_model = llm.model.split("-")[0]

    model_pricing = GPT_PRICING.get(gpt_model, {"prompt": 0.0, "completion": 0.0})
    if llm.model.startswith("gpt-4o-mini"):
        total_prompt_cost = (total_prompt_tokens / 1_000_000) * model_pricing["prompt"]
        total_completion_cost = (total_completion_tokens / 1_000_000) * model_pricing["completion"]
    else:
        total_prompt_cost = 0.0
        total_completion_cost = 0.0

    total_cost = total_prompt_cost + total_completion_cost

    cost_table = Table(title="Token and Cost Details", title_style="bold magenta")
    cost_table.add_column("Total Prompt Tokens", justify="right")
    cost_table.add_column("Total Completion Tokens", justify="right")
    cost_table.add_column("Total Prompt Cost ($)", justify="right")
    cost_table.add_column("Total Completion Cost ($)", justify="right")
    cost_table.add_column("Total Cost ($)", justify="right")
    cost_table.add_row(
        f"{total_prompt_tokens}",
        f"{total_completion_tokens}",
        f"${total_prompt_cost:.6f}",
        f"${total_completion_cost:.6f}",
        f"${total_cost:.6f}",
    )
    console.print(cost_table)

    total_end = time.time()
    section_times["total_processing"] = total_end - total_start

    token_info = {
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "prompt_cost": total_prompt_cost,
        "completion_cost": total_completion_cost,
        "total_cost": total_cost,
        "total_reviews": total_reviews,
        "past_reviews_path": past_excel_path,
        "new_reviews_path": new_excel_path,
    }

    section_start = time.time()
    save_results_to_json(
        review_results,
        token_info,
        section_times,
        model=llm.model,
        embeddings_model=embeddings_model,
        output_dir="output",
        raw_or_processed=raw_or_processed,
    )
    save_results_to_excel(
        review_results,
        token_info,
        section_times,
        model=llm.model,
        embeddings_model=embeddings_model,
        output_dir="output",
        raw_or_processed=raw_or_processed,
    )
    section_end = time.time()
    section_times["save_results"] = section_end - section_start

    console.print("[bold green]Processing completed.[/bold green]")
    total_end = time.time()
    total_time = total_end - total_start

    print_status_tracker(status_tracker)

    timing_table = Table(title="Section Timings", title_style="bold cyan")
    timing_table.add_column("Section", justify="left")
    timing_table.add_column("Duration (seconds)", justify="right")
    for section, duration in section_times.items():
        timing_table.add_row(section, f"{duration:.2f}")
    console.print(timing_table)

    console.print(f"[bold yellow]Average Total Tokens: {total_tokens / total_api_calls} tokens[/bold yellow]")
    console.print(f"[bold yellow]Average Review Length: {average_review_length} words[/bold yellow]")
    console.print(f"[bold magenta]Script total runtime: {total_time:.2f} seconds[/bold magenta]")
    console.print("[bold green]Script completed.[/bold green]")


if __name__ == "__main__":
    main()
