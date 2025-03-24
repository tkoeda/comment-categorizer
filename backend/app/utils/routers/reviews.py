import os
import time

from app.constants import GPT_PRICING, MODEL
from app.models.industries import Industry
from app.rag_pipeline.indexer import DummyRetriever
from app.rag_pipeline.openai_llm import OpenAILLM
from app.rag_pipeline.process_reviews import process_reviews_in_batches_async
from app.utils.common.calc_utils import calculate_average_time
from app.utils.common.console_utils import print_status_tracker
from app.utils.common.io_utils import save_results_to_excel
from rich.console import Console
from rich.table import Table

console = Console()


async def classify_and_merge(
    industry: Industry,
    new_reviews,
    retriever,
    new_combined_path: str,
    new_cleaned_path: str,
    use_past_reviews: bool = False,
    user_api_key: str = None,
) -> str:
    """
    Runs the classification pipeline and computes diagnostics (token counts, cost, etc.),
    merges the classification results with the original and cleaned files via save_results_to_excel(),
    and returns the final Excel file path.

    Args:
        industry: Industry object for the reviews
        new_reviews: List of new reviews to classify
        retriever: FaissRetriever or DummyRetriever instance (already initialized)
        new_combined_path: Path to the combined new reviews file
        new_cleaned_path: Path to the cleaned new reviews file
        use_past_reviews: Flag indicating whether past reviews are being used
    """
    total_start = time.time()

    # Initialize the LLM
    llm = OpenAILLM(api_key=user_api_key, model=MODEL, temperature=0.5)

    # Process reviews in batches using the provided retriever
    result = await process_reviews_in_batches_async(
        new_reviews,
        retriever,
        llm,
        industry,
        reviews_per_batch=20,
        max_concurrent_batches=20,
        max_attempts=3,
    )

    results = result.results
    retrieval_durations = result.retrieval_durations
    status_tracker = result.status_tracker
    avg_length = result.avg_length

    print_status_tracker(status_tracker)

    # Calculate token usage and costs
    total_prompt_tokens = llm.total_prompt_tokens
    total_completion_tokens = llm.total_completion_tokens
    total_tokens = llm.total_tokens
    total_api_calls = llm.api_calls

    # Track section times
    section_times = {}

    # Only record retrieval timing if we're using a FaissRetriever (not DummyRetriever)
    if use_past_reviews and not isinstance(retriever, DummyRetriever):
        section_times["retrieval_processing"] = calculate_average_time(
            retrieval_durations
        )
        retriever_type = "FAISS"
        embeddings_model = getattr(retriever, "embeddings_model_name", "default")
    else:
        section_times["retrieval_processing"] = "N/A"
        retriever_type = "None"
        embeddings_model = None

    # Calculate API call timing
    avg_api_call_duration_ms = calculate_average_time(llm.api_call_durations)
    section_times["avg_api_call_duration"] = avg_api_call_duration_ms / 1000

    # Calculate costs
    if "gpt-4o-mini" in llm.model:
        gpt_model = "gpt-4o-mini"
    else:
        gpt_model = llm.model.split("-")[0]

    model_pricing = GPT_PRICING.get(gpt_model, {"prompt": 0.0, "completion": 0.0})

    if llm.model.startswith("gpt-4o-mini"):
        total_prompt_cost = (total_prompt_tokens / 1_000_000) * model_pricing[
            "prompt"
        ]
        total_completion_cost = (
            total_completion_tokens / 1_000_000
        ) * model_pricing["completion"]
    else:
        total_prompt_cost = 0.0
        total_completion_cost = 0.0

    total_cost = total_prompt_cost + total_completion_cost

    # Calculate total processing time
    total_end = time.time()
    total_time = total_end - total_start
    section_times["total_processing"] = total_time

    # Compile token usage information
    token_info = {
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "prompt_cost": total_prompt_cost,
        "completion_cost": total_completion_cost,
        "total_cost": total_cost,
        "total_reviews": len(results),
        "retriever_type": retriever_type,
        "past_reviews_path": "Using FAISS index"
        if use_past_reviews
        else "Not using past reviews",
        "new_reviews_path": new_combined_path,
    }

    # Print diagnostic information to console
    def print_diagnostics():
        cost_table = Table(
            title="Token and Cost Details", title_style="bold magenta"
        )
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

        if total_api_calls > 0:
            console.print(
                f"[bold yellow]Average Total Tokens: {total_tokens / total_api_calls:.2f} tokens[/bold yellow]"
            )
        else:
            console.print("[bold yellow]No API calls made.[/bold yellow]")

        console.print(
            f"[bold yellow]Average Review Length: {avg_length:.2f} words[/bold yellow]"
        )
        console.print(
            f"[bold magenta]Total Runtime: {total_time:.2f} seconds[/bold magenta]"
        )

    print_diagnostics()

    # Save results to Excel file
    start_save = time.time()
    output_excel_path = save_results_to_excel(
        results,
        token_info,
        section_times,
        model=llm.model,
        industry_name=industry.name,
        embeddings_model=embeddings_model,
        new_combined_path=new_combined_path,
        new_cleaned_path=new_cleaned_path,
    )
    section_times["saving_results"] = time.time() - start_save

    return output_excel_path


def clean_up_files(temp_files, combined_file, cleaned_file):
    """Helper function to clean up files when an error occurs"""
    # Clean up temporary files
    for file_path in temp_files:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass

    # Delete combined file if it was created
    if combined_file and os.path.exists(combined_file):
        try:
            os.remove(combined_file)
        except OSError:
            pass

    # Delete cleaned file if it was created
    if cleaned_file and os.path.exists(cleaned_file):
        try:
            os.remove(cleaned_file)
        except OSError:
            pass
