import asyncio
import logging
import os
import shutil

from app.constants import CACHE_DIR, INDEX_DIR, REVIEW_FOLDER_PATHS
from app.models.industries import Industry
from app.models.reviews import Review
from sqlalchemy import event

logger = logging.getLogger(__name__)


def register_event_listeners(app=None):
    @event.listens_for(Review, "after_delete")
    def delete_review_file(mapper, connection, target):
        """Remove the file associated with a deleted review."""
        file_path = target.file_path
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"Successfully deleted file: {file_path}")
            except Exception as e:
                logger.error(f"Error deleting file {file_path}: {e}")

    @event.listens_for(Industry, "after_delete")
    def delete_industry_folder(mapper, connection, target):
        """Delete the folder associated with a deleted industry."""
        review_types_with_stages = {
            "new": ["combined", "cleaned", "raw"],
            "past": ["combined", "cleaned", "raw"],
            "final": ["processed"],
        }

        for review_type, stages in review_types_with_stages.items():
            for stage in stages:
                folder_path = REVIEW_FOLDER_PATHS.get(review_type, {}).get(
                    stage, None
                )

                if folder_path:
                    industry_folder_path = os.path.join(folder_path, target.name)
                    print(f"Checking folder: {industry_folder_path}")

                    if os.path.exists(industry_folder_path):
                        try:
                            for file_name in os.listdir(industry_folder_path):
                                file_path = os.path.join(
                                    industry_folder_path, file_name
                                )
                                if os.path.isfile(file_path):
                                    os.remove(file_path)
                            shutil.rmtree(industry_folder_path)
                            logger.info(
                                f"Successfully deleted folder and contents: {industry_folder_path}"
                            )
                        except Exception as e:
                            logger.error(
                                f"Error deleting folder {industry_folder_path}: {e}"
                            )
                    else:
                        logger.warning(f"Folder not found: {industry_folder_path}")

    @event.listens_for(Industry, "after_delete")
    def delete_index(mapper, connection, target):
        """Delete the index associated with a deleted industry."""
        industry_name = target.name
        index_path = os.path.join(INDEX_DIR, f"{industry_name}.index")
        if os.path.exists(index_path):
            try:
                os.remove(index_path)
                logger.info(f"Successfully deleted index: {index_path}")
            except Exception as e:
                logger.error(f"Error deleting index {index_path}: {e}")

    @event.listens_for(Industry, "after_delete")
    def delete_cache(mapper, connection, target):
        """Delete the cache associated with a deleted industry."""
        industry_name = target.name
        cache_path = os.path.join(CACHE_DIR, f"past_reviews_{industry_name}.pkl")
        if os.path.exists(cache_path):
            try:
                os.remove(cache_path)
                logger.info(f"Successfully deleted cache: {cache_path}")
            except Exception as e:
                logger.error(f"Error deleting cache {cache_path}: {e}")
