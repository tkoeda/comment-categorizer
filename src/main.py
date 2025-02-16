import argparse
import asyncio
import logging
import os
import time

from rich.console import Console
from rich.table import Table

from data_loader import fetch_new_reviews_from_excel

from indexer import FaissRetriever

from indexer_v2 import FaissRetrieverV2
from config import GPT_PRICING, INDUSTRY_CATEGORIES
from process_reviews import process_reviews_in_batches_async
from openai_llm import OpenAILLM
from process_reviews_no_rag import process_reviews_in_batches_async_no_rag
from utils import save_results_to_excel, save_results_to_json, calculate_average_time

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
    parser.add_argument("--use-rag", action="store_true", help="Enable FAISS-based retrieval (RAG)")
    parser.add_argument("--v2", action="store_true", help="Enable v2 version of embedding model")
    args = parser.parse_args()
    past_excel_path = os.path.abspath(args.past)
    new_excel_path = os.path.abspath(args.new)
    raw_or_cleaned = "cleaned" if "cleaned" in past_excel_path else "raw"
    print("Using past Excel file at:", past_excel_path)
    print("Using new Excel file at:", new_excel_path)

    console.print(f"[bold green]Processing reviews for industry: {args.industry}[/bold green]")

    section_start = time.time()
    new_reviews = fetch_new_reviews_from_excel(excel_path=new_excel_path, default_industry=args.industry)
    section_end = time.time()
    section_times["fetch_new_reviews_from_excel"] = section_end - section_start

    llm = OpenAILLM(model="gpt-4o-mini-2024-07-18", temperature=0)

    if args.use_rag:
        console.print("[bold cyan]Using FAISS-based retrieval (RAG mode).[/bold cyan]")
        section_start = time.time()
        if args.v2:
            faiss_retriever = FaissRetrieverV2(industry=args.industry, past_excel_path=past_excel_path)
        else:
            faiss_retriever = FaissRetriever(industry=args.industry, past_excel_path=past_excel_path)
        section_end = time.time()
        section_times["faiss_retriever"] = section_end - section_start
        embeddings_model = faiss_retriever.embeddings_model_name
        section_start = time.time()
        review_results, (prompt_tokens, completion_tokens), retrieval_durations, average_similar_review_length = (
            asyncio.run(process_reviews_in_batches_async(new_reviews, faiss_retriever, llm, INDUSTRY_CATEGORIES))
        )
        section_times["retrieval_processing"] = calculate_average_time(retrieval_durations)
        section_end = time.time()
        avg_faiss_retrieval_duration = calculate_average_time(retrieval_durations)
        section_times["avg_faiss_retrieval_duration"] = avg_faiss_retrieval_duration
    else:
        average_similar_review_length = None
        embeddings_model = None
        console.print("[bold cyan]Skipping FAISS retrieval. Using direct classification (non-RAG mode).[/bold cyan]")
        section_start = time.time()
        review_results, (prompt_tokens, completion_tokens) = asyncio.run(
            process_reviews_in_batches_async_no_rag(new_reviews, llm, INDUSTRY_CATEGORIES)
        )
        section_end = time.time()

    section_times["process_reviews"] = section_end - section_start

    total_reviews = len(review_results)
    console.print(f"[bold blue]Total reviews processed: {total_reviews}[/bold blue]")

    avg_api_call_duration = calculate_average_time(llm.api_call_durations)
    section_times["avg_api_call_duration"] = avg_api_call_duration

    if "gpt-3.5-turbo" in llm.model:
        gpt_model = "gpt-3.5-turbo"
    elif "gpt-4o" in llm.model:
        gpt_model = "gpt-4o"
    else:
        gpt_model = llm.model.split("-")[0]

    model_pricing = GPT_PRICING.get(gpt_model, {"prompt": 0.0, "completion": 0.0})
    if llm.model.startswith("gpt-4o-mini"):
        prompt_cost = (prompt_tokens / 1_000_000) * model_pricing["prompt"]
        completion_cost = (completion_tokens / 1_000_000) * model_pricing["completion"]
    elif llm.model.startswith("gpt-3.5-turbo"):
        prompt_cost = (prompt_tokens / 1_000_000) * model_pricing["prompt"]
        completion_cost = (completion_tokens / 1_000_000) * model_pricing["completion"]
    else:
        prompt_cost = 0.0
        completion_cost = 0.0

    total_cost = prompt_cost + completion_cost

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
        f"${total_cost:.6f}",
    )
    console.print(cost_table)

    token_info = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "prompt_cost": prompt_cost,
        "completion_cost": completion_cost,
        "total_cost": total_cost,
        "total_reviews": total_reviews,
        "past_reviews_path": past_excel_path,
        "new_reviews_path": new_excel_path,
    }
    total_end = time.time()
    section_times["total_processing"] = total_end - total_start

    section_start = time.time()
    save_results_to_json(
        review_results,
        token_info,
        section_times,
        model=llm.model,
        embeddings_model=embeddings_model,
        output_dir="output",
        use_rag=args.use_rag,
        raw_or_cleaned=raw_or_cleaned,
        average_similar_review_length=average_similar_review_length,
    )
    save_results_to_excel(
        review_results,
        token_info,
        section_times,
        model=llm.model,
        embeddings_model=embeddings_model,
        output_dir="output",
        use_rag=args.use_rag,
        raw_or_cleaned=raw_or_cleaned,
        average_similar_review_length=average_similar_review_length,
    )
    section_end = time.time()
    section_times["save_results"] = section_end - section_start

    console.print("[bold green]Processing completed.[/bold green]")
    total_end = time.time()
    total_time = total_end - total_start

    timing_table = Table(title="Section Timings", title_style="bold cyan")
    timing_table.add_column("Section", justify="left")
    timing_table.add_column("Duration (seconds)", justify="right")
    for section, duration in section_times.items():
        timing_table.add_row(section, f"{duration:.2f}")
    console.print(timing_table)
    console.print(
        f"[bold yellow]Average Similar Review Length: {average_similar_review_length:.2f} characters[/bold yellow]"
    )

    console.print(f"[bold magenta]Script total runtime: {total_time:.2f} seconds[/bold magenta]")
    console.print("[bold green]Script completed.[/bold green]")


if __name__ == "__main__":
    main()
