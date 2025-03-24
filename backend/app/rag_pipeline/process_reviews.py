import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List

from tqdm.asyncio import tqdm

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


retrieval_durations = []


@dataclass
class ProcessReviewsResult:
    results: List[Dict[str, Any]]
    retrieval_durations: List[float]
    llm: Any
    status_tracker: Any
    avg_length: float


@dataclass
class StatusTracker:
    num_batches_started: int = 0
    num_batches_in_progress: int = 0
    num_batches_succeeded: int = 0
    num_batches_failed: int = 0


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
                "id": review.get("id", None),
                "new_review": review["text"],
                "similar_reviews": "",
                "categories": ["N/A"],
            }

    if non_empty_items:
        indices, texts = zip(*non_empty_items)
        start_time = time.perf_counter()
        similar_reviews_list = faiss_retriever.batch_retrieve_similar_reviews(
            list(texts), top_k=3
        )
        end_time = time.perf_counter()
        duration = end_time - start_time
        retrieval_durations.append(duration)

        try:
            classification_result = await llm.classify_reviews_batch(
                list(texts), similar_reviews_list, possible_categories
            )
            logger.debug("Classification result: %s", classification_result)
        except Exception:
            logger.error("Classification failed after retries", exc_info=True)
            classification_result = {
                "results": [
                    {"review": i + 1, "categories": ["N/A"]}
                    for i in range(len(texts))
                ]
            }

        for idx, sim_reviews, res in zip(
            indices, similar_reviews_list, classification_result["results"]
        ):
            batch_results[idx] = {
                "id": batch[idx].get("id", None),
                "new_review": batch[idx]["text"],
                "similar_reviews": sim_reviews,
                "categories": res.get("categories", []),
            }

    return batch_results


async def process_batch_wrapper(
    batch,
    max_attempts,
    attempts_left,
    semaphore,
    retry_queue,
    status_tracker,
    faiss_retriever,
    llm,
    possible_categories,
):
    async with semaphore:
        status_tracker.num_batches_started += 1
        status_tracker.num_batches_in_progress += 1
        try:
            result = await process_single_batch(
                batch, faiss_retriever, llm, possible_categories
            )
            status_tracker.num_batches_succeeded += 1
            logger.debug("Batch processed successfully.")
            return result
        except Exception:
            logger.warning(
                "Batch processing failed; attempts left: %d",
                attempts_left,
                exc_info=True,
            )
            if attempts_left > 0:
                delay = 2 ** (max_attempts - attempts_left)
                await asyncio.sleep(delay)
                await retry_queue.put((batch, attempts_left - 1))
                status_tracker.num_batches_failed += 1
                return None
            else:
                logger.error(
                    "Batch failed after maximum attempts; returning default result"
                )
                status_tracker.num_batches_failed += 1
                return [
                    {
                        "id": r.get("id", None),
                        "new_review": r["text"],
                        "similar_reviews": "",
                        "categories": ["N/A"],
                    }
                    for r in batch
                ]
        finally:
            status_tracker.num_batches_in_progress -= 1
            logger.debug(
                "Finished processing a batch. In progress: %d",
                status_tracker.num_batches_in_progress,
            )


async def print_status_periodically(status_tracker, interval=5):
    """
    Print the current status tracker every 'interval' seconds.
    This is useful for long-running jobs.
    """
    while True:
        logger.debug(
            "Current Status: Started: %d | In Progress: %d | Succeeded: %d | Failed: %d",
            status_tracker.num_batches_started,
            status_tracker.num_batches_succeeded,
            status_tracker.num_batches_failed,
        )
        await asyncio.sleep(interval)


async def process_reviews_in_batches_async(
    new_reviews,
    faiss_retriever,
    llm,
    industry,
    reviews_per_batch=20,
    max_concurrent_batches=20,
    max_attempts=3,
):
    industry_categories = [category.name for category in industry.categories]
    print(industry_categories)
    batches = [
        new_reviews[i : i + reviews_per_batch]
        for i in range(0, len(new_reviews), reviews_per_batch)
    ]

    semaphore = asyncio.Semaphore(max_concurrent_batches)
    status_tracker = StatusTracker()
    retry_queue = asyncio.Queue()

    tasks = [
        process_batch_wrapper(
            batch,
            max_attempts,
            max_attempts,
            semaphore,
            retry_queue,
            status_tracker,
            faiss_retriever,
            llm,
            industry_categories,
        )
        for batch in batches
    ]
    batch_results = await tqdm.gather(*tasks)

    while not retry_queue.empty():
        batch, attempts_left = await retry_queue.get()
        result = await process_batch_wrapper(
            batch,
            max_attempts,
            attempts_left,
            semaphore,
            retry_queue,
            status_tracker,
            faiss_retriever,
            llm,
            industry_categories,
        )
        if result is not None:
            batch_results.append(result)

    results = []
    for br in batch_results:
        if br is not None:
            results.extend(br)

    total_length = 0
    count = 0
    for review in results:
        review_text = review.get("new_review", "")
        if review_text:
            total_length += len(review_text)
            count += 1
    avg_length = total_length / count if count > 0 else 0

    return ProcessReviewsResult(
        results=results,
        retrieval_durations=retrieval_durations,
        llm=llm,
        status_tracker=status_tracker,
        avg_length=avg_length,
    )


class DummyFaissRetriever:
    def batch_retrieve_similar_reviews(self, texts, top_k=3):
        return [["Dummy similar review"] * top_k for _ in texts]


class DummyLLM:
    def __init__(self):
        self.call_count = 0

    async def classify_reviews_batch(
        self, reviews, similar_reviews_list, categories
    ):
        self.call_count += 1
        if self.call_count < 2:
            raise Exception("Simulated LLM failure")
        else:
            return {
                "results": [
                    {"review": i + 1, "categories": ["TestCategory"]}
                    for i in range(len(reviews))
                ]
            }
