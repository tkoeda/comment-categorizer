import os

MODEL = "gpt-4o-mini"

GPT_PRICING = {
    "gpt-4o-mini": {"prompt": 0.15, "completion": 0.60},
}

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")


INDEX_DIR = os.path.join(DATA_DIR, "index")
CACHE_DIR = os.path.join(DATA_DIR, "cache")
REVIEWS_DIR = os.path.join(DATA_DIR, "reviews")
NEW_DIR = os.path.join(REVIEWS_DIR, "new")
PAST_DIR = os.path.join(REVIEWS_DIR, "past")

REVIEW_FOLDER_PATHS = {
    "new": {
        "combined": os.path.join(NEW_DIR, "combined"),
        "cleaned": os.path.join(NEW_DIR, "cleaned"),
        "raw": os.path.join(NEW_DIR, "raw"),
    },
    "past": {
        "combined": os.path.join(PAST_DIR, "combined"),
        "cleaned": os.path.join(PAST_DIR, "cleaned"),
        "raw": os.path.join(PAST_DIR, "raw"),
    },
    "final": {
        "processed": os.path.join(REVIEWS_DIR, "final"),
    },
}
