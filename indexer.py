import asyncio
import logging
import os
import pickle

from langchain_community.vectorstores import FAISS

from data_loader import fetch_historical_reviews_from_excel

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

CACHE_DIR = "cache"
INDEX_DIR_PREFIX = "faiss_index_"


class ReviewIndexer:
    def __init__(self, past_excel_path, industry, embeddings, cache_dir=CACHE_DIR, index_dir_prefix=INDEX_DIR_PREFIX):
        self.past_excel_path = past_excel_path
        self.industry = industry
        self.embeddings = embeddings
        self.cache_dir = cache_dir
        self.index_dir = f"{index_dir_prefix}{industry}"

    def load_reviews(self):
        # Create cache directory if it doesn't exist
        os.makedirs(self.cache_dir, exist_ok=True)
        cache_path = os.path.join(self.cache_dir, f"past_reviews_{self.industry}.pkl")
        if os.path.exists(cache_path):
            logger.info("Loading past reviews from cache for industry: %s", self.industry)
            with open(cache_path, "rb") as f:
                documents = pickle.load(f)
        else:
            logger.info("Cache not found for industry %s. Fetching from Excel...", self.industry)
            documents = fetch_historical_reviews_from_excel(self.past_excel_path, self.industry)
            with open(cache_path, "wb") as f:
                pickle.dump(documents, f)
        return documents

    def load_vectorstore(self):
        documents = self.load_reviews()
        # Check if the index directory exists
        if os.path.exists(self.index_dir):
            vectorstore = FAISS.load_local(self.index_dir, self.embeddings, allow_dangerous_deserialization=True)
            logger.info("Loaded FAISS vector store for industry '%s' from disk.", self.industry)
        else:
            vectorstore = FAISS.from_documents(documents, self.embeddings)
            vectorstore.save_local(self.index_dir)
            logger.info("Built and saved FAISS vector store for industry '%s'.", self.industry)
        return vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 3})

    async def async_load_vectorstore(self):
        documents = await asyncio.to_thread(self.load_reviews)  # Optionally offload cache loading
        if os.path.exists(self.index_dir):
            vectorstore = await FAISS.aload_local(self.index_dir, self.embeddings, asynchronous=True)
            logger.info("Loaded FAISS vector store for industry '%s' from disk.", self.industry)
        else:
            vectorstore = await FAISS.afrom_documents(documents, self.embeddings)
            # Assuming there's an async method for saving if needed,
            # otherwise, you may offload the saving part to a thread:
            await asyncio.to_thread(vectorstore.save_local, self.index_dir)
            logger.info("Built and saved FAISS vector store for industry '%s'.", self.industry)
        return vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 3})
