import os
import time
import json
from openai import AsyncOpenAI
from datetime import datetime, timezone, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def store_prompt(prompt, filepath="prompt_log.txt"):
    jst = timezone(timedelta(hours=9))
    timestamp = datetime.now(jst).isoformat()
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(f"Timestamp: {timestamp}\n")
        f.write(prompt)
        f.write("\n" + "=" * 80 + "\n")


class OpenAILLM:
    def __init__(self, model="gpt-4o-mini-2024-07-18", temperature=0):
        self.model = model
        self.temperature = temperature
        self.client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.api_call_durations = []
        self.prompt_tokens = 0
        self.completion_tokens = 0

    async def classify_reviews_batch_no_rag(self, reviews, categories):
        """
        Classify reviews without RAG.
        """
        prompt = "以下のレビューを分類してください。\n\n"
        for idx, review in enumerate(reviews, 1):
            prompt += f"レビュー {idx}: {review.strip()}\n\n"
        prompt += f"可能なカテゴリ: {categories}\n\n"
        prompt += (
            "タスク:\n"
            "- 上記の各レビューについて、提示されたカテゴリの中から適切なものを1つ以上選んで分類してください。\n"
            '- もしレビューが提示されたカテゴリ（「その他」以外）のどれにも該当しない場合は、[ "その他" ] のみを出力してください。\n'
            "- 該当するカテゴリをリスト形式で出力してください（複数選択可）。\n\n"
        )

        store_prompt(prompt)

        start_api = time.perf_counter()
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": prompt}],
            temperature=self.temperature,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "task_results",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "results": {
                                "type": "array",
                                "description": "A list of reviews with their associated categories.",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "review": {"type": "number", "description": "The review identifier."},
                                        "categories": {
                                            "type": "array",
                                            "description": "The selected categories for the review.",
                                            "items": {"type": "string", "description": "A selected category."},
                                        },
                                    },
                                    "required": ["review", "categories"],
                                    "additionalProperties": False,
                                },
                            }
                        },
                        "required": ["results"],
                        "additionalProperties": False,
                    },
                    "strict": True,
                },
            },
        )

        end_api = time.perf_counter()

        self.api_call_durations.append(end_api - start_api)
        self.prompt_tokens += response.usage.prompt_tokens
        self.completion_tokens += response.usage.completion_tokens

        try:
            content = response.choices[0].message.content
            return json.loads(content)
        except json.JSONDecodeError:
            return {"results": [{"review": i + 1, "categories": ["N/A"]} for i in range(len(reviews))]}

    async def classify_reviews_batch(self, reviews, similar_reviews_list, categories):
        """
        Classify multiple reviews (and their corresponding similar reviews) in one API call.
        Expects:
          - reviews: list of review texts (each review is 2-3 sentences)
          - similar_reviews_list: list of similar reviews (as strings) for each review, in the same order
          - categories: list of allowed categories
        Returns a JSON object with a "results" key containing a list of classification objects.
        """
        prompt = "以下のレビューを個別に分類してください。それぞれのレビューには類似レビューも添付されています。\n\n"
        for idx, (review, sim_reviews) in enumerate(zip(reviews, similar_reviews_list), 1):
            prompt += f"レビュー {idx}:\n"
            prompt += f"新しいレビュー: {review.strip()}\n"
            prompt += f"類似レビュー: {' '.join(sim_reviews)}\n\n"
        prompt += f"可能なカテゴリ: {categories}\n\n"
        prompt += (
            "タスク:\n"
            "- 上記の各レビューについて、提示されたカテゴリの中から適切なものを1つ以上選んで分類してください。\n"
            '- もしレビューが提示されたカテゴリ（「その他」以外）のどれにも該当しない場合は、[ "その他" ] のみを出力してください。\n'
            "- 該当するカテゴリをリスト形式で出力してください（複数選択可）。\n\n"
        )

        # store_prompt(prompt)
        start_api = time.perf_counter()
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": prompt}],
            temperature=self.temperature,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "task_results",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "results": {
                                "type": "array",
                                "description": "A list of reviews with their associated categories.",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "review": {"type": "number", "description": "The review identifier."},
                                        "categories": {
                                            "type": "array",
                                            "description": "The selected categories for the review.",
                                            "items": {"type": "string", "description": "A selected category."},
                                        },
                                    },
                                    "required": ["review", "categories"],
                                    "additionalProperties": False,
                                },
                            }
                        },
                        "required": ["results"],
                        "additionalProperties": False,
                    },
                    "strict": True,
                },
            },
        )
        end_api = time.perf_counter()
        api_duration = end_api - start_api
        self.api_call_durations.append(api_duration)

        self.prompt_tokens += response.usage.prompt_tokens
        self.completion_tokens += response.usage.completion_tokens

        try:
            content = response.choices[0].message.content
            return json.loads(content)
        except json.JSONDecodeError:
            return {"results": [{"review": i + 1, "categories": ["N/A"]} for i in range(len(reviews))]}

    def get_prompt_and_completion_tokens(self):
        return self.prompt_tokens, self.completion_tokens
