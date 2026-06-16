import json
import numpy as np
from sentence_transformers import SentenceTransformer
import os

DOCUMENTS_PATH = "data/processed/nco_documents.json"
EMBEDDINGS_PATH = "models/nco_embeddings.npy"

MODEL_NAME = "BAAI/bge-small-en-v1.5"

def load_documents(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def generate_embeddings(documents, model):
    return model.encode(
        documents,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True
    )

def save_embeddings(embeddings, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    np.save(path, embeddings)

if __name__ == "__main__":
    print("📥 Loading documents...")
    documents = load_documents(DOCUMENTS_PATH)

    print("🤖 Loading SBERT model...")
    model = SentenceTransformer(MODEL_NAME)

    print("🔢 Generating embeddings...")
    embeddings = generate_embeddings(documents, model)

    save_embeddings(embeddings, EMBEDDINGS_PATH)

    print("✅ Embeddings generated")
    print(f"📊 Shape: {embeddings.shape}")
