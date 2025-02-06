import os
import pickle

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from data_loader import fetch_historical_reviews_from_excel  # Your function to load reviews

CACHE_DIR = "cache"

class FaissRetriever:
    def __init__(self, past_excel_path, index_dir, industry, embeddings_model="sentence-transformers/all-MiniLM-L6-v2"):
        """
        Initializes the retriever.

        Args:
            past_excel_path (str): Path to the Excel file with past reviews.
            index_dir (str): Directory where the FAISS index will be stored.
            industry (str): Industry identifier (used for naming the index file).
            embeddings_model (str): HuggingFace model name for SentenceTransformer.
        """
        self.past_excel_path = past_excel_path
        self.index_dir = index_dir
        self.industry = industry
        self.embeddings_model = SentenceTransformer(embeddings_model)
        self.index_path = os.path.join(index_dir, f"{industry}.index")

        # If the index file doesn't exist, generate it from the past reviews Excel file.
        if not os.path.exists(self.index_path):
            print(f"Index file {self.index_path} does not exist. Generating FAISS index from past reviews...")
            self.generate_index()
        else:
            print(f"Index file {self.index_path} found. Loading index...")

        self.index = faiss.read_index(self.index_path)

    def generate_index(self):
        """
        Generates a FAISS index from the past reviews Excel file.
        Also caches the original reviews (documents) for later use.
        """
        # Load historical reviews using your custom loader
        documents = fetch_historical_reviews_from_excel(self.past_excel_path, self.industry)
        texts = [doc.page_content for doc in documents]

        # Compute embeddings for all reviews
        embeddings = self.embeddings_model.encode(texts, convert_to_numpy=True)
        dimension = embeddings.shape[1]

        # Create a FAISS index (using L2 distance)
        index = faiss.IndexFlatL2(dimension)
        index.add(embeddings)

        # Ensure the index directory exists
        os.makedirs(self.index_dir, exist_ok=True)
        # Save the FAISS index to disk
        faiss.write_index(index, self.index_path)
        print(f"Generated and saved FAISS index at: {self.index_path}")

        # Optionally, cache the original documents
        os.makedirs(CACHE_DIR, exist_ok=True)
        cache_file = os.path.join(CACHE_DIR, f"past_reviews_{self.industry}.pkl")
        with open(cache_file, "wb") as f:
            pickle.dump(documents, f)
        print(f"Cached past reviews at: {cache_file}")

    def retrieve_similar_reviews(self, query, top_k=3):
        """
        Retrieves the top_k most similar reviews for a given query.

        Args:
            query (str): The review text to query.
            top_k (int): Number of similar reviews to retrieve.

        Returns:
            List of tuples (index, distance).
        """
        query_vector = self.embeddings_model.encode([query]).astype(np.float32)
        distances, indices = self.index.search(query_vector, top_k)
        results = []
        for idx, dist in zip(indices[0], distances[0]):
            if idx != -1:
                results.append((idx, dist))
        return results

    def batch_retrieve_similar_reviews(self, reviews, top_k=3):
        """
        Retrieves similar reviews for a batch of reviews.

        Args:
            reviews (List[str]): A list of review texts.
            top_k (int): Number of similar reviews to retrieve for each review.

        Returns:
            List[List[tuple]]: A list (per review) of lists of tuples (index, distance).
        """
        query_vectors = self.embeddings_model.encode(reviews).astype(np.float32)
        distances, indices = self.index.search(query_vectors, top_k)
        batch_results = []
        for dist_list, idx_list in zip(distances, indices):
            review_results = [(idx, dist) for idx, dist in zip(idx_list, dist_list) if idx != -1]
            batch_results.append(review_results)
        return batch_results
