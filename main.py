import argparse
import asyncio
import logging
import time

import langchain

from data_loader import fetch_new_reviews_from_excel
from indexer import FaissRetriever
from review_processing import OpenAILLM, process_reviews_in_batches_async
from utils import save_results_to_excel, save_results_to_json

langchain.debug = False


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

industry_categories = {
    "hotel": ["部屋", "食事", "施設", "スタッフ", "フロント", "サービス", "その他"],
    "restaurant": ["料理の質", "サービス", "雰囲気"],
}

INDEX_DIR_PREFIX = "faiss_index_"


# ---------------------------------------------------
# 5. Main Execution Flow with Argument Parsing
# ---------------------------------------------------
def main():
    section_times = {}  # Dictionary to store elapsed times for each section

    total_start = time.time()

    parser = argparse.ArgumentParser(description="Process Excel reviews and classify them.")
    parser.add_argument("--industry", required=True, help="Industry for the reviews")
    parser.add_argument("--past", required=True, help="Path to past reviews Excel")
    parser.add_argument("--new", required=True, help="Path to new reviews Excel")
    args = parser.parse_args()

    print(f"Processing reviews for industry: {args.industry}")

    # Initialize FAISS and OpenAI models
    section_start = time.time()
    faiss_retriever = FaissRetriever(
        past_excel_path=args.past,  # Excel file with past reviews
        industry=args.industry,
    )
    section_end = time.time()
    section_times["faiss_retriever"] = section_end - section_start

    llm = OpenAILLM()

    # Load new reviews
    section_start = time.time()
    new_reviews = fetch_new_reviews_from_excel(excel_path=args.new, default_industry=args.industry)
    section_end = time.time()
    section_times["fetch_new_reviews_from_excel"] = section_end - section_start

    # Process reviews asynchronously
    section_start = time.time()
    review_results, total_tokens = asyncio.run(
        process_reviews_in_batches_async(new_reviews, faiss_retriever, llm, industry_categories)
    )
    section_end = time.time()
    section_times["process_reviews_in_batches_async"] = section_end - section_start

    # Save results
    section_start = time.time()
    save_results_to_json(review_results, total_tokens, output_dir="output")
    save_results_to_excel(review_results, total_tokens, output_dir="output")
    section_end = time.time()
    section_times["save_results_to_json"] = section_end - section_start
    print("Processing completed.")
    total_end = time.time()
    total_time = total_end - total_start

    print("\nSection Timings:")
    for section, duration in section_times.items():
        print(f"{section}: {duration:.2f} seconds")
    print(f"\nScript total runtime: {total_time:.2f} seconds")
    print(f"Total tokens used: {total_tokens}")


if __name__ == "__main__":
    main()
