import os
import pickle

import faiss
from sentence_transformers import SentenceTransformer

from data_loader import fetch_historical_reviews_from_excel

CACHE_DIR = "cache"
INDEX_DIR_PREFIX = "faiss_index_v2_"


class FaissRetrieverV2:
    def __init__(
        self,
        past_excel_path,
        industry,
        embeddings_model="pkshatech/GLuCoSE-base-ja-v2",
        index_dir_prefix=INDEX_DIR_PREFIX,
    ):
        self.past_excel_path = past_excel_path
        self.industry = industry
        self.index_dir = os.path.abspath(f"{index_dir_prefix}{industry}")
        self.embeddings_model_name = embeddings_model
        self.embeddings_model = SentenceTransformer(embeddings_model)
        self.index_path = os.path.join(self.index_dir, f"{industry}.index")

        if not os.path.exists(self.index_path):
            print(f"Index file {self.index_path} does not exist. Generating FAISS index...")
            self.generate_index()
        else:
            print(f"Index file {self.index_path} found. Loading index...")
            cache_file = os.path.join(CACHE_DIR, f"past_reviews_{industry}.pkl")
            if os.path.exists(cache_file):
                with open(cache_file, "rb") as f:
                    self.documents = pickle.load(f)
                # Prepend the required prefix for retrieval tasks
                self.texts = [f"passage: {doc.page_content}" for doc in self.documents]
            else:
                self.generate_index()

        self.index = faiss.read_index(self.index_path)

    def generate_index(self):
        self.documents = fetch_historical_reviews_from_excel(self.past_excel_path, self.industry)
        # Ensure each document is prefixed appropriately for the new model
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
        print(f"Generated and saved FAISS index at: {self.index_path}")

        os.makedirs(CACHE_DIR, exist_ok=True)
        cache_file = os.path.join(CACHE_DIR, f"past_reviews_{self.industry}.pkl")
        with open(cache_file, "wb") as f:
            pickle.dump(self.documents, f)
        print(f"Cached past reviews at: {cache_file}")

    def batch_retrieve_similar_reviews(self, reviews, top_k=3):
        # Add the query prefix to each review
        query_texts = [f"query: {review}" for review in reviews]
        query_vectors = self.embeddings_model.encode(query_texts, convert_to_numpy=True)
        _, indices = self.index.search(query_vectors, top_k)
        batch_results = []
        for i in range(len(indices)):
            review_results = []
            for num, idx in enumerate(indices[i], start=1):
                if idx != -1:
                    text = self.texts[int(idx)]
                    clean_text = text.removeprefix("passage: ").strip()
                    review_results.append(f"{num}. {clean_text}")
            batch_results.append(review_results)
        return batch_results
