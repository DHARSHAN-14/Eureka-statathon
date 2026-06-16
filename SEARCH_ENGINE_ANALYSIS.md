# Eureka Search Engine Implementation Analysis

**Comprehensive Comparison: Old (scripts/) vs New (src/) Implementations**

---

## Executive Summary

| Aspect | OLD (scripts/) | NEW (src/) | Winner |
|--------|---|---|---|
| **Code Organization** | Sequential scripts | Modular packages | NEW |
| **Maintainability** | Low (monolithic) | High (separation of concerns) | NEW |
| **Scalability** | Limited | Better structured | NEW |
| **Error Handling** | Minimal | Comprehensive | NEW |
| **Features** | Basic semantic search | + Graph, reranking | NEW |
| **Configuration** | Hardcoded | Centralized config.py | NEW |
| **Testing** | Difficult | Testable services | NEW |
| **Performance** | Optimized for NCO domain | General purpose | OLD* |
| **Complexity** | Simple to understand | Requires more dependencies | OLD* |
| **Dependencies** | Minimal | More extensive | OLD |

---

## PART 1: OLD IMPLEMENTATION (scripts/ folder)

### Architecture Overview

Six sequential scripts forming a linear pipeline:
```
01_preparation.py → 02_generateEmbedding.py → 03_build_faiss_index.py
                                                      ↓
                            04_search.py ← 05_searchGN.py
                                    ↓
                            06_searchapp.py (orchestrator)
```

### 1.1 **01_preparation.py** - Data Ingestion

**Purpose:** Convert raw NCO CSV to semantic documents

**Key Functions:**
- `load_data(path)` - Read CSV using pandas
- `safe_text(value)` - Handle NaN values with empty string fallback
- `create_documents(df)` - Generate 2 outputs:
  1. Rich text documents for embedding
  2. Metadata JSON with row_id, NCO code, occupation title

**Strengths:**
- Simple, straightforward text formatting
- Creates hierarchical structure (Division → Sub Division → Group → Family → Occupation)
- Preserves all descriptions

**Weaknesses:**
- No validation of required columns
- No error handling for malformed CSV
- `safe_text()` strips whitespace aggressively
- No data quality metrics

**Data Flow:**
```
nco_dataset_v3.csv 
  ↓
  → creates 2 outputs:
    - nco_documents.json (rich text docs)
    - nco_metadata.json (metadata list)
```

---

### 1.2 **02_generateEmbedding.py** - Embedding Generation

**Purpose:** Convert documents to dense vectors using SBERT

**Model:** BAAI/bge-small-en-v1.5 (128-dim embeddings)

**Key Functions:**
- `load_documents(path)` - Load JSON documents
- `generate_embeddings(documents, model)` - Batch encode with:
  - Progress bar enabled
  - Normalized embeddings (L2)
  - NumPy output format
- `save_embeddings(embeddings, path)` - Save .npy file

**Strengths:**
- Efficient batch encoding
- Normalized embeddings (good for cosine similarity)
- Clean output handling

**Weaknesses:**
- No error checking on document format
- No validation of embeddings (NaN/Inf)
- Single model hardcoded
- No batch size configuration
- Assumes embeddings directory exists

**Data Flow:**
```
nco_documents.json 
  → SBERT Model (BAAI/bge-small-en-v1.5)
  → Batch encoding (all documents at once)
  → nco_embeddings.npy (shape: [N, 128])
```

---

### 1.3 **03_build_faiss_index.py** - Index Construction

**Purpose:** Build FAISS index for fast similarity search

**Key Functions:**
- `load_embeddings(path)` - Load .npy file
- `build_index(embeddings)` - Create IndexFlatIP (Inner Product):
  - Dimension = embedding_dim (128)
  - All vectors added at once
- `save_index(index, path)` - Save FAISS index

**Strengths:**
- Simple, effective IndexFlatIP (works well for normalized embeddings)
- Fast O(1) insertion
- Clean separation from embedding generation

**Weaknesses:**
- No index configuration options
- No compression/quantization (full 128-dim vectors stored)
- Linear search O(N) on retrieval (not suitable for millions of docs)
- No validation of index integrity

**Data Flow:**
```
nco_embeddings.npy 
  → IndexFlatIP(128)
  → All embeddings added
  → nco_faiss.index (binary file)
```

---

### 1.4 **04_search.py** - Basic Semantic Search

**Purpose:** Interactive semantic search using FAISS

**Key Functions:**
- `load_metadata(path)` - Load occupation metadata
- `load_index(path)` - Load FAISS index
- `embed_query(query, model)` - Encode user query
- `search(query)` - Perform top-K search:
  - Load all data on each query (inefficient)
  - Query → embedding → FAISS search
  - Display top-5 results

**Strengths:**
- Simple, easy to understand
- Interactive loop for testing
- Displays NCO codes and confidence scores

**Weaknesses:**
- **Critical:** Reloads entire index/model/metadata on each query
- No result ranking or scoring
- Hardcoded TOP_K=5
- Model loaded in search function (inefficient)
- No error handling for empty queries
- No result filtering or confidence threshold

**Search Flow:**
```
Query Input
  → Embed query with SBERT
  → FAISS top-K search (top-5)
  → Return raw scores [0-1]
  → Display results
```

---

### 1.5 **05_searchGN.py** - Graph Network Construction

**Purpose:** Build simple keyword-based graph from documents

**Key Functions:**
- Load metadata and documents
- Extract keywords from document text using regex
- Build sector information from division text
- Create graph JSON with nodes: `{code: {sector, keywords}}`

**Graph Structure:**
```json
{
  "1111": {
    "sector": "Professionals",
    "keywords": ["officer", "administrator", ...]
  },
  ...
}
```

**Strengths:**
- Lightweight approach
- No external graph library dependencies

**Weaknesses:**
- **Very primitive:** Just keyword extraction + regex parsing
- No actual graph relationships
- Keywords extracted using simple word splitting
- Sector extracted by parsing text (fragile)
- No hierarchy representation
- No relationship types
- Output is flat key-value, not graph structure
- Limited usefulness for actual graph queries

**Graph Output:**
```
nco_graph.json (flat dictionary, not a real graph)
```

---

### 1.6 **06_searchapp.py** - Hybrid Search Orchestrator

**Purpose:** Advanced search combining semantic + graph scoring with custom boosting

**Architecture:**
- Loads all data at startup (good for performance)
- Maintains 3 indices:
  1. FAISS full-document index
  2. FAISS title-only index
  3. CSV job details lookup table

**Key Search Components:**

**Step 1: Dual Index Search**
```python
# Search both full documents and titles separately
- Full index: semantic_score (normalized embedding match)
- Title index: title_score (occupation title relevance)
```

**Step 2: Graph Scoring**
```python
gn_score = keyword overlap / total_keywords
(Compute how many query words match occupation keywords)
```

**Step 3: Score Combining**
```python
base_score = ALPHA * semantic_score + BETA * gn_score
  where: ALPHA=0.7, BETA=0.3
  
boosted = base_score * 1.8  # Global multiplier

# Title-based boost (very aggressive)
if title_clean == query_clean or title_words ⊆ query_words:
    boost_factor = 1.6
elif overlap_exists:
    boost_factor = 1.25

semantic_final = boosted * boost_factor
title_final = title_score * 1.15
final_score = min(max(semantic_final, title_final), 1.0)
```

**Step 4: Confidence Threshold**
- Checks if top result score < 0.45
- Shows warning if confidence too low

**Strengths:**
- **Sophisticated hybrid approach**
- Multiple scoring dimensions (semantic + graph + title)
- Upfront data loading (startup cost, fast queries)
- Title index separate (helps short queries)
- Aggressive tuning for NCO domain (works well for occupation data)
- Confidence threshold feedback
- Detailed result display with hierarchy

**Weaknesses:**
- **Extremely hardcoded tuning:** 7 magic numbers (ALPHA, BETA, multipliers, threshold)
- No configuration file (would require code changes to tune)
- Complex scoring logic with unclear parameter interactions
- Title boost logic convoluted and fragile
- Custom P.I.G.S. system (Prompt Intelligence & Guidance) mixed in
- Difficult to debug or replicate results
- No proper error handling
- Result display tightly coupled to CLI

**Ranking Pipeline (Simplified):**
```
Candidates (from FAISS)
  → Add semantic_score + title_score + gn_score
  → Combine scores with magic weights
  → Apply title-based boost
  → Cap at 1.0
  → Sort by final_score
  → Return top-K
```

**Search Configuration (Hardcoded):**
```python
TOP_K = 5
MAX_TOP_K = 100
CANDIDATE_K = 50          # Pre-filter from FAISS
TITLE_CANDIDATE_K = 50    # Pre-filter title index
CONFIDENCE_THRESHOLD = 0.45
ALPHA = 0.7               # Semantic weight
BETA = 0.3                # Graph weight
# Plus 3 multipliers: 1.8, 1.6, 1.25, 1.15
```

---

## PART 2: NEW IMPLEMENTATION (src/ folder)

### Architecture Overview

Modular package structure with clear separation of concerns:

```
src/
├── ingestion/           (Data preparation & embeddings)
│   ├── preparation.py          (DocumentPreparationService)
│   ├── embedding_generator.py  (EmbeddingGenerationService)
│   └── faiss_builder.py        (FaissIndexBuilder)
│
├── retrieval/           (Search & retrieval engines)
│   ├── semantic_search.py      (SemanticSearch)
│   ├── query_engine.py         (QueryEngine - orchestrator)
│   └── hybrid_search.py        (HybridSearch - combines sources)
│
├── models/              (AI models)
│   ├── embedding_model.py      (EmbeddingModel - singleton)
│   └── reranker.py             (Reranker - CrossEncoder)
│
├── graph/               (Knowledge graph)
│   ├── knowledge_graph_builder.py  (NCOKnowledgeGraphBuilder)
│   ├── graph_schema.py             (Node/relationship schema)
│   └── graph_search.py             (GraphSearch - queries)
│
└── utils/
    ├── config.py        (Centralized configuration)
    └── logger.py
```

### 2.1 **src/ingestion/preparation.py** - Enhanced Data Preparation

**Class:** `DocumentPreparationService`

**Features:**
- Schema validation (checks all required columns present)
- Data quality tracking
- Rich metadata extraction
- Structured dataclass output: `PreparationStats`

**Key Methods:**
```python
load_dataset()          # Validates file existence, reads CSV
validate_schema(df)     # Ensures all required columns present
clean_text(value)       # Normalize text (handle NaN, whitespace)
build_document(row)     # Create enriched document text
build_metadata(row, id) # Create structured metadata
create_outputs(df)      # Process entire dataset
validate_outputs()      # Verify document/metadata alignment
process()               # Main orchestration method
```

**Required Columns:**
```python
S No, Occupational Title, NCO 2015, NCO 2004,
Division, Sub Division, Group, Family,
Division Description, Sub Division Description,
Group Description, Family Description,
Occupation Description
```

**Output Validation:**
- Document count = metadata count
- No missing NCO codes tracking
- No missing titles tracking
- Comprehensive stats reporting

**Strengths:**
- ✅ Schema validation (prevents silent failures)
- ✅ Structured error reporting
- ✅ Data quality metrics
- ✅ Comprehensive metadata (14 fields)
- ✅ Better text normalization (preserves logical spacing)
- ✅ Dataclass stats for tracking

**Weaknesses:**
- ⚠️ More verbose than old version
- ⚠️ Higher cognitive load for simple use case

**Data Flow:**
```
NCO CSV (v6_final)
  → Schema validation
  → Text cleaning + document building
  → Output validation
  → 2 JSON files:
    - nco_documents.json
    - nco_metadata.json (14 fields)
```

---

### 2.2 **src/ingestion/embedding_generator.py** - Robust Embedding Generation

**Class:** `EmbeddingGenerationService`

**Features:**
- Dependency injection of embedding model
- Comprehensive validation
- Batch size configuration
- Output dataclass: `EmbeddingStats`

**Key Methods:**
```python
load_documents()        # Validates format & content
generate_embeddings()   # Batch encode with progress bar
validate_embeddings()   # Check shape, NaN, Inf
save_embeddings()       # Save .npy file
```

**Validations:**
```python
✅ Document file exists
✅ JSON format is correct (list of strings)
✅ No empty documents
✅ Embeddings are 2D NumPy array
✅ No NaN values
✅ No Inf values
✅ Document/embedding count match
✅ Non-zero embedding dimension
```

**Configuration:**
```python
DEFAULT_BATCH_SIZE = 32
# Model injected from EmbeddingModel singleton
```

**Strengths:**
- ✅ Extensive error checking (10+ validations)
- ✅ Configurable batch size
- ✅ Dependency injection pattern
- ✅ Clear error messages
- ✅ Progress tracking via stats

**Weaknesses:**
- ⚠️ More boilerplate code
- ⚠️ Dependency on EmbeddingModel singleton

---

### 2.3 **src/ingestion/faiss_builder.py** - Index Construction

**Class:** `FaissIndexBuilder`

**Features:**
- Comprehensive validation
- Verification of saved index
- Output dataclass: `FaissStats`

**Key Methods:**
```python
load_embeddings()           # Load .npy + validate
validate_embeddings()       # 5-point validation
build_index()               # Create IndexFlatIP
save_index()                # Save to disk
verify_saved_index()        # Post-save validation
```

**Validations:**
```python
✅ File exists
✅ Is NumPy array
✅ Is 2D
✅ Has vectors (shape[0] > 0)
✅ Has dimensions (shape[1] > 0)
✅ No NaN values
✅ No Inf values
```

**Strengths:**
- ✅ Thorough validation
- ✅ Post-save verification
- ✅ Clear error messages
- ✅ Defensive programming

**Weaknesses:**
- ⚠️ Same IndexFlatIP as old version (not scalable for large datasets)
- ⚠️ No index optimization options

---

### 2.4 **src/models/embedding_model.py** - Model Management

**Class:** `EmbeddingModel` (Singleton Pattern)

**Features:**
- Lazy loading (only when needed)
- Singleton ensures single model instance
- Encoding methods for queries and documents

**Key Methods:**
```python
__new__()               # Singleton pattern implementation
encode()                # Encode texts with normalization
encode_query()          # Single query encoding
encode_documents()      # Batch document encoding
```

**Model:** BAAI/bge-small-en-v1.5 (128-dim)

**Strengths:**
- ✅ Efficient resource usage (single model instance)
- ✅ Lazy loading reduces startup time
- ✅ Consistent embedding handling

**Weaknesses:**
- ⚠️ Hardcoded model in config
- ⚠️ No model swapping capability
- ⚠️ Singleton pattern makes testing harder

---

### 2.5 **src/models/reranker.py** - Result Reranking

**Class:** `Reranker`

**Purpose:** Use CrossEncoder to rerank semantic search results

**Features:**
- Uses MS MARCO MiniLM reranker (cross-encoder/ms-marco-MiniLM-L-6-v2)
- Takes query + candidate pairs
- Returns reranked results with scores

**Key Methods:**
```python
__init__()              # Load CrossEncoder model
rerank()                # Rerank candidates, return top-K
```

**Strengths:**
- ✅ **NOT in OLD implementation**
- ✅ Significantly improves result quality
- ✅ MiniLM is fast (6 layers)
- ✅ MARCO trained (good for ranking)

**Weaknesses:**
- ⚠️ Additional computational cost
- ⚠️ Requires paired comparisons

**Unique Feature:** This is a **major advantage** over the old implementation.

---

### 2.6 **src/graph/graph_schema.py** - Graph Data Model

**Classes/Functions:**
- `GraphNode` (frozen dataclass): node_id, node_type, label
- `clean_text()`: Text normalization
- `build_node_id()`: Generate unique node identifiers
- `create_node()`: Factory method

**Node Types:**
```python
Division, SubDivision, Group, Family, Occupation
```

**Node ID Format:**
```python
"Division:Public Administration"
"SubDivision:Civil Services"
"Group:Officers"
"Family:Administrative Officers"
"Occupation:1111" (NCO code)
```

**Strengths:**
- ✅ Clean data model
- ✅ Immutable nodes (frozen dataclass)
- ✅ Type safety
- ✅ Factory pattern

---

### 2.7 **src/graph/knowledge_graph_builder.py** - Graph Construction

**Class:** `NCOKnowledgeGraphBuilder`

**Purpose:** Build hierarchical knowledge graph from NCO data

**Features:**
- Uses NetworkX DiGraph
- Builds proper hierarchy relationships
- Multiple export formats (JSON, GraphML, GEXF)

**Key Methods:**
```python
build_from_dataframe()      # Main graph construction
add_node()                  # Add node to graph
add_relationship()          # Add edge to graph
save_graph_json()           # Export to JSON
save_graph_graphml()        # Export GraphML format
save_graph_gexf()           # Export GEXF format
visualize_graph()           # Create HTML visualization
```

**Graph Structure:**
```
Division
  ↓ HAS_SUBDIVISION
SubDivision
  ↓ HAS_GROUP
Group
  ↓ HAS_FAMILY
Family
  ↓ HAS_OCCUPATION
Occupation
```

**Example Path:**
```
"Division:Professionals"
  → "SubDivision:Science and Engineering"
    → "Group:Engineers"
      → "Family:Mechanical Engineers"
        → "Occupation:2143"
```

**Strengths:**
- ✅ **TRUE hierarchical graph** (vs OLD's flat keywords)
- ✅ Proper relationship types
- ✅ Full hierarchy representation
- ✅ Multiple export formats
- ✅ Visualization support (HTML)
- ✅ Uses standard NetworkX library

**Weaknesses:**
- ⚠️ Higher memory usage (full graph in memory)
- ⚠️ NetworkX not optimized for very large graphs

---

### 2.8 **src/graph/graph_search.py** - Graph Traversal

**Class:** `GraphSearch`

**Purpose:** Query graph relationships and find connected occupations

**Key Methods:**
```python
load_graph()                # Load graph from JSON
find_node()                 # Search by keyword
get_parent()                # Get direct parent
get_children()              # Get direct children
get_full_hierarchy()        # Get path from root to node
get_ancestors()             # Get all ancestors
get_descendants()           # Get all descendants
get_siblings()              # Get sibling nodes
get_family_occupations()    # Get all occupations in family
```

**Strengths:**
- ✅ Rich graph query API
- ✅ Supports multiple traversal patterns
- ✅ Uses NetworkX algorithms (efficient)

**Example Query:**
```python
hierarchy = graph.get_full_hierarchy("Occupation:2143")
# Returns: ["Division:Professionals", ..., "Occupation:2143"]

siblings = graph.get_siblings("Occupation:2143")
# Returns: Other occupations in same family
```

---

### 2.9 **src/retrieval/semantic_search.py** - FAISS Search

**Class:** `SemanticSearch`

**Features:**
- Lazy loading of index/metadata
- Comprehensive validation
- Result dataclass: `SemanticSearchResult`

**Key Methods:**
```python
load_index()                        # Load FAISS index
load_metadata()                     # Load metadata
validate_index_metadata_alignment() # Cross-check consistency
embed_query()                       # Query embedding
search()                            # Perform top-K search
```

**Search Flow:**
```
Query Input
  → Validate non-empty
  → Embed query (normalized)
  → FAISS top-K search
  → Reconstruct documents from metadata
  → Return results with score + metadata
```

**Validation Points:**
- Query is non-empty
- Index loaded successfully
- Metadata loaded successfully
- Index/metadata counts match
- Embeddings have no NaN/Inf

**Strengths:**
- ✅ Pure semantic search (FAISS)
- ✅ Clean, focused class
- ✅ Comprehensive validation
- ✅ Returns rich result objects

**Weaknesses:**
- ⚠️ Still uses inefficient IndexFlatIP (same as OLD)
- ⚠️ No semantic optimizations

---

### 2.10 **src/retrieval/hybrid_search.py** - Multi-Source Fusion

**Class:** `HybridSearch`

**Purpose:** Combine semantic search + graph context

**Key Methods:**
```python
search()                    # Fuse semantic + graph
get_hierarchy()             # Get occupation hierarchy
get_siblings()              # Get sibling occupations
```

**Search Flow:**
```
Query Input
  ↓
  └→ SemanticSearch.search()
       ↓
       Returns: [result1, result2, ...]
       ↓
       For each result:
         ├→ GraphSearch.get_full_hierarchy()
         └→ GraphSearch.get_siblings()
       ↓
       Enrich with hierarchy + siblings
  ↓
  Return enriched results
```

**Output Format:**
```json
{
  "occupation_title": "Software Engineer",
  "nco_code": "2143",
  "semantic_score": 0.95,
  "document": "...",
  "metadata": {...},
  "hierarchy": ["Division:...", "...", "Occupation:2143"],
  "siblings": ["Occupation:2144", "Occupation:2145"]
}
```

**Strengths:**
- ✅ Cleanly separates semantic + graph
- ✅ Enriches results with context
- ✅ Simple error handling (return empty on graph error)

**Weaknesses:**
- ⚠️ No score fusion (graph not included in ranking)
- ⚠️ Hierarchy/siblings are context only, not reranking
- ⚠️ Simple filtering (not sophisticated like OLD's hybrid)

---

### 2.11 **src/retrieval/query_engine.py** - Orchestrator

**Class:** `QueryEngine`

**Purpose:** User-facing search interface

**Key Methods:**
```python
search()                    # Get results
display()                   # Print formatted results
```

**Flow:**
```
User Query
  → QueryEngine.search()
    → HybridSearch.search()
      → SemanticSearch + GraphSearch
    → Format results
  → Return to user
```

**Result Format:**
```json
{
  "occupation_title": "...",
  "nco_code": "...",
  "confidence": 0.95,
  "hierarchy": [...]
}
```

**Strengths:**
- ✅ Clean CLI interface
- ✅ Separation between logic and presentation

**Weaknesses:**
- ⚠️ Limited ranking sophistication (no score tuning)

---

### 2.12 **src/utils/config.py** - Centralized Configuration

**Features:**
- All constants in one file
- Path management using pathlib.Path
- Easy to modify without code changes

**Configuration Categories:**
```python
# Paths
DATA_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR
NCO_CSV_PATH, DOCUMENTS_PATH, METADATA_PATH
MODELS_DIR, EMBEDDINGS_PATH, FAISS_INDEX_PATH
GRAPH_DIR, GRAPH_JSON_PATH, HTML_VISUALIZATION_PATH

# Models
EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"

# Search
TOP_K_RESULTS = 10
SEMANTIC_WEIGHT = 0.70
GRAPH_WEIGHT = 0.30

# Graph Schema
NODE_DIVISION, NODE_SUBDIVISION, NODE_GROUP, NODE_FAMILY, NODE_OCCUPATION
REL_HAS_SUBDIVISION, REL_HAS_GROUP, REL_HAS_FAMILY, REL_HAS_OCCUPATION
```

**Strengths:**
- ✅ All constants in one place
- ✅ Easy to modify
- ✅ Using pathlib.Path (cross-platform)
- ✅ Centralized configuration

**Weaknesses:**
- ⚠️ Weights are defined but not used in search (hardcoded to 0.70/0.30)
- ⚠️ No dynamic configuration loading

---

## PART 3: DETAILED COMPARISON

### 3.1 Code Organization & Modularity

| Aspect | OLD | NEW |
|--------|-----|-----|
| **Files** | 6 scripts | 12+ classes across packages |
| **Separation** | Sequential pipeline | Package-based (ingestion/retrieval/models/graph) |
| **Reusability** | Limited | High (service classes) |
| **Coupling** | Tight (direct file I/O) | Loose (dependency injection) |
| **Testability** | Poor (scripts) | Good (classes with clear APIs) |
| **Code Reuse** | Copy-paste | Import services |

**Winner:** NEW (significant improvement)

---

### 3.2 Architecture Patterns

#### OLD Approach: Procedural Pipeline
```python
# Each script does one thing in sequence
script1.py → load CSV → process → save JSON
script2.py → load JSON → embed → save embeddings
script3.py → load embeddings → build index → save
script4.py → load index → search → display
script6.py → orchestrate all with complex logic
```

#### NEW Approach: Service Objects
```python
# Classes encapsulate logic + state
prep_service = DocumentPreparationService()
prep_service.process()  # Returns PreparationStats

embedding_service = EmbeddingGenerationService()
embeddings = embedding_service.generate_embeddings(docs)

search_engine = HybridSearch()
results = search_engine.search("Software Engineer")
```

**Winner:** NEW (object-oriented, more maintainable)

---

### 3.3 Data Flow

#### OLD Implementation
```
CSV
  ↓ (01_preparation)
Documents JSON + Metadata JSON
  ↓ (02_generateEmbedding)
Embeddings .npy
  ↓ (03_build_faiss_index)
FAISS Index
  ↓ (04/05/06_search)
Results (with display)
```

#### NEW Implementation
```
CSV
  ↓ (DocumentPreparationService)
Documents JSON + Metadata JSON
  ↓ (EmbeddingGenerationService + EmbeddingModel singleton)
Embeddings .npy
  ↓ (FaissIndexBuilder)
FAISS Index
  ↓ (NCOKnowledgeGraphBuilder)
Graph JSON → GraphSearch
  ↓
SemanticSearch + GraphSearch
  ↓ (HybridSearch)
Enriched Results ← QueryEngine
```

**Winner:** NEW (cleaner, with proper separation)

---

### 3.4 Search Functionality

#### OLD (06_searchapp.py)
**Approach:** Aggressive hybrid scoring with domain tuning
```python
# 1. Dual FAISS search (full docs + titles)
semantic_score = full_doc_match
title_score = title_match

# 2. Graph scoring
gn_score = keyword_overlap

# 3. Complex combination
base_score = 0.7 * semantic + 0.3 * gn
boosted = base_score * 1.8
title_boost = 1.6 or 1.25 or 1.0
final = clamp(boosted * boost)

# 4. Confidence check (< 0.45 = warning)
# 5. P.I.G.S. analysis (hierarchy match quality)
```

**Pros:**
- ✅ Heavily optimized for NCO occupation domain
- ✅ Works very well in practice
- ✅ Smart title boosting for short queries
- ✅ Confidence feedback to user

**Cons:**
- ❌ 7+ magic numbers (not reproducible)
- ❌ Complex tuning interactions
- ❌ No configuration file
- ❌ Hard to debug or modify

#### NEW (HybridSearch + QueryEngine)
**Approach:** Semantic + graph context enrichment
```python
# 1. Semantic search (FAISS)
semantic_results = semantic_search.search()

# 2. Enrich with graph context
for result in semantic_results:
    hierarchy = graph.get_full_hierarchy()
    siblings = graph.get_siblings()
    result['hierarchy'] = hierarchy
    result['siblings'] = siblings

# 3. Return enriched results (no reranking)
```

**Pros:**
- ✅ Clean separation of concerns
- ✅ Graph provides context/relationships
- ✅ Includes reranker capability (not used)
- ✅ Extensible architecture

**Cons:**
- ❌ No score fusion (graph not affecting ranking)
- ❌ Less optimized than OLD
- ❌ Hierarchy/siblings don't affect ranking

**Verdict:** OLD is more sophisticated in search. NEW is more general-purpose but less tuned for this domain.

---

### 3.5 Knowledge Graph Implementation

#### OLD (05_searchGN.py)
**What it does:**
```python
# For each occupation:
# 1. Extract keywords using regex
keywords = re.findall(r'\b[a-z]{3,}\b', desc)

# 2. Extract sector from division text
sector = "extract from document text"

# 3. Create flat dictionary
{
  "1111": {
    "sector": "Professionals",
    "keywords": ["officer", "administrator", ...]
  },
  ...
}
```

**Problems:**
- ❌ Not a real graph (flat key-value dict)
- ❌ No relationships between occupations
- ❌ Keyword extraction is naive (regex on lowercase text)
- ❌ Sector extracted by fragile text parsing
- ❌ No hierarchy representation
- ❌ Cannot answer: "What's the parent of this occupation?"

#### NEW (knowledge_graph_builder.py + graph_search.py)
**What it does:**
```
# Build proper directed graph with 5 levels:
Division
  ↓ HAS_SUBDIVISION
SubDivision
  ↓ HAS_GROUP
Group
  ↓ HAS_FAMILY
Family
  ↓ HAS_OCCUPATION
Occupation

# Can answer queries:
- get_full_hierarchy(occupation) → [Div, SubDiv, Group, Fam, Occ]
- get_siblings(occupation) → [other occupations in same family]
- get_family_occupations(family) → all occupations
- find_node(keyword) → search by name
- get_ancestors/descendants
```

**Advantages:**
- ✅ True hierarchical graph
- ✅ Proper relationship types
- ✅ Can traverse relationships
- ✅ Multiple query methods
- ✅ Visualization support (HTML)
- ✅ Multiple export formats (JSON, GraphML, GEXF)
- ✅ Standard NetworkX library

**Verdict:** NEW is drastically better. OLD's "graph" is not really a graph.

---

### 3.6 Error Handling

#### OLD
- ❌ Minimal error checking
- ❌ Silent failures (missing columns not caught)
- ❌ File not found errors not handled
- ❌ Invalid data not validated
- ❌ Only basic exception handling

#### NEW
- ✅ Comprehensive validation
- ✅ Specific error messages
- ✅ Data quality checks
- ✅ Upfront schema validation
- ✅ Embedding validation (NaN/Inf)
- ✅ Index/metadata alignment checks
- ✅ Try-catch in critical sections

**Winner:** NEW (significantly better)

---

### 3.7 Configuration Management

#### OLD
```python
# Hardcoded throughout files
INPUT_CSV = "data/raw/nco_dataset_v3.csv"
OUTPUT_JSON = "data/processed/nco_documents.json"
MODEL_NAME = "BAAI/bge-small-en-v1.5"
ALPHA = 0.7
BETA = 0.3
# Plus 5 more magic numbers in 06_searchapp.py
```

**Problems:**
- ❌ Constants scattered across files
- ❌ Magic numbers mixed with code
- ❌ Hard to maintain
- ❌ Difficult to experiment with parameters

#### NEW
```python
# Centralized config.py
NCO_CSV_PATH = "data/raw/nco_dataset_v6_final.csv"
DOCUMENTS_PATH = "data/processed/nco_documents.json"
EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
TOP_K_RESULTS = 10
SEMANTIC_WEIGHT = 0.70
GRAPH_WEIGHT = 0.30
```

**Advantages:**
- ✅ Single configuration file
- ✅ Easy to modify
- ✅ Clear separation of config from code
- ⚠️ But weights not actually used in search

**Winner:** NEW (better organization)

---

### 3.8 Scalability

#### OLD
- Large NCO dataset (1000+ occupations): Works fine
- Millions of documents: Would struggle (full O(N) search in IndexFlatIP)
- Real-time search: Acceptable (loads model each time)
- Memory usage: Moderate (full model + index in memory)

#### NEW
- Same limitations as OLD
- Same IndexFlatIP approach
- Better structured for potential improvements
- Lazy loading helps startup time

**Verdict:** Similar limitations, but NEW has better foundation for optimization.

---

### 3.9 Performance Characteristics

#### Index Search Time (FAISS)
Both use IndexFlatIP with inner product:
- Time complexity: O(N) where N = number of vectors
- For ~1000 occupations: ~1-5ms per query
- Both acceptable for this dataset size

#### Memory Usage
| Component | OLD | NEW |
|-----------|-----|-----|
| Model | ~300MB | ~300MB (singleton) |
| FAISS Index | ~2MB | ~2MB |
| Metadata | ~5MB | ~5MB |
| Graph | Minimal | ~10-20MB (full NetworkX graph) |
| **Total** | ~307MB | ~315-325MB |

**Winner:** OLD (slightly lighter), but difference negligible

---

### 3.10 Dependencies

#### OLD
```
pandas
numpy
faiss-cpu
sentence-transformers
```
**Total:** 4 main packages (plus their dependencies)

#### NEW
```
pandas
numpy
faiss-cpu
sentence-transformers
networkx  # NEW: graph support
```
**Total:** 5 main packages (plus their dependencies)

**Difference:** NEW adds NetworkX (~2MB)

**Winner:** OLD (fewer dependencies), but NEW's addition is well-justified

---

### 3.11 Testing & Debugging

#### OLD
- Cannot easily unit test (scripts, no classes)
- Integration testing only
- Hard to mock data/dependencies
- Difficult to test individual components

#### NEW
- Service classes can be unit tested
- Mock metadata/index easily
- Test each service independently
- Dependency injection enables testing

**Example NEW test:**
```python
@unittest.mock.patch('src.models.embedding_model.EmbeddingModel')
def test_semantic_search(mock_model):
    search = SemanticSearch(...)
    results = search.search("query")
    assert len(results) > 0
```

**Winner:** NEW (much better testability)

---

### 3.12 Feature Completeness

| Feature | OLD | NEW |
|---------|-----|-----|
| Semantic search | ✅ | ✅ |
| FAISS indexing | ✅ | ✅ |
| Keyword-based "graph" | ✅ (primitive) | ✅ (true graph) |
| Hybrid scoring | ✅ (tuned) | ⚠️ (no fusion) |
| Reranking | ❌ | ✅ (CrossEncoder) |
| Graph traversal | ❌ | ✅ |
| Hierarchy queries | ❌ | ✅ |
| Visualization | ❌ | ✅ (HTML export) |
| Configuration | ⚠️ (hardcoded) | ✅ (config.py) |
| Error handling | ❌ | ✅ |
| Data validation | ⚠️ (minimal) | ✅ |
| **Total Features** | 3 | **10+** |

**Winner:** NEW (more comprehensive)

---

### 3.13 Maintainability Scorecard

| Aspect | Score (1-10) |
|--------|--------------|
| **Code Organization** | OLD: 3, NEW: 9 |
| **Error Handling** | OLD: 2, NEW: 9 |
| **Configuration** | OLD: 3, NEW: 8 |
| **Documentation** | OLD: 4, NEW: 5 |
| **Testability** | OLD: 2, NEW: 8 |
| **Extensibility** | OLD: 2, NEW: 8 |
| **Performance Clarity** | OLD: 6, NEW: 7 |
| **Learning Curve** | OLD: 8 (simple), NEW: 5 (complex) |
| **AVERAGE** | **OLD: 3.75** | **NEW: 7.4** |

---

## PART 4: STRENGTHS & WEAKNESSES

### OLD Implementation (scripts/)

**STRENGTHS:**
1. ✅ **Domain-optimized:** Heavily tuned parameters work very well for NCO data
2. ✅ **Simple to understand:** Sequential scripts are easy to follow
3. ✅ **Minimal dependencies:** Only 4 core packages
4. ✅ **Fast startup:** No complex initialization
5. ✅ **Good search quality:** Hybrid approach with intelligent boosting
6. ✅ **Title/semantic dual indexing:** Separate indices for different query types
7. ✅ **Confidence feedback:** P.I.G.S. system gives user insights
8. ✅ **Production-ready:** Has been working well in practice

**WEAKNESSES:**
1. ❌ **Not maintainable:** Hard to modify parameters
2. ❌ **Not testable:** Scripts can't be unit tested
3. ❌ **Hardcoded magic numbers:** 7+ parameters mixed with code
4. ❌ **Fragile graph:** Simple keyword extraction doesn't scale
5. ❌ **No configuration file:** Would need code edits to tune
6. ❌ **Error handling:** Minimal validation
7. ❌ **Poor code reuse:** Each script isolated
8. ❌ **Complex logic:** Scoring algorithm convoluted and hard to debug
9. ❌ **No true hierarchy:** "Graph" is just keywords
10. ❌ **Not extensible:** Adding features means editing core logic

---

### NEW Implementation (src/)

**STRENGTHS:**
1. ✅ **Well-organized:** Package structure with clear concerns
2. ✅ **Testable:** Service classes can be unit tested
3. ✅ **Maintainable:** Easy to modify or extend
4. ✅ **True knowledge graph:** Proper hierarchical graph with relationships
5. ✅ **Better error handling:** Comprehensive validation
6. ✅ **Reranking capability:** CrossEncoder for result refinement
7. ✅ **Configuration management:** Centralized config.py
8. ✅ **Graph traversal API:** Rich query methods
9. ✅ **Visualization:** HTML graph export
10. ✅ **Extensible:** Easy to add new features
11. ✅ **Data quality metrics:** Tracks validation stats
12. ✅ **Better documentation potential:** Classes have clear APIs

**WEAKNESSES:**
1. ❌ **More complex:** Higher cognitive load
2. ❌ **Heavyweight:** Adds NetworkX dependency
3. ❌ **Startup overhead:** More initialization
4. ❌ **Less optimized:** Search not tuned for NCO domain
5. ❌ **Graph not used in ranking:** Hierarchy/siblings are context only
6. ❌ **No score fusion:** Simple concatenation, not intelligent combination
7. ⚠️ **Configuration not used:** Weights defined but hardcoded to 0.70/0.30
8. ⚠️ **Larger memory footprint:** Graph data structure adds overhead
9. ❌ **Same FAISS limitations:** Still uses IndexFlatIP, not scalable to millions
10. ⚠️ **Reranker not integrated:** CrossEncoder available but not used

---

## PART 5: RECOMMENDATIONS

### When to Use OLD Implementation
- ✅ Small NCO dataset (~1-10K occupations)
- ✅ Production system with stable requirements
- ✅ Need maximum performance for domain
- ✅ Team wants simple, transparent logic
- ✅ Not planning major changes

### When to Use NEW Implementation
- ✅ Planning significant enhancements
- ✅ Need maintainability over optimization
- ✅ Want true graph capabilities
- ✅ Building larger system with multiple components
- ✅ Team values code quality and testability

### HYBRID Approach (Best of Both)
1. **Keep NEW's organization** (ingestion/retrieval/models/graph structure)
2. **Integrate OLD's scoring logic** (move tuned parameters to config)
3. **Use NEW's graph properly** (integrate in ranking, not just context)
4. **Enable reranking** (activate CrossEncoder in HybridSearch)
5. **Implement proper score fusion** (combine semantic + graph scores)

**Pseudo-code for improved hybrid:**
```python
class ImprovedHybridSearch:
    def search(query, top_k):
        # Get semantic results
        semantic = self.semantic_search.search(query, top_k * 2)
        
        # Score with graph
        for result in semantic:
            occ_id = f"Occupation:{result['nco_code']}"
            hierarchy_depth = len(self.graph.get_full_hierarchy(occ_id))
            result['hierarchy_score'] = calculate_hierarchy_relevance(
                hierarchy_depth,
                query
            )
        
        # Rerank with CrossEncoder
        reranked = self.reranker.rerank(query, semantic, top_k)
        
        # Combine scores (configurable)
        for result in reranked:
            result['final_score'] = (
                SEMANTIC_WEIGHT * result['semantic_score'] +
                GRAPH_WEIGHT * result['hierarchy_score'] +
                RERANK_WEIGHT * result['rerank_score']
            )
        
        return sorted(reranked, key='final_score')[:top_k]
```

---

## PART 6: MIGRATION STRATEGY

### Phase 1: Setup (Week 1)
- Install NEW infrastructure alongside OLD
- Configure both systems to use same data
- Run validation tests

### Phase 2: Gradual Adoption (Weeks 2-4)
- Migrate ingestion to NEW (prep + embedding + FAISS)
- Keep search hybrid (compare results)
- Tune NEW's parameters
- Train team on NEW architecture

### Phase 3: Integration (Weeks 5-6)
- Integrate graph properly into ranking
- Activate reranker
- Test performance vs OLD
- Document API differences

### Phase 4: Cutover (Week 7)
- Switch production to NEW
- Archive OLD for fallback
- Monitor performance

---

## SUMMARY TABLE

| Dimension | OLD | NEW | Best |
|-----------|-----|-----|------|
| Code Organization | 2/10 | 9/10 | NEW |
| Error Handling | 2/10 | 8/10 | NEW |
| Maintainability | 3/10 | 8/10 | NEW |
| Performance | 8/10 | 6/10 | OLD* |
| Search Quality | 9/10 | 6/10 | OLD |
| Features | 3/10 | 9/10 | NEW |
| Testability | 2/10 | 8/10 | NEW |
| Extensibility | 2/10 | 8/10 | NEW |
| Dependencies | 9/10 | 8/10 | OLD |
| Graph Quality | 2/10 | 9/10 | NEW |
| Configuration | 2/10 | 8/10 | NEW |
| **AVERAGE** | 4.2/10 | 7.8/10 | **NEW** |

**Note:** OLD performs better on domain-specific optimization. NEW is better for everything else.

---

## CONCLUSION

The **NEW implementation is superior from a software engineering perspective**, providing better code organization, maintainability, error handling, and extensibility. However, the **OLD implementation has better search quality** due to domain-specific tuning.

**Recommendation:** Adopt NEW's architecture while incorporating OLD's search optimization strategy. This would combine the best of both approaches.

