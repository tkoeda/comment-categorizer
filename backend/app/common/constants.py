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


# Function to get user-specific directories
def get_user_dirs(user_id):
    """Get user-specific directories based on user_id"""
    # Main user directory
    user_dir = os.path.join(REVIEWS_DIR, f"user_{user_id}")

    # User-specific directories for new and past reviews
    user_new_dir = os.path.join(user_dir, "new")
    user_past_dir = os.path.join(user_dir, "past")

    # Return dictionary with all user-specific paths
    return {
        "base": user_dir,
        "new": {
            "base": user_new_dir,
            "combined": os.path.join(user_new_dir, "combined"),
            "cleaned": os.path.join(user_new_dir, "cleaned"),
            "raw": os.path.join(user_new_dir, "raw"),
        },
        "past": {
            "base": user_past_dir,
            "combined": os.path.join(user_past_dir, "combined"),
            "cleaned": os.path.join(user_past_dir, "cleaned"),
            "raw": os.path.join(user_past_dir, "raw"),
        },
        "final": {
            "processed": os.path.join(user_dir, "final"),
        },
    }


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


# User-specific index and cache directories
def get_user_index_dir(user_id):
    user_index_dir = os.path.join(INDEX_DIR, f"user_{user_id}")
    os.makedirs(user_index_dir, exist_ok=True)
    return user_index_dir


def get_user_cache_dir(user_id):
    user_cache_dir = os.path.join(CACHE_DIR, f"user_{user_id}")
    os.makedirs(user_cache_dir, exist_ok=True)
    return user_cache_dir
