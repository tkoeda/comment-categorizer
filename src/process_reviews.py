import asyncio
import logging
import time


from tqdm.asyncio import tqdm

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


retrieval_durations = []


async def process_single_batch(batch, faiss_retriever, llm, possible_categories):
    """
    Process a single batch of reviews.
    Returns a list of results corresponding to the reviews in the batch.
    """
    batch_results = [None] * len(batch)
    non_empty_items = []

    for j, review in enumerate(batch):
        if review["text"] and review["text"].strip():
            non_empty_items.append((j, review["text"]))
        else:
            batch_results[j] = {
                "NO": review.get("NO", None),
                "new_review": review["text"],
                "similar_reviews": "",
                "categories": ["N/A"],
            }

    if non_empty_items:
        indices, texts = zip(*non_empty_items)
        start_time = time.perf_counter()
        similar_reviews_list = faiss_retriever.batch_retrieve_similar_reviews(list(texts), top_k=3)
        end_time = time.perf_counter()
        duration = end_time - start_time
        retrieval_durations.append(duration)
        classification_result = await llm.classify_reviews_batch(list(texts), similar_reviews_list, possible_categories)

        for idx, sim_reviews, res in zip(indices, similar_reviews_list, classification_result["results"]):
            batch_results[idx] = {
                "NO": batch[idx].get("NO", None),
                "new_review": batch[idx]["text"],
                "similar_reviews": sim_reviews,
                "categories": res.get("categories", []),
            }
    return batch_results


async def process_reviews_in_batches_async(
    new_reviews, faiss_retriever, llm, industry_categories, reviews_per_batch=10, max_concurrent_batches=10
):
    industry = new_reviews[0].get("industry", "unknown")
    possible_categories = industry_categories.get(industry, [])

    batches = [new_reviews[i : i + reviews_per_batch] for i in range(0, len(new_reviews), reviews_per_batch)]

    results = []
    semaphore = asyncio.Semaphore(max_concurrent_batches)

    async def process_batch_wrapper(batch):
        async with semaphore:
            return await process_single_batch(batch, faiss_retriever, llm, possible_categories)

    tasks = [process_batch_wrapper(batch) for batch in batches]

    batch_results = await tqdm.gather(*tasks, desc="Processing batches")

    for br in batch_results:
        results.extend(br)

    total_length = 0
    count = 0
    for result in results:
        similar_reviews = result.get("similar_reviews")
        if isinstance(similar_reviews, list):
            for review_text in similar_reviews:
                total_length += len(review_text)
                count += 1
    avg_length = total_length / count if count > 0 else 0
    print(f"Average length of similar reviews: {avg_length:.2f} characters")

    return results, (llm.get_prompt_and_completion_tokens()), retrieval_durations, avg_length
