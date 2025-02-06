import asyncio
import json
import os

import openai


class OpenAILLM:
    def __init__(self, model="gpt-3.5-turbo", temperature=0):
        self.model = model
        self.temperature = temperature
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is missing. Add it to your environment variables.")

    async def classify_review(self, new_review, similar_reviews, categories):
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
            "categories": ["選ばれたカテゴリ1", "選ばれたカテゴリ2", ...],
        }}
        """

        response = await asyncio.to_thread(
            openai.ChatCompletion.create,
            model=self.model,
            messages=[{"role": "system", "content": prompt}],
            temperature=self.temperature
        )

        try:
            return json.loads(response["choices"][0]["message"]["content"])
        except json.JSONDecodeError:
            return {"categories": ["N/A"]}

async def process_reviews_in_batches_async(
    new_reviews, faiss_retriever, llm, industry_categories, batch_size=20
):
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
                    "summary": "No review text provided.",
                }
            )

        if not non_empty_batch:
            continue

        # Retrieve similar reviews
        similar_reviews_list = faiss_retriever.batch_retrieve_similar_reviews(
            [review["text"] for review in non_empty_batch], top_k=3
        )

        # Prepare async LLM calls
        tasks = []
        for j, review in enumerate(non_empty_batch):
            similar_reviews = "\n".join(
                [f"{idx+1}. {sim_review}" for idx, (sim_review, _) in enumerate(similar_reviews_list[j])]
            )
            tasks.append(
                llm.classify_review(
                    review["text"], similar_reviews, possible_categories
                )
            )

        # Run LLM tasks asynchronously
        batch_results = await asyncio.gather(*tasks)

        # Process LLM outputs
        for j, review in enumerate(non_empty_batch):
            categories = batch_results[j].get("categories", [])
            summary = batch_results[j].get("summary", "No summary available.")
            results.append(
                {
                    "NO": review.get("NO", None),
                    "new_review": review["text"],
                    "similar_reviews": similar_reviews_list[j],
                    "categories": categories,
                    "summary": summary,
                }
            )

    return results
