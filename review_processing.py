import asyncio
import json
import logging
import os

from openai import AsyncOpenAI

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class OpenAILLM:
    def __init__(self, model="gpt-3.5-turbo", temperature=0):
        self.model = model
        self.temperature = temperature
        # Instantiate the async client with your API key.
        self.client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        if not os.environ.get("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY is missing. Add it to your environment variables.")
        
        self.total_tokens = 0

    async def classify_review(self, new_review, similar_reviews, categories):
        new_review = new_review.strip()
        similar_reviews = " ".join(similar_reviews.split())  # Remove extra spaces within similar reviews

        prompt = f"""
        新しいレビュー:  
        "{new_review}"
        
        類似レビュー:
        {similar_reviews}
        
        可能なカテゴリ: {categories}

        タスク:
        - 上記の新しいレビューを、提示されたカテゴリの中から最も適切なもの **1つ以上** に分類してください。
        - 該当するカテゴリを **リスト形式** で出力してください（複数選択可）。

        出力は、次のJSONフォーマットに従ってください:
        {{
            "categories": ["選ばれたカテゴリ1", "選ばれたカテゴリ2", ...]
        }}
        """
        # Use the async client's API call directly.
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": prompt}],
            temperature=self.temperature,
            response_format={"type": "json_object"},
        )
        
        self.total_tokens += response.usage.total_tokens
        
        try:
            content = response.choices[0].message.content
            return json.loads(content)
        except json.JSONDecodeError:
            return {"categories": ["N/A"]}
        
    def get_total_tokens(self):
        return self.total_tokens


async def process_reviews_in_batches_async(new_reviews, faiss_retriever, llm, industry_categories, batch_size=20):
    results = []
    industry = new_reviews[0].get("industry", "unknown")
    possible_categories = industry_categories.get(industry, [])

    for i in range(0, len(new_reviews), batch_size):
        batch = new_reviews[i : i + batch_size]
        non_empty_batch = [r for r in batch if r["text"] and r["text"].strip()]
        empty_reviews = [r for r in batch if not r["text"] or not r["text"].strip()]

        for review in empty_reviews:
            results.append(
                {
                    "NO": review.get("NO", None),
                    "new_review": review["text"],
                    "similar_reviews": "",
                    "categories": ["N/A"],
                }
            )

        if not non_empty_batch:
            continue

        # Retrieve similar reviews
        similar_reviews_list = faiss_retriever.batch_retrieve_similar_reviews(
            [review["text"] for review in non_empty_batch], top_k=3
        )

        print("similar_reviews_list", similar_reviews_list)

        # Prepare async LLM calls
        tasks = []
        for j, review in enumerate(non_empty_batch):
            similar_reviews = [sim_review for sim_review in similar_reviews_list[j]]
            tasks.append(llm.classify_review(review["text"], "\n".join(similar_reviews), possible_categories))

        # Run LLM tasks asynchronously
        batch_results = await asyncio.gather(*tasks)

        # Process LLM outputs
        for j, review in enumerate(non_empty_batch):
            categories = batch_results[j].get("categories", [])
            results.append(
                {
                    "NO": review.get("NO", None),
                    "new_review": review["text"],
                    "similar_reviews": similar_reviews_list[j],
                    "categories": categories,
                }
            )
            
    logger.info(f"Total tokens used: {llm.get_total_tokens()}")

    return results
