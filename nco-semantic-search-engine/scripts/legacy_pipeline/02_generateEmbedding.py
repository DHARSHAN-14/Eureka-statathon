import os
import sys

from sentence_transformers import SentenceTransformer

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_DIR not in sys.path:
    sys.path.append(PROJECT_DIR)

from database import db_store


MODEL_NAME = "BAAI/bge-small-en-v1.5"


if __name__ == "__main__":
    db_store.init_db()
    print("Loading documents from PostgreSQL...")
    documents, _ = db_store.load_search_documents()

    print("Loading SBERT model...")
    model = SentenceTransformer(MODEL_NAME)

    print("Generating embeddings...")
    embeddings = model.encode(
        documents,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    db_store.save_embeddings(embeddings)
    print("Embeddings stored in PostgreSQL")
    print(f"Shape: {embeddings.shape}")
