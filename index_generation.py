# indexer.py (or a new module like index_generation.py)
import os
import pickle

import faiss
from sentence_transformers import SentenceTransformer

from data_loader import fetch_historical_reviews_from_excel  # your loader


def generate_faiss_index(past_excel_path, industry, embeddings_model_name="all-MiniLM-L6-v2", index_dir_prefix="faiss_index_"):
    # Load historical reviews from the Excel file
    documents = fetch_historical_reviews_from_excel(past_excel_path, industry)
    texts = [doc.page_content for doc in documents]
    
    # Initialize the SentenceTransformer model
    model = SentenceTransformer(embeddings_model_name)
    embeddings = model.encode(texts, convert_to_numpy=True)
    dimension = embeddings.shape[1]
    
    # Create a FAISS index (using L2 distance)
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)
    
    # Prepare the directory and file path for saving the index
    index_dir = f"{index_dir_prefix}{industry}"
    os.makedirs(index_dir, exist_ok=True)
    index_file = os.path.join(index_dir, f"{industry}.index")
    
    # Write the FAISS index to disk
    faiss.write_index(index, index_file)
    
    # Optionally, cache the documents for later use
    cache_dir = "cache"
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f"past_reviews_{industry}.pkl")
    with open(cache_file, "wb") as f:
        pickle.dump(documents, f)
    
    print(f"Generated FAISS index at {index_file} and cache at {cache_file}")
    return index_file
