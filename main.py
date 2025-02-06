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
    total_start = time.time()
    
    parser = argparse.ArgumentParser(description="Process Excel reviews and classify them.")
    parser.add_argument("--industry", required=True, help="Industry for the reviews")
    parser.add_argument("--past", required=True, help="Path to past reviews Excel")
    parser.add_argument("--new", required=True, help="Path to new reviews Excel")
    args = parser.parse_args()

    print(f"Processing reviews for industry: {args.industry}")

    # Initialize FAISS and OpenAI models

    faiss_retriever = FaissRetriever(
        past_excel_path=args.past,   # Excel file with past reviews
        index_dir=f"{INDEX_DIR_PREFIX}{args.industry}",  # e.g., "faiss_index_hotel"
        industry=args.industry
)

    llm = OpenAILLM()

    # Load new reviews
    new_reviews = fetch_new_reviews_from_excel(excel_path=args.new, default_industry=args.industry)

    # Process reviews asynchronously
    review_results = asyncio.run(process_reviews_in_batches_async(new_reviews, faiss_retriever, llm, industry_categories))

    # Save results
    save_results_to_json(review_results, output_path="output/result.json")
    save_results_to_excel(review_results, output_path="output/result.xlsx")

    print("Processing completed.")
    total_end = time.time()
    print(f"Total processing time: {total_end - total_start} seconds")

if __name__ == "__main__":
    main()
