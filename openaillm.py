import asyncio
import json
import os

from openai import OpenAI


class OpenAILLM:
    def __init__(self, model="gpt-3.5-turbo", temperature=0):
        self.model = model
        self.temperature = temperature
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
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
            self.client.chat.completions.create,
            messages=[{"role": "user", "content": prompt}],
            model=self.model,
            temperature=self.temperature,
        )

        try:
            # Extract and parse the response
            content = response["choices"][0]["message"]["content"]
            return json.loads(content)
        except Exception as e:
            return {"categories": ["N/A"], "summary": f"Error parsing LLM response: {e}"}
