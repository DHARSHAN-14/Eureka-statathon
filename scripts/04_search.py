import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

INDEX_PATH = "models/nco_faiss.index"
EMBEDDINGS_PATH = "models/nco_embeddings.npy"
METADATA_PATH = "data/processed/nco_metadata.json"

MODEL_NAME = "BAAI/bge-small-en-v1.5"
TOP_K = 5

def load_metadata(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_index(path):
    return faiss.read_index(path)

def embed_query(query, model):
    embedding = model.encode(
        [query],
        convert_to_numpy=True,
        normalize_embeddings=True
    )
    return embedding

def search(query):
    print(f"\n🔎 Query: {query}\n")

    metadata = load_metadata(METADATA_PATH)
    index = load_index(INDEX_PATH)

    model = SentenceTransformer(MODEL_NAME)

    query_vec = embed_query(query, model)

    scores, indices = index.search(query_vec, TOP_K)

    print("📌 Top Matches:\n")
    for rank, (idx, score) in enumerate(zip(indices[0], scores[0]), start=1):
        result = metadata[idx]
        print(f"{rank}. {result['occupation_title']}")
        print(f"   NCO Code: {result['nco_2015']}")
        print(f"   Confidence Score: {score:.4f}\n")

if __name__ == "__main__":
    while True:
        query = input("Enter occupation query (or 'exit'): ")
        if query.lower() == "exit":
            break
        search(query)
