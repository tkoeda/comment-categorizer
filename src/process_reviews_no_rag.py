import asyncio
import logging


from tqdm.asyncio import tqdm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def process_single_batch_no_rag(batch, llm, possible_categories):
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
                "categories": ["N/A"],
            }
    if non_empty_items:
        indices, texts = zip(*non_empty_items)
        classification_result = await llm.classify_reviews_batch_no_rag(list(texts), possible_categories)

        for idx, res in zip(indices, classification_result["results"]):
            batch_results[idx] = {
                "NO": batch[idx].get("NO", None),
                "new_review": batch[idx]["text"],
                "categories": res.get("categories", []),
            }
    return batch_results


async def process_reviews_in_batches_async_no_rag(
    new_reviews, llm, industry_categories, reviews_per_batch=10, max_concurrent_batches=10
):
    industry = new_reviews[0].get("industry", "unknown")
    possible_categories = industry_categories.get(industry, [])

    batches = [new_reviews[i : i + reviews_per_batch] for i in range(0, len(new_reviews), reviews_per_batch)]

    results = []
    semaphore = asyncio.Semaphore(max_concurrent_batches)

    async def process_batch_wrapper(batch):
        async with semaphore:
            return await process_single_batch_no_rag(batch, llm, possible_categories)

    tasks = [process_batch_wrapper(batch) for batch in batches]
    batch_results = await tqdm.gather(*tasks, desc="Processing batches")

    for br in batch_results:
        results.extend(br)

    print(len(results))

    return results, (llm.get_prompt_and_completion_tokens())
