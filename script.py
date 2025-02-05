import argparse
import asyncio
import concurrent.futures
import getpass
import json
import logging
import os
import time

import langchain
import pandas as pd
from dotenv import load_dotenv
from langchain.callbacks import get_openai_callback
from langchain.prompts import PromptTemplate
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI

from data_loader import fetch_new_reviews_from_excel
from indexer import ReviewIndexer

langchain.debug = True


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

if not os.getenv("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = getpass.getpass("Enter your OpenAI API key: ")

openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError(
        "Error: OPENAI_API_KEY is not set. Please add it to your .env file."
    )

# Define a custom executor with increased concurrency.
# Adjust max_workers based on your machine and API limits.
CUSTOM_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=25)

industry_categories = {
    "hotel": ["部屋", "食事", "施設", "スタッフ", "フロント", "サービス", "その他"],
    "restaurant": ["料理の質", "サービス", "雰囲気"],
}

# Prompt template for classifying and summarizing new reviews.
prompt_template = """
新しいレビュー:  
"{new_review}"

類似レビュー:
{similar_reviews}

可能なカテゴリ: {categories}

タスク:
- 上記の新しいレビューを、提示されたカテゴリの中から最も適切なもの **1つ以上** に分類してください。
- 該当するカテゴリを **リスト形式** で出力してください（複数選択可）。
- レビューの要点を1〜2文で要約してください。

出力は、次のJSONフォーマットに従ってください:
{{
    "categories": ["選ばれたカテゴリ1", "選ばれたカテゴリ2", ...],
    "summary": "レビューの要点を1〜2文で要約した内容"
}}
"""

prompt = PromptTemplate(
    input_variables=["new_review", "similar_reviews", "categories"],
    template=prompt_template,
)

# Initialize the LLM (ensure your OPENAI_API_KEY is set in your environment)
llm = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0)
chain = prompt | llm


# Asynchronous wrapper that uses the custom executor.
async def async_invoke(input_data):
    loop = asyncio.get_running_loop()
    # Wrap chain.invoke in run_in_executor to make it non-blocking
    return await loop.run_in_executor(CUSTOM_EXECUTOR, chain.invoke, input_data)


def retrieve_similar_reviews_parallel(retriever, reviews, max_workers=25):
    """
    Uses parallel processing to retrieve similar reviews from FAISS.
    Returns a dictionary mapping each review's "NO" to its similar reviews string.
    """

    def retrieve(review):
        docs = retriever.invoke(review["text"])
        # Filter out documents that exactly match the new review text.
        filtered_docs = [
            doc for doc in docs if doc.page_content.strip() != review["text"].strip()
        ]

        # Limit the results to a maximum of 3 similar reviews.
        filtered_docs = filtered_docs[:3]

        # Build the string output for the similar reviews.
        similar_reviews_str = "\n".join(
            [f'{i + 1}. "{doc.page_content}"' for i, doc in enumerate(filtered_docs)]
        )
        return review.get("NO", None), similar_reviews_str

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(retrieve, reviews))
    # Convert list of tuples to a dictionary
    return dict(results)


def process_reviews_in_batches(new_reviews, industry_vectorstores, batch_size=20):
    """
    Processes new reviews in batches.
    Retrieves similar historical reviews using parallel processing for each batch,
    then calls the LLM for each review in the batch.
    Returns a dictionary with the industry as key and a list of results as value,
    along with the total cost of all LLM calls.
    """
    results = {}
    total_cost = 0.0
    if not new_reviews:
        return results, total_cost

    industry = new_reviews[0].get("industry", "unknown")
    logger.info("Processing industry: %s", industry)
    retriever = industry_vectorstores.get(industry)
    if not retriever:
        logger.warning("No vector store found for industry '%s'.", industry)
        return results, total_cost

    possible_categories = industry_categories.get(industry, [])
    results[industry] = []

    # Process reviews in batches
    # Process reviews in batches
    for i in range(0, len(new_reviews), batch_size):
        batch = new_reviews[i : i + batch_size]

        # Separate empty and non-empty reviews
        non_empty_batch = []
        for review in batch:
            if not review["text"] or not review["text"].strip():
                # Add a placeholder result for empty reviews
                results[industry].append(
                    {
                        "NO": review.get("NO", None),
                        "new_review": "",
                        "similar_reviews": "",
                        "categories": ["N/A"],
                        "summary": "No review provided",
                        "cost": 0.0,
                    }
                )
            else:
                non_empty_batch.append(review)

        # If there are no non-empty reviews in this batch, skip LLM calls.
        if not non_empty_batch:
            continue

        # Use parallel retrieval to get similar reviews for the non-empty batch
        similar_reviews_dict = retrieve_similar_reviews_parallel(
            retriever, non_empty_batch
        )

        # Prepare inputs for each non-empty review in the batch
        batch_inputs = []
        for review in non_empty_batch:
            similar_reviews_str = similar_reviews_dict.get(review.get("NO", None), "")
            batch_inputs.append(
                {
                    "new_review": review["text"],
                    "similar_reviews": similar_reviews_str,
                    "categories": str(possible_categories),
                }
            )

        # Process non-empty reviews by calling the LLM
        with get_openai_callback() as cb:
            batch_results = [chain.invoke(input_data) for input_data in batch_inputs]
        total_cost += cb.total_cost
        logger.info("Batch LLM call cost: $%f", cb.total_cost)

        # Parse and store results for non-empty reviews
        for j, review in enumerate(non_empty_batch):
            result_output = batch_results[j]
            if isinstance(result_output, dict) and "text" in result_output:
                result_str = result_output["text"]
            elif hasattr(result_output, "content"):
                result_str = result_output.content
            else:
                result_str = str(result_output)

            try:
                parsed_result = json.loads(result_str)
            except json.JSONDecodeError:
                logger.error("Failed to parse LLM output: %s", result_str)
                parsed_result = {
                    "categories": ["N/A"],
                    "summary": "Failed to parse LLM output.",
                }

            categories = parsed_result.get("categories", [])
            summary = parsed_result.get("summary", "")

            results[industry].append(
                {
                    "NO": review.get("NO", None),
                    "new_review": review["text"],
                    "categories": categories,
                    "summary": summary,
                    "cost": cb.total_cost / len(batch_results),
                }
            )

    return results, total_cost


async def process_reviews_in_batches_async(
    new_reviews, industry_vectorstores, batch_size=20, max_workers=20
):
    results = {}
    industry = new_reviews[0].get("industry", "unknown")
    retriever = industry_vectorstores.get(industry)
    if not retriever:
        logger.warning("No vector store found for industry '%s'.", industry)
        return results

    possible_categories = industry_categories.get(industry, [])
    results[industry] = []

    for i in range(0, len(new_reviews), batch_size):
        batch = new_reviews[i : i + batch_size]
        non_empty_batch = [r for r in batch if r["text"] and r["text"].strip()]
        if not non_empty_batch:
            continue

        # Use parallel retrieval to get similar reviews for the non-empty batch
        similar_reviews_dict = retrieve_similar_reviews_parallel(
            retriever, non_empty_batch, max_workers=max_workers
        )

        # Prepare inputs for each non-empty review in the batch
        batch_inputs = [
            {
                "new_review": review["text"],
                "similar_reviews": similar_reviews_dict.get(review.get("NO", None), ""),
                "categories": str(possible_categories),
            }
            for review in non_empty_batch
        ]

        # Wrap the chain.invoke call asynchronously using our async_invoke helper
        batch_results = await asyncio.gather(
            *(chain.ainvoke(input_data) for input_data in batch_inputs)
        )

        # Process batch_results (as in your synchronous version)
        for j, review in enumerate(non_empty_batch):
            result_output = batch_results[j]
            if isinstance(result_output, dict) and "text" in result_output:
                result_str = result_output["text"]
            elif hasattr(result_output, "content"):
                result_str = result_output.content
            else:
                result_str = str(result_output)

            try:
                parsed_result = json.loads(result_str)
            except json.JSONDecodeError:
                logger.error("Failed to parse LLM output: %s", result_str)
                parsed_result = {
                    "categories": ["N/A"],
                    "summary": "Failed to parse LLM output.",
                }

            categories = parsed_result.get("categories", [])
            summary = parsed_result.get("summary", "")
            results[industry].append(
                {
                    "NO": review.get("NO", None),
                    "new_review": review["text"],
                    "similar_reviews": similar_reviews_dict.get(
                        review.get("NO", None), ""
                    ),
                    "categories": categories,
                    "summary": summary,
                }
            )

    return results


def save_results_to_excel(results, output_path="output.xlsx"):
    """
    Saves the processed review results to an Excel file.
    Each row contains:
    - NO: Review ID
    - Comment: The original review text
    - Categories: A comma-separated string of assigned categories
    - Summary: The summarized review
    - Cost: The cost of the LLM call
    """
    all_data = []

    for industry, reviews in results.items():
        for res in reviews:
            all_data.append(
                {
                    "NO": res.get("NO", "N/A"),
                    "Comment": res.get("new_review", ""),
                    "Similar Reviews": res.get("similar_reviews", ""),
                    "Categories": ", ".join(res.get("categories", ["N/A"])),
                    "Summary": res.get("summary", "No summary available"),
                }
            )

    # Convert list to DataFrame
    df = pd.DataFrame(all_data)

    # Save DataFrame to Excel file
    df.to_excel(output_path, index=False)
    logger.info(f"Results have been saved to {output_path}")


# ---------------------------------------------------
# 5. Main Execution Flow with Argument Parsing
# ---------------------------------------------------
def main():
    total_start = time.time()
    section_times = {}  # Dictionary to store elapsed times for each section

    parser = argparse.ArgumentParser(
        description="Process Excel reviews and classify them using an LLM."
    )
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
    new_reviews = fetch_new_reviews_from_excel(
        excel_path=new_excel_path, default_industry=default_industry
    )
    section_end = time.time()
    section_times["Fetching new reviews"] = section_end - section_start
    logger.info(
        "Fetching new reviews took %.2f seconds", section_times["Fetching new reviews"]
    )

    # -------------------------------------------------------------------
    # Section 3: Process new reviews (asynchronously).
    section_start = time.time()
    print("Processing new reviews...")
    review_results = asyncio.run(
        process_reviews_in_batches_async(new_reviews, industry_vectorstores)
    )
    section_end = time.time()
    section_times["Processing new reviews"] = section_end - section_start
    logger.info(
        "Processing new reviews took %.2f seconds",
        section_times["Processing new reviews"],
    )

    # -------------------------------------------------------------------
    # Section 4: Save results to output files.
    section_start = time.time()
    with open("output.json", "w", encoding="utf-8") as f:
        json.dump(review_results, f, ensure_ascii=False, indent=4)
    save_results_to_excel(review_results, output_path="output.xlsx")
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
