import os
import sys
import time
import math
import re
from collections import defaultdict

# Add project directory to path
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_DIR)

import db_store

# Set environment variable to load .env before anything else
from dotenv import load_dotenv
load_dotenv()

# Simple tokenizer and text cleaner
def clean_and_tokenize(text):
    text = str(text or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return [w for w in text.split() if len(w) > 2]

class PurePythonTFIDF:
    def __init__(self):
        self.doc_count = 0
        self.vocab = set()
        # Word -> list of (doc_idx, term_frequency)
        self.inverted_index = defaultdict(list)
        # Doc index -> length of doc vector (for cosine normalization)
        self.doc_lengths = {}
        # Word -> doc frequency
        self.df = defaultdict(int)
        # Store metadata
        self.metadata = []

    def fit_transform(self, documents, metadata):
        self.doc_count = len(documents)
        self.metadata = metadata
        
        # Build document vectors
        doc_tfs = []
        for idx, doc in enumerate(documents):
            words = clean_and_tokenize(doc)
            tf = defaultdict(int)
            for w in words:
                tf[w] += 1
            doc_tfs.append(tf)
            
            # Count document frequencies
            for w in tf.keys():
                self.df[w] += 1
                self.vocab.add(w)
                
        # Build inverted index and compute lengths
        for idx, tf in enumerate(doc_tfs):
            length_sq = 0.0
            for term, count in tf.items():
                # TF-IDF calculation: tf * idf
                # idf = log(N / df)
                idf = math.log((self.doc_count + 1) / (self.df[term] + 0.5)) + 1
                tfidf_val = count * idf
                self.inverted_index[term].append((idx, tfidf_val))
                length_sq += tfidf_val ** 2
            self.doc_lengths[idx] = math.sqrt(length_sq) if length_sq > 0 else 1.0

    def search(self, query, top_k=5):
        query_words = clean_and_tokenize(query)
        if not query_words:
            return []
            
        # Compute query vector
        query_tf = defaultdict(int)
        for w in query_words:
            query_tf[w] += 1
            
        query_vector = {}
        query_length_sq = 0.0
        for term, count in query_tf.items():
            if term in self.df:
                idf = math.log((self.doc_count + 1) / (self.df[term] + 0.5)) + 1
                val = count * idf
                query_vector[term] = val
                query_length_sq += val ** 2
        query_length = math.sqrt(query_length_sq) if query_length_sq > 0 else 1.0
        
        # Accumulate scores for documents
        scores = defaultdict(float)
        for term, q_val in query_vector.items():
            for doc_idx, doc_val in self.inverted_index[term]:
                scores[doc_idx] += q_val * doc_val
                
        # Normalize and build results
        results = []
        for doc_idx, raw_score in scores.items():
            # Cosine similarity
            cosine_score = raw_score / (query_length * self.doc_lengths[doc_idx])
            results.append((doc_idx, cosine_score))
            
        results = sorted(results, key=lambda x: x[1], reverse=True)[:top_k]
        
        output = []
        for doc_idx, score in results:
            meta = self.metadata[doc_idx]
            output.append({
                "occupation_title": meta.get("occupation_title"),
                "nco_code": meta.get("nco_2015"),
                "score": score
            })
        return output

def main():
    print("Connecting and loading search documents from PostgreSQL...")
    start_time = time.time()
    documents, metadata = db_store.load_search_documents()
    print(f"Loaded {len(documents)} search documents in {time.time() - start_time:.4f}s")
    
    if not documents:
        print("No search documents found in database. Run migration first.")
        return
        
    print("Building TF-IDF Index...")
    start_time = time.time()
    tfidf = PurePythonTFIDF()
    tfidf.fit_transform(documents, metadata)
    print(f"TF-IDF Index built in {time.time() - start_time:.4f}s")
    
    # Test queries
    test_queries = [
        "agriculture crop farmer",
        "doctor physician medical",
        "software engineer computer developer",
        "carpenter wood working",
        "helper manual labor"
    ]
    
    print("\n--- Running Search Tests ---")
    for q in test_queries:
        start_search = time.time()
        results = tfidf.search(q, top_k=3)
        search_time = (time.time() - start_search) * 1000  # ms
        print(f"\nQuery: '{q}' (took {search_time:.3f}ms)")
        for idx, r in enumerate(results):
            print(f"  {idx+1}. Code: {r['nco_code']} | Score: {r['score']:.4f} | Title: {r['occupation_title']}")

if __name__ == "__main__":
    main()
