import os
import sys

import faiss

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_DIR not in sys.path:
    sys.path.append(PROJECT_DIR)

from database import db_store


if __name__ == "__main__":
    db_store.init_db()
    print("Loading embeddings from PostgreSQL...")
    embeddings = db_store.load_embeddings()
    if embeddings is None:
        raise RuntimeError("No embeddings found. Run scripts/02_generateEmbedding.py first.")

    print("Building FAISS index...")
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    db_store.save_asset("nco_faiss.index", bytes(faiss.serialize_index(index)), "application/x-faiss")

    print("FAISS index stored in PostgreSQL")
    print(f"Total vectors indexed: {index.ntotal}")
