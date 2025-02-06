import argparse
import asyncio
import logging
import time

import langchain
from langchain_huggingface import HuggingFaceEmbeddings

from data_loader import fetch_new_reviews_from_excel
from indexer import ReviewIndexer
from review_processing import process_reviews_in_batches_async
from utils import save_results_to_excel, save_results_to_json

langchain.debug = False


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


# ---------------------------------------------------
# 5. Main Execution Flow with Argument Parsing
# ---------------------------------------------------
def main():
    total_start = time.time()
    section_times = {}  # Dictionary to store elapsed times for each section

    parser = argparse.ArgumentParser(description="Process Excel reviews and classify them using an LLM.")
    parser.add_argument(
        "--industry",
        required=True,
        help="Industry for the reviews (e.g., hotel, restaurant)",
    )
    parser.add_argument(
        "--past",
        required=True,
        help="Path to the Excel file containing historical (past) reviews",
    )
    parser.add_argument(
        "--new",
        required=True,
        help="Path to the Excel file containing new reviews",
    )
    args = parser.parse_args()

    default_industry = args.industry
    past_excel_path = args.past
    new_excel_path = args.new

    print(f"Processing reviews for industry: {default_industry}")
    print(f"Past reviews Excel file path: {past_excel_path}")
    print(f"New reviews Excel file path: {new_excel_path}")

    # Initialize embeddings (using a SentenceTransformer model).
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    # -------------------------------------------------------------------
    # Section 1: Load FAISS vector stores for historical reviews.
    section_start = time.time()
    print("Loading FAISS vector stores for historical reviews...")
    review_indexer = ReviewIndexer(
        past_excel_path=past_excel_path,
        industry=default_industry,
        embeddings=embeddings,
    )
    industry_vectorstores = {default_industry: review_indexer.load_vectorstore()}
    section_end = time.time()
    section_times["Loading FAISS vector stores"] = section_end - section_start
    logger.info(
        "Loading FAISS vector stores for historical reviews took %.2f seconds",
        section_times["Loading FAISS vector stores"],
    )

    # -------------------------------------------------------------------
    # Section 2: Fetch new reviews from Excel.
    section_start = time.time()
    new_reviews = fetch_new_reviews_from_excel(excel_path=new_excel_path, default_industry=default_industry)
    section_end = time.time()
    section_times["Fetching new reviews"] = section_end - section_start
    logger.info("Fetching new reviews took %.2f seconds", section_times["Fetching new reviews"])

    # -------------------------------------------------------------------
    # Section 3: Process new reviews (asynchronously).
    section_start = time.time()
    print("Processing new reviews...")
    review_results = asyncio.run(process_reviews_in_batches_async(new_reviews, industry_vectorstores))
    section_end = time.time()
    section_times["Processing new reviews"] = section_end - section_start
    logger.info(
        "Processing new reviews took %.2f seconds",
        section_times["Processing new reviews"],
    )

    # -------------------------------------------------------------------
    # Section 4: Save results to output files.
    section_start = time.time()
    save_results_to_json(review_results, output_path="output/result.json")
    save_results_to_excel(review_results, output_path="output/result.xlsx")
    section_end = time.time()
    section_times["Saving results"] = section_end - section_start
    logger.info("Saving results took %.2f seconds", section_times["Saving results"])

    # -------------------------------------------------------------------
    total_end = time.time()
    total_time = total_end - total_start
    logger.info("Script total runtime: %.2f seconds", total_time)

    # Print summary of section timings.
    print("\nSection Timings:")
    for section, duration in section_times.items():
        print(f"{section}: {duration:.2f} seconds")
    print(f"\nScript total runtime: {total_time:.2f} seconds")


if __name__ == "__main__":
    main()
