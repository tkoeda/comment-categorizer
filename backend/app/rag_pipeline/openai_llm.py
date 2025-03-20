import asyncio
import json
import logging

from app.utils.calc_utils import time_to_seconds
from app.utils.console_utils import display_rate_limit_progress
from app.utils.prompts_utils import append_prompt_to_json
from openai import AsyncOpenAI
from rich.console import Console
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)
console = Console()


class OpenAILLM:
    def __init__(
        self, api_key=None, model="gpt-4o-mini-2024-07-18", temperature=0.5
    ):
        self.model = model
        self.temperature = temperature
        self.client = AsyncOpenAI(api_key=api_key)
        self.api_call_durations = []
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0
        self.api_calls = 0

    async def classify_reviews_batch(
        self, reviews, similar_reviews_list, categories
    ):
        """
        Classify multiple reviews (and their corresponding similar reviews) in one API call.
        Expects:
          - reviews: list of review texts (each review is 2-3 sentences)
          - similar_reviews_list: list of similar reviews (as strings) for each review, in the same order
          - categories: list of allowed categories
        Returns a JSON object with a "results" key containing a list of classification objects.
        """
        prompt = self._build_prompt(reviews, similar_reviews_list, categories)
        # append_prompt_to_json(prompt, output_file="prompts.json")
        chat_params = {
            "model": self.model,
            "messages": [{"role": "system", "content": prompt}],
            "temperature": self.temperature,
            "n": 1,
            "response_format": {
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
                                        "review": {
                                            "type": "number",
                                            "description": "The review identifier.",
                                        },
                                        "categories": {
                                            "type": "array",
                                            "description": "The selected categories for the review.",
                                            "items": {
                                                "type": "string",
                                                "description": "A selected category.",
                                            },
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
        }

        try:
            response = await self._call_api_with_retry(chat_params)

            try:
                content = response.choices[0].message.content
                return json.loads(content)
            except json.JSONDecodeError:
                logger.error("JSON decoding failed. Raw response: %s", response)
                return self._default_response(len(reviews))
        except Exception as e:
            logger.error("API call failed after retries: %s", e)
            return self._default_response(len(reviews))

    def _build_prompt(self, reviews, similar_reviews_list, categories) -> str:
        """Helper to construct the classification prompt."""
        prompt_lines = []

        rag_mode = similar_reviews_list and any(similar_reviews_list)

        if rag_mode:
            prompt_lines.append(
                "以下のレビューを個別に分類してください。それぞれのレビューには類似レビューも添付されています。\n\n"
            )
        else:
            prompt_lines.append("以下のレビューを個別に分類してください。")
        prompt_lines.append("")

        for idx, review in enumerate(reviews, 1):
            prompt_lines.append(f"レビュー {idx}:")
            prompt_lines.append(f"新しいレビュー: {review.strip()}")
            if rag_mode:
                if (
                    idx - 1 < len(similar_reviews_list)
                    and similar_reviews_list[idx - 1]
                ):
                    sim_text = " ".join(similar_reviews_list[idx - 1])
                else:
                    sim_text = "なし"
                prompt_lines.append(f"類似レビュー: {sim_text}")
            prompt_lines.append("")
        prompt_lines.append(f"可能なカテゴリ: {categories}")
        prompt_lines.append("")
        prompt_lines.append("タスク:")
        prompt_lines.append(
            "- 各レビューに対して、最も適切なカテゴリを1つ以上選び、リスト形式で出力してください。"
        )
        prompt_lines.append(
            "- どのカテゴリにも該当しない場合は、['その他']としてください。"
        )

        return "\n".join(prompt_lines)

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(4),
        retry=retry_if_exception_type(Exception),
    )
    async def _call_api_with_retry(self, chat_params: dict):
        """
        Calls the API while applying rate limiting and retry logic.
        """
        raw_response = await self.client.chat.completions.with_raw_response.create(
            **chat_params
        )

        response = raw_response.parse()

        headers = raw_response.headers

        self.api_call_durations.append(int(headers.get("openai-processing-ms", 0)))
        self.total_prompt_tokens += response.usage.prompt_tokens
        self.total_completion_tokens += response.usage.completion_tokens
        self.total_tokens += response.usage.total_tokens
        self.api_calls += 1

        display_rate_limit_progress(headers)
        reset_time = time_to_seconds(headers.get("x-ratelimit-reset-tokens", 1))
        remaining_tokens = int(headers.get("x-ratelimit-remaining-tokens", 0))
        if remaining_tokens < 4000:
            console.print(
                f"[red]Waiting {reset_time} seconds for token reset...[/red]"
            )
            await asyncio.sleep(reset_time)

        return response

    def _default_response(self, num_reviews: int) -> dict:
        """Return a default classification response."""
        return {
            "results": [
                {"review": i + 1, "categories": ["N/A"]} for i in range(num_reviews)
            ]
        }

    def get_average_prompt_tokens(self):
        if self.api_calls > 0:
            return self.total_prompt_tokens / self.api_calls
        return 0

    def get_average_completion_tokens(self):
        """
        Returns the average number of completion tokens per API call.
        """
        if self.api_calls > 0:
            return self.total_completion_tokens / self.api_calls
        return 0

    def get_average_tokens(self):
        if self.api_calls > 0:
            return (self.total_tokens) / self.api_calls
        return 0
