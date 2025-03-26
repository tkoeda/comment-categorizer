import asyncio
import logging
import os
import pickle
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Optional

import faiss
import tqdm
from app.common.constants import get_user_cache_dir, get_user_index_dir
from app.models.index import Index
from app.models.industries import Industry
from app.models.users import User
from app.rag_pipeline.data_loader import fetch_historical_reviews_from_excel
from sentence_transformers import SentenceTransformer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DummyRetriever:
    def batch_retrieve_similar_reviews(self, reviews, top_k=3):
        return [[] for _ in reviews]


class FaissRetriever:
    @classmethod
    async def create(
        cls,
        industry: Industry,
        user: User,
        db: Optional[AsyncSession] = None,
        past_excel_path: Optional[str] = None,
        embeddings_model="pkshatech/GLuCoSE-base-ja-v2",
    ):
        # Create an instance with minimal initialization
        instance = cls.__new__(cls)

        # Complete the async initialization
        await instance.init_async(
            industry=industry,
            user=user,
            db=db,
            past_excel_path=past_excel_path,
            embeddings_model=embeddings_model,
        )

        return instance

    def __init__(self):
        pass

    async def init_async(
        self,
        industry: Industry,
        user: User,
        db: Optional[AsyncSession] = None,
        past_excel_path: Optional[str] = None,
        embeddings_model="pkshatech/GLuCoSE-base-ja-v2",
    ):
        self.past_excel_path = past_excel_path
        self.user = user
        self.embeddings_model_name = embeddings_model
        self.embeddings_model = SentenceTransformer(embeddings_model)
        self.industry_obj = industry
        self.industry_name = industry.name
        self.cancel_requested = False
        self.index_dir = get_user_index_dir(user.id)
        # スナップショット
        self.snapshot_dir = None
        self.snapshot_index_path = None
        self.snapshot_cache_path = None
        # if db is not None:
        #     print("Database session provided")
        # else:
        #     print("No database session provided")

        self.index_info = None

        # Perform the async database operation
        if db is not None and self.industry_obj is not None:
            logger.info(
                f"Checking for existing index in database for industry ID: {self.industry_obj.id}"
            )
            stmt = select(Index).filter(Index.industry_id == self.industry_obj.id)
            result = await db.execute(stmt)
            self.index_info = result.scalar_one_or_none()
            if self.index_info:
                logger.debug(
                    f"Found existing index record in database: {self.index_info.id}"
                )
            else:
                logger.debug("No existing index record found in database")

        if self.index_info:
            self.index_path = self.index_info.index_path
            self.cache_path = self.index_info.cached_data_path
        else:
            self.index_path = os.path.join(
                self.index_dir, f"{self.industry_name}.index"
            )
            self.cache_path = os.path.join(
                get_user_cache_dir(user.id),
                f"past_reviews_{self.industry_name}.pkl",
            )

        if os.path.exists(self.index_path) and os.path.exists(self.cache_path):
            # print(f"Index file {self.index_path} found. Loading index...")
            self._load_cached_data()
            self.index = faiss.read_index(self.index_path)
        elif past_excel_path:
            logger.debug(
                f"Index file {self.index_path} does not exist. Generating FAISS index..."
            )
            self.past_excel_path = past_excel_path
            await self.generate_index()

            if db is not None and self.industry_obj is not None:
                await self._update_index_record(db)
        else:
            raise ValueError(
                "Index does not exist and no past_excel_path provided to create it."
            )

    def _create_snapshot(self):
        """Create a snapshot of the current index and cached data if they exist"""
        if not os.path.exists(self.index_path) or not os.path.exists(
            self.cache_path
        ):
            logger.info("No existing index or cache to snapshot.")
            return False

        try:
            # Create a temporary directory for the snapshot
            self.snapshot_dir = tempfile.mkdtemp(prefix="index_snapshot_")
            self.snapshot_index_path = os.path.join(
                self.snapshot_dir, os.path.basename(self.index_path)
            )
            self.snapshot_cache_path = os.path.join(
                self.snapshot_dir, os.path.basename(self.cache_path)
            )

            # Copy the current index and cache files to the snapshot directory
            shutil.copy2(self.index_path, self.snapshot_index_path)
            shutil.copy2(self.cache_path, self.snapshot_cache_path)

            logger.info(f"Created snapshot of index in {self.snapshot_dir}")
            return True
        except Exception as e:
            logger.error(f"Failed to create snapshot: {str(e)}")
            self._cleanup_snapshot()
            return False

    def _restore_snapshot(self):
        """Restore the index and cached data from snapshot if available"""
        if not self.snapshot_dir or not os.path.exists(self.snapshot_dir):
            logger.warning("No snapshot available to restore.")
            return False

        try:
            if os.path.exists(self.snapshot_index_path) and os.path.exists(
                self.snapshot_cache_path
            ):
                # Copy the snapshot files back to the original locations
                shutil.copy2(self.snapshot_index_path, self.index_path)
                shutil.copy2(self.snapshot_cache_path, self.cache_path)

                # Reload the index and cached data
                self._load_cached_data()
                self.index = faiss.read_index(self.index_path)

                logger.info(f"Restored index from snapshot {self.snapshot_dir}")
                return True
            else:
                logger.warning("Snapshot files are incomplete.")
                return False
        except Exception as e:
            logger.error(f"Failed to restore snapshot: {str(e)}")
            return False
        finally:
            self._cleanup_snapshot()

    def _cleanup_snapshot(self):
        """Clean up the snapshot directory"""
        if self.snapshot_dir and os.path.exists(self.snapshot_dir):
            try:
                shutil.rmtree(self.snapshot_dir)
                logger.info(f"Cleaned up snapshot directory {self.snapshot_dir}")
            except Exception as e:
                logger.error(f"Failed to clean up snapshot directory: {str(e)}")

            self.snapshot_dir = None
            self.snapshot_index_path = None
            self.snapshot_cache_path = None

    def cancel(self):
        self.cancel_requested = True
        if hasattr(self, "_restore_snapshot"):
            logger.info(
                "Cancellation requested, will restore from snapshot if available."
            )

    def _load_cached_data(self):
        """Load cached document data from disk"""
        with open(self.cache_path, "rb") as f:
            self.documents = pickle.load(f)
        self.texts = [f"passage: {doc.page_content}" for doc in self.documents]

    async def _update_index_record(self, db: AsyncSession):
        """Create or update the index record in the database"""

        now = datetime.now(timezone.utc)

        if not self.index_info:
            self.index_info = Index(
                industry_id=self.industry_obj.id,
                user_id=self.user.id,
                index_path=self.index_path,
                cached_data_path=self.cache_path,
                embeddings_model=self.embeddings_model_name,
                reviews_included=len(self.documents),
                created_at=now,
                updated_at=now,
            )
            db.add(self.index_info)
        else:
            self.index_info.index_path = self.index_path
            self.index_info.cached_data_path = self.cache_path
            self.index_info.embeddings_model = self.embeddings_model_name
            self.index_info.reviews_included = len(self.documents)
            self.index_info.updated_at = now

        # print("Saving index record to database...")
        await db.commit()
        await db.refresh(self.index_info)

    async def generate_index(self):
        """Asynchronous wrapper for index generation"""
        loop = asyncio.get_running_loop()
        index_success = False
        temp_dir = tempfile.mkdtemp(prefix="temp_index_")
        original_index_path = self.index_path
        original_cache_path = self.cache_path

        # Use temporary paths during generation
        temp_index_path = os.path.join(temp_dir, os.path.basename(self.index_path))
        temp_cache_path = os.path.join(temp_dir, os.path.basename(self.cache_path))
        self.index_path = temp_index_path
        self.cache_path = temp_cache_path
        # Run CPU-intensive work in a ThreadPoolExecutor
        with ThreadPoolExecutor() as executor:
            try:
                index_success = await loop.run_in_executor(
                    executor, self._generate_index_sync
                )
                if index_success:
                    shutil.copy2(temp_index_path, original_index_path)
                    shutil.copy2(temp_cache_path, original_cache_path)
                    self.index_path = original_index_path
                    self.cache_path = original_cache_path

                return index_success
            except Exception as e:
                logger.error(f"Failed to generate index: {str(e)}")
                raise e

    def _generate_index_sync(self):
        """Synchronous version of generate_index to run in a thread"""
        try:
            self.documents = fetch_historical_reviews_from_excel(
                self.past_excel_path, self.industry_name
            )
            self.texts = [f"passage: {doc.page_content}" for doc in self.documents]

            embeddings = self.embeddings_model.encode(
                self.texts, convert_to_numpy=True
            )

            dimension = embeddings.shape[1]

            index = faiss.IndexFlatL2(dimension)
            batch_size = 100
            total_embeddings = embeddings.shape[0]
            for i in tqdm.tqdm(range(0, total_embeddings, batch_size)):
                if self.cancel_requested:
                    logger.info("Index generation cancelled.")
                    return
                batch = embeddings[i : i + batch_size]
                index.add(batch)
            if not self.cancel_requested:
                # Create parent directories
                os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
                os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)

                # Save index file
                faiss.write_index(index, self.index_path)
                logger.info(f"Generated and saved FAISS index at: {self.index_path}")

                # Save cache file - using the exact path stored in self.cache_path
                with open(self.cache_path, "wb") as f:
                    pickle.dump(self.documents, f)
                logger.info(f"Cached past reviews at: {self.cache_path}")

                # Verify files were created
                if not os.path.exists(self.index_path):
                    logger.error(
                        f"Index file was not created properly at: {self.index_path}"
                    )
                    return False

                if not os.path.exists(self.cache_path):
                    logger.error(
                        f"Cache file was not created properly at: {self.cache_path}"
                    )
                    return False

                self.index = index
                return True
            else:
                return False
        except Exception as e:
            logger.error(f"Error in _generate_index_sync: {str(e)}")
            raise e

    async def update_index(
        self,
        new_past_excel_path: str,
        db: Optional[AsyncSession] = None,
        replace: bool = False,
    ):
        """
        Update the index with new past reviews.
        """
        snapshot_created = self._create_snapshot()
        loop = asyncio.get_running_loop()
        update_success = False

        try:
            # Run CPU-intensive work in a ThreadPoolExecutor
            with ThreadPoolExecutor() as executor:
                update_success = await loop.run_in_executor(
                    executor, self._update_index_sync, new_past_excel_path, replace
                )

            # Only update the database record after the CPU-intensive work is done
            if update_success and db is not None and self.industry_obj is not None:
                await self._update_index_record(db)

            return update_success
        except Exception as e:
            logger.error(f"Failed to update index: {str(e)}")
            if snapshot_created:
                self._restore_snapshot()
            raise e

    def _update_index_sync(self, new_past_excel_path: str, replace: bool = False):
        """Synchronous version of update_index to run in a thread"""
        try:
            new_documents = fetch_historical_reviews_from_excel(
                new_past_excel_path, self.industry_name
            )
            new_texts = [f"passage: {doc.page_content}" for doc in new_documents]

            new_embeddings = self.embeddings_model.encode(
                new_texts, convert_to_numpy=True
            )

            if replace or not os.path.exists(self.index_path):
                dimension = new_embeddings.shape[1]
                self.index = faiss.IndexFlatL2(dimension)
                self.documents = new_documents
                self.texts = new_texts
            else:
                if not hasattr(self, "documents") or not hasattr(self, "texts"):
                    self._load_cached_data()
                    self.index = faiss.read_index(self.index_path)

                self.documents.extend(new_documents)
                self.texts.extend(new_texts)

            batch_size = 100
            total_embeddings = new_embeddings.shape[0]
            for i in tqdm.tqdm(range(0, total_embeddings, batch_size)):
                if self.cancel_requested:
                    logger.info("Index generation cancelled.")
                    return
                batch = new_embeddings[i : i + batch_size]
                self.index.add(batch)
            if not self.cancel_requested:
                faiss.write_index(self.index, self.index_path)
                with open(self.cache_path, "wb") as f:
                    pickle.dump(self.documents, f)

                logger.info(
                    f"{'Replaced' if replace else 'Updated'} FAISS index at: {self.index_path}"
                )
                logger.info(f"Total documents in index: {len(self.documents)}")
                self._cleanup_snapshot()
                return True
            else:
                return False
        except Exception as e:
            logger.error(f"Error in _update_index_sync: {str(e)}")
            if hasattr(self, "_restore_snapshot"):
                self._restore_snapshot()
            raise e

    def batch_retrieve_similar_reviews(self, reviews, top_k=3):
        query_texts = [f"query: {review}" for review in reviews]
        query_vectors = self.embeddings_model.encode(
            query_texts, convert_to_numpy=True
        )
        _, indices = self.index.search(query_vectors, top_k)
        batch_results = []
        for i in range(len(indices)):
            review_results = []
            for num, idx in enumerate(indices[i], start=1):
                if idx != -1:
                    text = self.texts[int(idx)]
                    clean_text = text.removeprefix("passage: ").strip()
                    categories = self.documents[int(idx)].metadata.get(
                        "categories", []
                    )
                    if categories:
                        formatted = f"{num}. {clean_text} (カテゴリー: {', '.join(categories)})"
                    else:
                        formatted = f"{num}. {clean_text}"
                    review_results.append(formatted)
            batch_results.append(review_results)
        return batch_results
