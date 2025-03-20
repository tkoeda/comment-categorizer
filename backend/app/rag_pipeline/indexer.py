import asyncio
import logging
import os
import pickle
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Optional

import faiss
from app.constants import CACHE_DIR, INDEX_DIR
from app.models.index import Index
from app.models.industries import Industry
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
        db: Optional[AsyncSession] = None,
        past_excel_path: Optional[str] = None,
        embeddings_model="pkshatech/GLuCoSE-base-ja-v2",
        index_dir=INDEX_DIR,
    ):
        # Create an instance with minimal initialization
        instance = cls.__new__(cls)

        # Complete the async initialization
        await instance.init_async(
            industry, db, past_excel_path, embeddings_model, index_dir
        )

        return instance

    def __init__(self):
        pass

    async def init_async(
        self,
        industry: Industry,
        db: Optional[AsyncSession] = None,
        past_excel_path: Optional[str] = None,
        embeddings_model="pkshatech/GLuCoSE-base-ja-v2",
        index_dir=INDEX_DIR,
    ):
        self.past_excel_path = past_excel_path
        self.index_dir = index_dir
        self.embeddings_model_name = embeddings_model
        self.embeddings_model = SentenceTransformer(embeddings_model)
        self.industry_obj = industry
        self.industry_name = industry.name

        # if db is not None:
        #     print("Database session provided")
        # else:
        #     print("No database session provided")

        self.index_info = None

        # Perform the async database operation
        if db is not None and self.industry_obj is not None:
            print(
                f"Checking for existing index in database for industry ID: {self.industry_obj.id}"
            )
            stmt = select(Index).filter(Index.industry_id == self.industry_obj.id)
            result = await db.execute(stmt)
            self.index_info = result.scalar_one_or_none()
            # if self.index_info:
            #     print(
            #         f"Found existing index record in database: {self.index_info.id}"
            #     )
            # else:
            #     print("No existing index record found in database")

        if self.index_info:
            self.index_path = self.index_info.index_path
            self.cache_path = self.index_info.cached_data_path
        else:
            self.index_path = os.path.join(
                self.index_dir, f"{self.industry_name}.index"
            )
            self.cache_path = os.path.join(
                CACHE_DIR, f"past_reviews_{self.industry_name}.pkl"
            )

        if os.path.exists(self.index_path) and os.path.exists(self.cache_path):
            # print(f"Index file {self.index_path} found. Loading index...")
            self._load_cached_data()
            self.index = faiss.read_index(self.index_path)
        elif past_excel_path:
            # print(
            #     f"Index file {self.index_path} does not exist. Generating FAISS index..."
            # )
            self.past_excel_path = past_excel_path
            await self.generate_index()

            if db is not None and self.industry_obj is not None:
                await self._update_index_record(db)
        else:
            raise ValueError(
                "Index does not exist and no past_excel_path provided to create it."
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

    async def generate_index(self):
        """Asynchronous wrapper for index generation"""
        loop = asyncio.get_running_loop()

        # Run CPU-intensive work in a ThreadPoolExecutor
        with ThreadPoolExecutor() as executor:
            await loop.run_in_executor(executor, self._generate_index_sync)

    def _generate_index_sync(self):
        """Synchronous version of generate_index to run in a thread"""
        self.documents = fetch_historical_reviews_from_excel(
            self.past_excel_path, self.industry_name
        )
        self.texts = [f"passage: {doc.page_content}" for doc in self.documents]

        embeddings = self.embeddings_model.encode(self.texts, convert_to_numpy=True)

        dimension = embeddings.shape[1]

        index = faiss.IndexFlatL2(dimension)
        batch_size = 100
        total_embeddings = embeddings.shape[0]
        for i in range(0, total_embeddings, batch_size):
            batch = embeddings[i : i + batch_size]
            index.add(batch)

        os.makedirs(self.index_dir, exist_ok=True)
        faiss.write_index(index, self.index_path)
        logger.info(f"Generated and saved FAISS index at: {self.index_path}")

        os.makedirs(CACHE_DIR, exist_ok=True)
        cache_file = os.path.join(
            CACHE_DIR, f"past_reviews_{self.industry_name}.pkl"
        )
        with open(cache_file, "wb") as f:
            pickle.dump(self.documents, f)
        logger.info(f"Cached past reviews at: {cache_file}")

        self.index = index

    async def update_index(
        self,
        new_past_excel_path: str,
        db: Optional[AsyncSession] = None,
        replace: bool = False,
    ):
        """
        Update the index with new past reviews.
        """
        loop = asyncio.get_running_loop()

        # Run CPU-intensive work in a ThreadPoolExecutor
        with ThreadPoolExecutor() as executor:
            await loop.run_in_executor(
                executor, self._update_index_sync, new_past_excel_path, replace
            )

        # Only update the database record after the CPU-intensive work is done
        if db is not None and self.industry_obj is not None:
            await self._update_index_record(db)

    def _update_index_sync(self, new_past_excel_path: str, replace: bool = False):
        """Synchronous version of update_index to run in a thread"""
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
        for i in range(0, total_embeddings, batch_size):
            batch = new_embeddings[i : i + batch_size]
            self.index.add(batch)

        faiss.write_index(self.index, self.index_path)
        with open(self.cache_path, "wb") as f:
            pickle.dump(self.documents, f)

        logger.info(
            f"{'Replaced' if replace else 'Updated'} FAISS index at: {self.index_path}"
        )
        logger.info(f"Total documents in index: {len(self.documents)}")

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
