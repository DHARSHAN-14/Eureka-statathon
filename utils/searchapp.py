import json
import os
import numpy as np
import faiss
import re
from sentence_transformers import SentenceTransformer
import sys

# ------------------ CONFIG ------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
if PROJECT_DIR not in sys.path:
    sys.path.append(PROJECT_DIR)

from database import db_store

MODEL_NAME = "intfloat/multilingual-e5-base"   # ⚠️ MUST match scripts/legacy_pipeline/02_generateEmbedding.py & scripts/migrate_to_postgres.py (768 dims)
DEFAULT_TOP_K = 5
MAX_TOP_K = 100
CANDIDATE_K = 150
TITLE_CANDIDATE_K = 100
CONFIDENCE_THRESHOLD = 0.45
ALPHA = 0.65               # semantic (description FAISS)
BETA  = 0.15               # graph keyword coverage — lowered (keywords include structural noise)
GAMMA = 0.20               # description keyword match — raised (more targeted signal)

# Words that carry no occupational meaning — filtered before scoring
STOPWORDS = {
    "i", "me", "my", "we", "our", "you", "your", "he", "she", "it", "his", "her", "its",
    "they", "their", "this", "that", "these", "those", "am", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did", "a", "an", "the",
    "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "from",
    "will", "would", "could", "should", "may", "might", "can", "as", "if", "then",
    "so", "up", "out", "about", "into", "through", "during", "some", "any", "all",
    "each", "both", "few", "more", "most", "other", "such", "no", "not", "only", "own",
    "same", "than", "too", "very", "just", "also", "still", "now", "how", "where",
    "when", "what", "who", "which", "there", "here",
    # Generic occupation/person words that appear everywhere and carry no signal
    "work", "works", "working", "worked", "person", "people", "professional",
    "worker", "workers", "staff", "employee", "employees",
}

# Patterns that introduce first-person job descriptions without adding occupational content
_FILLER_RE = re.compile(
    r"^i\s+(am\s+a[n]?\s+|am\s+|'m\s+a[n]?\s+|'m\s+|work\s+as\s+a[n]?\s+|work\s+as\s+|have\s+been\s+a[n]?\s+)",
    re.IGNORECASE,
)
_JOB_PREFIX_RE = re.compile(
    r"^(my\s+job\s+is\s+(to\s+)?|my\s+work\s+is\s+(to\s+)?|my\s+occupation\s+is\s+)",
    re.IGNORECASE,
)

# ------------------ LOAD DATA ------------------
print("Loading metadata from PostgreSQL...")
documents, metadata = db_store.load_search_documents()
if not metadata:
    raise RuntimeError("No search metadata found in PostgreSQL. Run scripts/migrate_to_postgres.py first.")

print("Loading Graph Network from PostgreSQL...")
gn = db_store.load_graph()

print("Loading FAISS index from PostgreSQL...")
index_bytes = db_store.load_asset("nco_faiss.index")
if not index_bytes:
    raise RuntimeError("No FAISS index found in PostgreSQL. Run scripts/migrate_to_postgres.py first.")
index = faiss.deserialize_index(np.frombuffer(index_bytes, dtype="uint8"))

print("Loading SBERT model...")
model = SentenceTransformer(MODEL_NAME)

print("Building title search index...")
title_documents = [item.get("occupation_title", "") for item in metadata]
# multilingual-e5 requires "passage: " prefix for corpus/document encoding
title_embeddings = model.encode(
    ["passage: " + t for t in title_documents],
    show_progress_bar=False,
    convert_to_numpy=True,
    normalize_embeddings=True,
)
title_index = faiss.IndexFlatIP(title_embeddings.shape[1])
title_index.add(title_embeddings)

print("Loading detailed job descriptions from PostgreSQL...")
job_details = {}
_, occupation_rows = db_store.load_csv_rows()
for row in occupation_rows:
    nco_code = row["NCO 2015"]
    job_details[nco_code] = {
        "nco_2004_code": row["NCO 2004"],
        "division": row["Division"],
        "sub_division": row["Sub Division"],
        "group": row["Group"],
        "family": row["Family"],
        "occupation_description": row["Occupation Description"],
        "family_description": row["Family Description"],
        "group_description": row["Group Description"]
    }

# ------------------ HELPER FUNCTIONS ------------------
def clean_text(text):
    return re.sub(r"[^a-z0-9\s]", "", text.lower())

# Pre-build description word sets for fast lookup (rebuilt on reload_from_db)
_desc_word_sets = {}

def _build_desc_word_sets():
    global _desc_word_sets
    _desc_word_sets = {}
    for code, d in job_details.items():
        combined = " ".join(filter(None, [
            d.get("occupation_description", ""),
            d.get("family_description", ""),
            d.get("group_description", ""),
        ]))
        _desc_word_sets[code] = set(clean_text(combined).split()) - STOPWORDS if combined else set()

_build_desc_word_sets()


def _preprocess_query(query: str) -> str:
    """Strip first-person filler that adds no occupational signal."""
    q = _JOB_PREFIX_RE.sub("", query.strip())
    q = _FILLER_RE.sub("", q)
    return q.strip() or query.strip()


def embed_query(query):
    core = _preprocess_query(query)
    # Append "occupation" only for very short (1-word) queries to anchor meaning
    if len(core.split()) <= 1:
        core = core + " occupation"
    # multilingual-e5 models require "query: " prefix for queries
    prefixed = "query: " + core
    return model.encode([prefixed], convert_to_numpy=True, normalize_embeddings=True)


def compute_graph_score(query, occupation_code):
    """
    Fraction of meaningful query words covered by the occupation's keyword graph.
    Measures query-side coverage — not penalised by how many keywords the occupation has.
    """
    query_words = set(clean_text(_preprocess_query(query)).split()) - STOPWORDS
    if not query_words:
        return 0.0
    keywords = set(gn.get(occupation_code, {}).get("keywords", []))
    if not keywords:
        return 0.0
    overlap = query_words & keywords
    return len(overlap) / len(query_words)


def compute_description_score(query, occupation_code):
    """
    Fraction of meaningful query words that appear in the occupation's description text.
    Provides a lightweight keyword-level signal independent of SBERT.
    """
    query_words = set(clean_text(_preprocess_query(query)).split()) - STOPWORDS
    if not query_words:
        return 0.0
    desc_words = _desc_word_sets.get(occupation_code, set())
    if not desc_words:
        return 0.0
    overlap = query_words & desc_words
    return len(overlap) / len(query_words)


# ------------------ HELPER FUNCTIONS ------------------
def _matches_filter(filter_val, row_val):
    if not filter_val:
        return True
    if isinstance(filter_val, (list, tuple, set)):
        normalized_filter = {str(v).strip().lower() for v in filter_val if v}
        if not normalized_filter:
            return True
        return str(row_val).strip().lower() in normalized_filter
    return str(filter_val).strip().lower() == str(row_val).strip().lower()

_all_jobs_cache = None


def get_all_jobs(filters=None):
    global _all_jobs_cache
    if not filters:
        if _all_jobs_cache is not None:
            return _all_jobs_cache
    all_jobs = []
    _, rows = db_store.load_csv_rows()
    for row in rows:
        if filters:
            if not _matches_filter(filters.get("division"), row.get("Division")):
                continue
            if not _matches_filter(filters.get("sub_division"), row.get("Sub Division")):
                continue
            if not _matches_filter(filters.get("group"), row.get("Group")):
                continue
            if not _matches_filter(filters.get("family"), row.get("Family")):
                continue

        all_jobs.append({
            "occupation_title": row["Occupational Title"],
            "nco_code": row["NCO 2015"],
            "details": {
                "nco_2004_code": row["NCO 2004"],
                "division": row["Division"],
                "sub_division": row["Sub Division"],
                "group": row["Group"],
                "family": row["Family"],
                "occupation_description": row.get("Occupation Description", ""),
                "family_description": row.get("Family Description", ""),
                "group_description": row.get("Group Description", ""),
            }
        })
    if not filters:
        _all_jobs_cache = all_jobs
    return all_jobs


def reload_from_db():
    global documents, metadata, gn, index, title_index, job_details, _all_jobs_cache, _desc_word_sets
    _all_jobs_cache = None

    print("Reloading search runtime from PostgreSQL...")
    documents, metadata = db_store.load_search_documents()
    gn = db_store.load_graph()

    index_bytes = db_store.load_asset("nco_faiss.index")
    if not index_bytes:
        raise RuntimeError("No FAISS index found in PostgreSQL.")
    index = faiss.deserialize_index(np.frombuffer(index_bytes, dtype="uint8"))

    title_documents = [item.get("occupation_title", "") for item in metadata]
    # multilingual-e5 requires "passage: " prefix for corpus/document encoding
    title_embeddings = model.encode(
        ["passage: " + t for t in title_documents],
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    title_index = faiss.IndexFlatIP(title_embeddings.shape[1])
    title_index.add(title_embeddings)

    job_details = {}
    _, rows = db_store.load_csv_rows()
    for row in rows:
        nco_code = row["NCO 2015"]
        job_details[nco_code] = {
            "nco_2004_code": row["NCO 2004"],
            "division": row["Division"],
            "sub_division": row["Sub Division"],
            "group": row["Group"],
            "family": row["Family"],
            "occupation_description": row["Occupation Description"],
            "family_description": row["Family Description"],
            "group_description": row["Group Description"]
        }

    _build_desc_word_sets()

# ------------------ SEARCH FUNCTION ------------------
def search(query, top_k=DEFAULT_TOP_K, filters=None):
    import difflib
    try:
        top_k = int(top_k)
    except (TypeError, ValueError):
        top_k = DEFAULT_TOP_K
    top_k = max(1, min(top_k, MAX_TOP_K))

    has_filters = filters and any(filters.values())
    clean_query = query.strip().lower()

    # Embed once — shared by FAISS retrieval and title-match scoring
    query_vec = embed_query(query)

    # --- FAISS retrieval ---
    candidate_k = max(CANDIDATE_K, top_k)
    title_candidate_k = max(TITLE_CANDIDATE_K, top_k)
    if has_filters:
        candidate_k = max(1000, top_k * 10)
        title_candidate_k = max(1000, top_k * 10)

    scores, indices = index.search(query_vec, candidate_k)
    title_scores, title_indices = title_index.search(query_vec, title_candidate_k)

    # Unified candidate pool keyed by metadata index position
    # title_match_priority: 0=exact, 1=startswith, 2=contains, 3=semantic-only
    pool = {}
    for idx, sem_score in zip(indices[0], scores[0]):
        if idx < 0:
            continue
        pool[int(idx)] = {
            "semantic_score": float(sem_score),
            "title_score": 0.0,
            "title_match_priority": 3,
        }
    for idx, ts in zip(title_indices[0], title_scores[0]):
        if idx < 0:
            continue
        entry = pool.setdefault(int(idx), {
            "semantic_score": 0.0,
            "title_score": 0.0,
            "title_match_priority": 3,
        })
        entry["title_score"] = float(ts)

    # --- Inject substring title matches; boost title_score and set priority ---
    if clean_query:
        for idx, item in enumerate(metadata):
            title_lower = item.get("occupation_title", "").lower()
            if clean_query not in title_lower:
                continue
            ratio = difflib.SequenceMatcher(None, clean_query, title_lower).ratio()
            match_bonus = 0.7 + 0.3 * ratio
            if title_lower == clean_query:
                priority = 0
            elif title_lower.startswith(clean_query):
                priority = 1
            else:
                priority = 2
            entry = pool.setdefault(idx, {
                "semantic_score": 0.0,
                "title_score": 0.0,
                "title_match_priority": 3,
            })
            entry["title_match_priority"] = min(entry["title_match_priority"], priority)
            # Keep the higher of FAISS title similarity and string-match bonus
            entry["title_score"] = max(entry["title_score"], match_bonus)

    # --- Score all candidates ---
    candidates = []
    for idx, data in pool.items():
        semantic_score = data["semantic_score"]
        title_score    = data["title_score"]
        occ_code       = metadata[idx]["nco_2015"]
        details        = job_details.get(occ_code, {})

        if has_filters:
            if not _matches_filter(filters.get("division"), details.get("division")):
                continue
            if not _matches_filter(filters.get("sub_division"), details.get("sub_division")):
                continue
            if not _matches_filter(filters.get("group"), details.get("group")):
                continue
            if not _matches_filter(filters.get("family"), details.get("family")):
                continue

        gn_score   = compute_graph_score(query, occ_code)
        desc_score = compute_description_score(query, occ_code)

        combined = (
            ALPHA * float(semantic_score) +
            BETA  * gn_score +
            GAMMA * desc_score
        )
        # Reduce title cosine weight — it hurts descriptive/sentence queries
        final_score = min(0.78 * combined + 0.22 * float(title_score), 1.0)

        candidates.append({
            "occupation_title": metadata[idx]["occupation_title"],
            "row_id": metadata[idx].get("row_id", idx),
            "nco_code": occ_code,
            "semantic_score": float(semantic_score),
            "title_score": float(title_score),
            "gn_score": float(gn_score),
            "desc_score": float(desc_score),
            "final_score": float(final_score),
            "title_match_priority": data["title_match_priority"],
            "details": details
        })

    # Sort: exact/startswith/contains title matches first, then by final_score within each group
    candidates.sort(key=lambda x: (x["title_match_priority"], -x["final_score"]))

    # Deduplicate by NCO code and return top_k
    seen: set = set()
    final_results = []
    for item in candidates:
        if item["nco_code"] not in seen:
            final_results.append(item)
            seen.add(item["nco_code"])
        if len(final_results) >= top_k:
            break

    return final_results

def display_results(query, top_results):
    if not top_results or top_results[0]["final_score"] < CONFIDENCE_THRESHOLD:
        print("⚠️ Low confidence: please clarify your occupation description.\n")

    print(f"\n" + "="*80)
    print(f"🔎 Query: {query}")
    print("="*80 + "\n")

    for rank, r in enumerate(top_results, start=1):
        details = r['details']

        print(f"RANK {rank} | SCORE: {r['final_score']:.3f}")
        print(f"Title: {r['occupation_title']}")
        print(f"NCO Code: {r['nco_code']}")
        print("-" * 40)

        if details:
            print(f"Hierarchy:")
            print(f"  - Division: {details['division']}")
            print(f"  - Sub-Division: {details['sub_division']}")
            print(f"  - Group: {details['group']}")
            print(f"  - Family: {details['family']}")
            print("\nOccupation Description:")
            print(f"  {details['occupation_description']}")
            print("\nFamily Description:")
            print(f"  {details['family_description']}")
            print("\nGroup Description:")
            print(f"  {details['group_description']}")
        else:
            print("No additional details found in CSV.")

        print(f"\nMetadata Scores:")
        print(f"   (Semantic: {r['semantic_score']:.3f} | Graph: {r['gn_score']:.3f} | Desc: {r.get('desc_score', 0):.3f})")
        print("="*80 + "\n")




# ------------------ MAIN LOOP ------------------
if __name__ == "__main__":
    while True:
        query = input("Enter occupation query (or 'exit'): ").strip()
        if query.lower() == "exit":
            break
        results = search(query)
        display_results(query, results)
