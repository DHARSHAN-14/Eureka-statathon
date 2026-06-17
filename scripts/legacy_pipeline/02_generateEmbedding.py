import os
import sys

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_DIR not in sys.path:
    sys.path.append(PROJECT_DIR)

from database import db_store


MODEL_NAME = "intfloat/multilingual-e5-base"   # ⚠️ Must match utils/searchapp.py MODEL_NAME (768 dims)
# multilingual-e5 requires "passage: " prefix for corpus documents
CORPUS_PREFIX = "passage: "


if __name__ == "__main__":
    db_store.init_db()
    print("Loading documents from PostgreSQL...")
    documents, _ = db_store.load_search_documents()

    print(f"Loading SBERT model: {MODEL_NAME}...")
    model = SentenceTransformer(MODEL_NAME)

    print(f"Generating embeddings for {len(documents)} documents with '{CORPUS_PREFIX}' prefix...")
    prefixed_docs = [CORPUS_PREFIX + doc for doc in documents]
    embeddings = model.encode(
        prefixed_docs,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    print("Saving embeddings to PostgreSQL...")
    db_store.save_embeddings(embeddings)
    print(f"Embeddings stored. Shape: {embeddings.shape}")

    print("Building FAISS index...")
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    serialized_index = faiss.serialize_index(index)
    db_store.save_asset("nco_faiss.index", bytes(serialized_index), "application/x-faiss")
    print(f"FAISS index saved to PostgreSQL (dim={dim}, vectors={index.ntotal})")
    print("Done! Restart the server to apply changes.")
