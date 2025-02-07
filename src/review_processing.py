import asyncio
import json
import logging
import os

from openai import AsyncOpenAI
from tqdm import tqdm

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class OpenAILLM:
    def __init__(self, model="gpt-4o-mini-2024-07-18", temperature=0):
        self.model = model
        self.temperature = temperature
        self.client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        if not os.environ.get("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY is missing. Add it to your environment variables.")

        self.prompt_tokens = 0
        self.completion_tokens = 0

    async def classify_review(self, new_review, similar_reviews, categories):
        new_review = new_review.strip()
        similar_reviews = " ".join(similar_reviews.split())
        prompt = f"""
        新しいレビュー:  
        {new_review}

        類似レビュー:
        {similar_reviews}

        可能なカテゴリ: {categories}

        タスク:
        - 上記の新しいレビューを、提示されたカテゴリの中から適切なものを1つ以上選んで分類してください。
        - ただし、もしレビューが提示されたカテゴリ（「その他」以外）のどれにも該当しない場合は、[ "その他" ] のみを出力してください。
        - 該当するカテゴリをリスト形式で出力してください（複数選択可）。

        出力は、次のJSONフォーマットに従ってください:
        {{
            "categories": ["選ばれたカテゴリ1", "選ばれたカテゴリ2", ...]
        }}
        """
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": prompt}],
            temperature=self.temperature,
            response_format={"type": "json_object"},
        )

        self.prompt_tokens += response.usage.prompt_tokens
        self.completion_tokens += response.usage.completion_tokens

        try:
            content = response.choices[0].message.content
            return json.loads(content)
        except json.JSONDecodeError:
            return {"categories": ["N/A"]}

    def get_prompt_and_completion_tokens(self):
        return self.prompt_tokens, self.completion_tokens


async def process_reviews_in_batches_async(new_reviews, faiss_retriever, llm, industry_categories, batch_size=25):
    results = [None] * len(new_reviews)
    industry = new_reviews[0].get("industry", "unknown")
    possible_categories = industry_categories.get(industry, [])

    for i in tqdm(range(0, len(new_reviews), batch_size), desc="Processing review batches"):
        batch = new_reviews[i : i + batch_size]
        batch_results = [None] * len(batch)
        non_empty_tasks = []
        non_empty_indices = []

        for j, review in enumerate(batch):
            if review["text"] and review["text"].strip():
                non_empty_indices.append(j)
                non_empty_tasks.append(review)
            else:
                batch_results[j] = {
                    "NO": review.get("NO", None),
                    "new_review": review["text"],
                    "similar_reviews": "",
                    "categories": ["N/A"],
                }

        if non_empty_tasks:
            similar_reviews_list = faiss_retriever.batch_retrieve_similar_reviews(
                [review["text"] for review in non_empty_tasks], top_k=3
            )

            tasks = []
            for k, review in enumerate(non_empty_tasks):
                sim_reviews = similar_reviews_list[k]
                tasks.append(llm.classify_review(review["text"], "\n".join(sim_reviews), possible_categories))
            non_empty_results = await asyncio.gather(*tasks)

            for idx, result, sim_reviews in zip(non_empty_indices, non_empty_results, similar_reviews_list):
                batch_results[idx] = {
                    "NO": batch[idx].get("NO", None),
                    "new_review": batch[idx]["text"],
                    "similar_reviews": sim_reviews,
                    "categories": result.get("categories", []),
                }

        results[i : i + batch_size] = batch_results

    return results, (llm.get_prompt_and_completion_tokens())
