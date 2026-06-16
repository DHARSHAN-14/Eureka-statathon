import numpy as np
import faiss
import os

EMBEDDINGS_PATH = "models/nco_embeddings.npy"
INDEX_PATH = "models/nco_faiss.index"

def load_embeddings(path):
    return np.load(path)

def build_index(embeddings):
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    return index

def save_index(index, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    faiss.write_index(index, path)

if __name__ == "__main__":
    print("📥 Loading embeddings...")
    embeddings = load_embeddings(EMBEDDINGS_PATH)

    print("🧱 Building FAISS index...")
    index = build_index(embeddings)

    save_index(index, INDEX_PATH)

    print("✅ FAISS index created")
    print(f"🔢 Total vectors indexed: {index.ntotal}")
