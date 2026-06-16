from pathlib import Path
from enum import Enum


# ==========================================
# Project Root
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent.parent


# ==========================================
# Data Paths
# ==========================================

DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

NCO_CSV_PATH = RAW_DATA_DIR / "nco_dataset_v6_final.csv"
DOCUMENTS_PATH = PROCESSED_DATA_DIR / "nco_documents.json"
METADATA_PATH = PROCESSED_DATA_DIR / "nco_metadata.json"
OLD_GN_PATH = PROCESSED_DATA_DIR / "nco_graph.json"  # OLD implementation's graph


# ==========================================
# Models
# ==========================================

MODELS_DIR = BASE_DIR / "models"
EMBEDDINGS_PATH = MODELS_DIR / "nco_embeddings.npy"
FAISS_INDEX_PATH = MODELS_DIR / "nco_faiss.index"

EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
RERANKER_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"


# ==========================================
# Knowledge Graph
# ==========================================

GRAPH_DIR = BASE_DIR / "src" / "graph" / "graph_output"
GRAPH_JSON_PATH = GRAPH_DIR / "nco_graph.json"
GRAPHML_PATH = GRAPH_DIR / "nco_graph.graphml"
GEXF_PATH = GRAPH_DIR / "nco_graph.gexf"
HTML_VISUALIZATION_PATH = GRAPH_DIR / "nco_knowledge_graph.html"


# ==========================================
# Advanced Hybrid Search Configuration
# ==========================================

class SearchMode(str, Enum):
    """Search modes for different use cases"""
    SEMANTIC = "semantic"           # Pure semantic search
    HYBRID_BALANCED = "hybrid_balanced"  # NEW default
    HYBRID_OPTIMIZED = "hybrid_optimized"  # OLD domain-tuned
    HYBRID_GRAPH_FOCUSED = "hybrid_graph"  # Graph emphasis
    RERANKED = "reranked"           # With CrossEncoder


# Default search mode
DEFAULT_SEARCH_MODE = SearchMode.HYBRID_OPTIMIZED

# Top-K configuration
TOP_K_RESULTS = 10
MAX_TOP_K = 100
CANDIDATE_K = 50    # Pre-filter from FAISS
TITLE_CANDIDATE_K = 50


# ==========================================
# Hybrid Scoring Parameters (Domain Tuned)
# ==========================================

# Semantic scoring weights
SEMANTIC_WEIGHT = 0.70              # Weight for semantic similarity
GRAPH_WEIGHT = 0.20                 # Weight for graph hierarchy
TITLE_WEIGHT = 0.10                 # Weight for title matching

# Score boosting (from OLD implementation)
GLOBAL_BOOST_MULTIPLIER = 1.8       # Applied to base score
TITLE_EXACT_BOOST = 1.6             # Exact title match
TITLE_PARTIAL_BOOST = 1.25          # Partial title match
TITLE_INDEX_BOOST = 1.15            # Title index score boost

# Reranking weights
RERANK_WEIGHT = 0.10                # Weight for reranker score

# Confidence threshold (warning if below)
CONFIDENCE_THRESHOLD = 0.45
CONFIDENCE_LOW_THRESHOLD = 0.3
CONFIDENCE_HIGH_THRESHOLD = 0.75


# ==========================================
# Graph Hierarchy Scoring
# ==========================================

# Hierarchy depth-based scoring
HIERARCHY_DEPTH_SCORES = {
    1: 0.2,   # Division level
    2: 0.4,   # SubDivision level
    3: 0.6,   # Group level
    4: 0.8,   # Family level
    5: 1.0,   # Occupation level (full)
}

# Sibling relevance boost
SIBLING_BOOST = 0.05
PARENT_RELEVANCE_BOOST = 0.03


# ==========================================
# Retrieval Configuration
# ==========================================

# FAISS search parameters
FAISS_METRIC_TYPE = "IndexFlatIP"  # Inner Product (dot product) for normalized embeddings
BATCH_SIZE_EMBEDDING = 32
BATCH_SIZE_RERANKING = 32

# Caching
ENABLE_QUERY_CACHING = True
CACHE_MAX_SIZE = 1000
CACHE_TTL_SECONDS = 3600


# ==========================================
# Logging & Monitoring
# ==========================================

LOG_LEVEL = "INFO"
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "search_engine.log"
ENABLE_QUERY_LOGGING = True
ENABLE_PERFORMANCE_METRICS = True


# ==========================================
# API Configuration
# ==========================================

API_HOST = "0.0.0.0"
API_PORT = 8000
API_VERSION = "1.0.0"
API_TITLE = "NCO Intelligence Engine Pro"
ENABLE_CORS = True
DOCS_ENABLED = True  # Swagger UI


# ==========================================
# Node Types
# ==========================================

NODE_DIVISION = "Division"
NODE_SUBDIVISION = "SubDivision"
NODE_GROUP = "Group"
NODE_FAMILY = "Family"
NODE_OCCUPATION = "Occupation"

NODE_TYPES = [
    NODE_DIVISION,
    NODE_SUBDIVISION,
    NODE_GROUP,
    NODE_FAMILY,
    NODE_OCCUPATION,
]


# ==========================================
# Relationship Types
# ==========================================

REL_HAS_SUBDIVISION = "HAS_SUBDIVISION"
REL_HAS_GROUP = "HAS_GROUP"
REL_HAS_FAMILY = "HAS_FAMILY"
REL_HAS_OCCUPATION = "HAS_OCCUPATION"

RELATIONSHIP_TYPES = [
    REL_HAS_SUBDIVISION,
    REL_HAS_GROUP,
    REL_HAS_FAMILY,
    REL_HAS_OCCUPATION,
]


# ==========================================
# Feature Flags
# ==========================================

FEATURE_ENABLE_RERANKER = True
FEATURE_ENABLE_GRAPH_HIERARCHY = True
FEATURE_ENABLE_SCORE_DETAILS = True
FEATURE_ENABLE_ANALYTICS = True
FEATURE_ENABLE_EXPORT_RESULTS = True

REL_HAS_GROUP = "HAS_GROUP"

REL_HAS_FAMILY = "HAS_FAMILY"

REL_HAS_OCCUPATION = "HAS_OCCUPATION"