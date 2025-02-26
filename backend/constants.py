import os

MODEL = "gpt-4o-mini"

GPT_PRICING = {
    "gpt-4o-mini": {"prompt": 0.15, "completion": 0.60},
}

INDUSTRY_CATEGORIES = {
    "hotel": ["部屋", "食事", "施設", "スタッフ", "フロント", "サービス", "その他"],
    "processed_hotel": [
        "部屋",
        "食事",
        "施設",
        "スタッフ",
        "フロント",
        "サービス",
        "その他",
    ],
    "restaurant": ["料理の質", "サービス", "雰囲気"],
}

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
