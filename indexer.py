import os
import pickle

import faiss
from sentence_transformers import SentenceTransformer

from data_loader import fetch_historical_reviews_from_excel  # Your loader function

CACHE_DIR = "cache"
INDEX_DIR_PREFIX = "faiss_index_"

def clean_text(text):
    """Remove the \u3000 (ideographic space) and perform other text cleaning if necessary."""
    if isinstance(text, str):
        # Replace \u3000 with a regular space or remove it entirely
        return text.replace("\u3000", "")  # Remove the ideographic space
    return text

class FaissRetriever:
    def __init__(self, past_excel_path, industry, embeddings_model="sentence-transformers/all-MiniLM-L6-v2", index_dir_prefix=INDEX_DIR_PREFIX):
        self.past_excel_path = past_excel_path
        self.industry = industry
        self.index_dir = f"{index_dir_prefix}{industry}"
        self.embeddings_model = SentenceTransformer(embeddings_model)
        self.index_path = os.path.join(self.index_dir, f"{industry}.index")
        
        # If the index file doesn't exist, generate it.
        if not os.path.exists(self.index_path):
            print(f"Index file {self.index_path} does not exist. Generating FAISS index...")
            self.generate_index()
        else:
            print(f"Index file {self.index_path} found. Loading index...")
            # Optionally, load the cached documents if available.
            cache_file = os.path.join(CACHE_DIR, f"past_reviews_{industry}.pkl")
            if os.path.exists(cache_file):
                with open(cache_file, "rb") as f:
                    self.documents = pickle.load(f)
                self.texts = [clean_text(doc.page_content) for doc in self.documents]
            else:
                # If no cache is found, you may want to re-generate the index.
                self.generate_index()
                
        self.index = faiss.read_index(self.index_path)

    def generate_index(self):
        # Load historical reviews using your loader function
        self.documents = fetch_historical_reviews_from_excel(self.past_excel_path, self.industry)
        # Extract texts from documents (adjust this if your documents are structured differently)
        self.texts = [doc.page_content for doc in self.documents]
        
        # Compute embeddings for all texts
        embeddings = self.embeddings_model.encode(self.texts, convert_to_numpy=True)
        dimension = embeddings.shape[1]
        
        # Create a FAISS index (here we use a simple flat index with L2 distance)
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
            pickle.dump(self.documents, f)
        print(f"Cached past reviews at: {cache_file}")

    def batch_retrieve_similar_reviews(self, reviews, top_k=3):
        # Encode the queries
        query_vectors = self.embeddings_model.encode(reviews, convert_to_numpy=True)
        distances, indices = self.index.search(query_vectors, top_k)
        batch_results = []
        # For each query, convert indices to actual review texts.
        for dist_list, idx_list in zip(distances, indices):
            review_results = []
            for idx in idx_list:
                if idx != -1:
                    # Convert idx (which might be numpy.int64) to int and then retrieve the review text.
                    review_text = self.texts[int(idx)]
                    review_results.append(review_text)
            batch_results.append(review_results)
        return batch_results
