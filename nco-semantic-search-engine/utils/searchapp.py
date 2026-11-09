import os
import numpy as np
import re
import difflib
from sentence_transformers import SentenceTransformer
import sys

# ------------------ CONFIG ------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
if PROJECT_DIR not in sys.path:
    sys.path.append(PROJECT_DIR)

from database import db_store

MODEL_NAME = "BAAI/bge-small-en-v1.5"
DEFAULT_TOP_K = 5
MAX_TOP_K = 100
CONFIDENCE_THRESHOLD = 0.45
ALPHA = 0.65               # weight: full-document semantic score
BETA  = 0.15               # weight: graph keyword coverage
GAMMA = 0.20               # weight: description keyword match

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

# ------------------ LOAD DATA AT STARTUP ------------------
print("Loading Graph Network from PostgreSQL...")
gn = db_store.load_graph()

print("Loading SBERT model...")
model = SentenceTransformer(MODEL_NAME)

print("Loading detailed job descriptions from PostgreSQL...")
job_details = {}
metadata = []      # list of {row_id, nco_2015, occupation_title} — used for substring search
_all_jobs_cache = None

def _load_job_details_and_metadata():
    global job_details, metadata
    job_details = {}
    metadata = []
    _, occupation_rows = db_store.load_csv_rows()
    for row in occupation_rows:
        nco_code = row["NCO 2015"]
        row_id   = int(row.get("_row_id") or 0)
        job_details[nco_code] = {
            "nco_2004_code":          row["NCO 2004"],
            "division":               row["Division"],
            "sub_division":           row["Sub Division"],
            "group":                  row["Group"],
            "family":                 row["Family"],
            "occupation_description": row["Occupation Description"],
            "family_description":     row["Family Description"],
            "group_description":      row["Group Description"],
        }
        metadata.append({
            "row_id":           row_id,
            "nco_2015":         nco_code,
            "occupation_title": row["Occupational Title"],
        })

_load_job_details_and_metadata()

# ------------------ HELPER FUNCTIONS (defined before module-level calls) ------------------
def clean_text(text):
    return re.sub(r"[^a-z0-9\s]", "", text.lower())


# Pre-build description word sets for fast keyword overlap scoring
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
print("Search engine ready (pgvector backend).")

def _preprocess_query(query: str) -> str:
    """Strip first-person filler that adds no occupational signal."""
    q = _JOB_PREFIX_RE.sub("", query.strip())
    q = _FILLER_RE.sub("", q)
    return q.strip() or query.strip()


def embed_query(query):
    """Encode the query for full-document similarity (with BGE instruction)."""
    core = _preprocess_query(query)
    if len(core.split()) <= 1:
        core = core + " occupation"
    instruction = "Represent this sentence for searching relevant passages: " + core
    return model.encode([instruction], convert_to_numpy=True, normalize_embeddings=True)[0]


def embed_title_query(query):
    """Encode the query for title similarity (plain, no instruction)."""
    core = _preprocess_query(query)
    return model.encode([core], convert_to_numpy=True, normalize_embeddings=True)[0]


def compute_graph_score(query, occupation_code):
    """Fraction of meaningful query words covered by the occupation's keyword graph."""
    query_words = set(clean_text(_preprocess_query(query)).split()) - STOPWORDS
    if not query_words:
        return 0.0
    keywords = set(gn.get(occupation_code, {}).get("keywords", []))
    if not keywords:
        return 0.0
    overlap = query_words & keywords
    return len(overlap) / len(query_words)


def compute_description_score(query, occupation_code):
    """Fraction of meaningful query words that appear in the occupation's description text."""
    query_words = set(clean_text(_preprocess_query(query)).split()) - STOPWORDS
    if not query_words:
        return 0.0
    desc_words = _desc_word_sets.get(occupation_code, set())
    if not desc_words:
        return 0.0
    overlap = query_words & desc_words
    return len(overlap) / len(query_words)


def _matches_filter(filter_val, row_val):
    if not filter_val:
        return True
    if isinstance(filter_val, (list, tuple, set)):
        normalized_filter = {str(v).strip().lower() for v in filter_val if v}
        if not normalized_filter:
            return True
        return str(row_val).strip().lower() in normalized_filter
    return str(filter_val).strip().lower() == str(row_val).strip().lower()


# ------------------ DIRECTORY LISTING ------------------
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
            "nco_code":         row["NCO 2015"],
            "details": {
                "nco_2004_code":          row["NCO 2004"],
                "division":               row["Division"],
                "sub_division":           row["Sub Division"],
                "group":                  row["Group"],
                "family":                 row["Family"],
                "occupation_description": row.get("Occupation Description", ""),
                "family_description":     row.get("Family Description", ""),
                "group_description":      row.get("Group Description", ""),
            }
        })
    if not filters:
        _all_jobs_cache = all_jobs
    return all_jobs


# ------------------ HOT-RELOAD ------------------
def reload_from_db():
    """Reload all in-memory data after an admin CRUD mutation."""
    global gn, _all_jobs_cache
    _all_jobs_cache = None

    print("Reloading search runtime from PostgreSQL...")
    gn = db_store.load_graph()
    _load_job_details_and_metadata()
    _build_desc_word_sets()
    print("Search runtime reloaded.")


# ------------------ SEARCH FUNCTION ------------------
def search(query, top_k=DEFAULT_TOP_K, filters=None):
    try:
        top_k = int(top_k)
    except (TypeError, ValueError):
        top_k = DEFAULT_TOP_K
    top_k = max(1, min(top_k, MAX_TOP_K))

    clean_query = query.strip().lower()

    # --- Stage 1: Substring title-match fast path ---
    # Scans in-memory metadata; returns immediately if enough matches found.
    # pgvector is not involved at this stage.
    title_hits = {}   # nco_code -> {row info}
    if clean_query:
        for item in metadata:
            title_lower = item.get("occupation_title", "").lower()
            if clean_query not in title_lower:
                continue
            occ_code = item["nco_2015"]
            details  = job_details.get(occ_code, {})
            if filters:
                if not _matches_filter(filters.get("division"),     details.get("division")):
                    continue
                if not _matches_filter(filters.get("sub_division"), details.get("sub_division")):
                    continue
                if not _matches_filter(filters.get("group"),        details.get("group")):
                    continue
                if not _matches_filter(filters.get("family"),       details.get("family")):
                    continue
            ratio = difflib.SequenceMatcher(None, clean_query, title_lower).ratio()
            match_bonus = 0.7 + 0.3 * ratio
            if title_lower == clean_query:
                priority = 0
            elif title_lower.startswith(clean_query):
                priority = 1
            else:
                priority = 2
            existing = title_hits.get(occ_code)
            if existing is None or priority < existing["priority"]:
                title_hits[occ_code] = {
                    "occupation_title":    item["occupation_title"],
                    "row_id":              item.get("row_id", 0),
                    "nco_code":            occ_code,
                    "semantic_score":      match_bonus,
                    "title_score":         match_bonus,
                    "gn_score":            compute_graph_score(query, occ_code),
                    "desc_score":          compute_description_score(query, occ_code),
                    "final_score":         match_bonus,
                    "priority":            priority,
                    "details":             details,
                }

    title_results = sorted(title_hits.values(), key=lambda x: (x["priority"], -x["final_score"]))

    if len(title_results) >= top_k:
        return title_results[:top_k]

    # --- Stage 2: pgvector semantic search (fills remaining slots) ---
    query_vec = embed_query(query)
    title_vec = embed_title_query(query)

    pgv_results = db_store.vector_search(
        query_vec=query_vec,
        title_vec=title_vec,
        top_k=max(top_k * 4, 50),   # fetch extra so graph/desc re-scoring has room to reorder
        filters=filters,
    )

    seen = {item["nco_code"] for item in title_results}
    candidates = list(title_results)

    for r in pgv_results:
        occ_code = r["nco_2015"]
        if occ_code in seen:
            continue
        seen.add(occ_code)

        details = job_details.get(occ_code, {
            "nco_2004_code":          r.get("nco_2004", ""),
            "division":               r.get("division", ""),
            "sub_division":           r.get("sub_division", ""),
            "group":                  r.get("occupation_group", ""),
            "family":                 r.get("family", ""),
            "occupation_description": r.get("occupation_description", ""),
            "family_description":     r.get("family_description", ""),
            "group_description":      r.get("group_description", ""),
        })

        gn_score   = compute_graph_score(query, occ_code)
        desc_score = compute_description_score(query, occ_code)
        doc_s      = r["doc_score"]
        title_s    = r["title_score"]

        combined = ALPHA * doc_s + BETA * gn_score + GAMMA * desc_score
        final_score = min(0.78 * combined + 0.22 * title_s, 1.0)

        candidates.append({
            "occupation_title": r["occupation_title"],
            "row_id":           r["id"],
            "nco_code":         occ_code,
            "semantic_score":   doc_s,
            "title_score":      title_s,
            "gn_score":         gn_score,
            "desc_score":       desc_score,
            "final_score":      final_score,
            "priority":         3,   # semantic-only, lower than any title match
            "details":          details,
        })

    # Sort: exact/startswith/contains title matches first, then by score
    candidates.sort(key=lambda x: (x["priority"], -x["final_score"]))
    return candidates[:top_k]


# ------------------ CLI (for local testing) ------------------
def display_results(query, top_results):
    if not top_results or top_results[0]["final_score"] < CONFIDENCE_THRESHOLD:
        print("⚠️ Low confidence: please clarify your occupation description.\n")

    print(f"\n" + "="*80)
    print(f"🔎 Query: {query}")
    print("="*80 + "\n")

    for rank, r in enumerate(top_results, start=1):
        details = r["details"]
        print(f"RANK {rank} | SCORE: {r['final_score']:.3f}")
        print(f"Title: {r['occupation_title']}")
        print(f"NCO Code: {r['nco_code']}")
        print("-" * 40)
        if details:
            print(f"Hierarchy:")
            print(f"  - Division:     {details.get('division', '')}")
            print(f"  - Sub-Division: {details.get('sub_division', '')}")
            print(f"  - Group:        {details.get('group', '')}")
            print(f"  - Family:       {details.get('family', '')}")
            print("\nOccupation Description:")
            print(f"  {details.get('occupation_description', '')}")
            print("\nFamily Description:")
            print(f"  {details.get('family_description', '')}")
            print("\nGroup Description:")
            print(f"  {details.get('group_description', '')}")
        else:
            print("No additional details found.")
        print(f"\nMetadata Scores:")
        print(f"   (Semantic: {r['semantic_score']:.3f} | Graph: {r['gn_score']:.3f} | Desc: {r.get('desc_score', 0):.3f})")
        print("="*80 + "\n")


if __name__ == "__main__":
    while True:
        query = input("Enter occupation query (or 'exit'): ").strip()
        if query.lower() == "exit":
            break
        results = search(query)
        display_results(query, results)
