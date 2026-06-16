# NCO Search Engine API

Standalone deployable API extracted from the Eureka NCO occupation search project. The main project is **unchanged** — this folder is a self-contained copy for Docker deployment and independent use.

## What's included

### Full data pipeline

| Step | Script | Output |
|------|--------|--------|
| 1 | `scripts/01_preparation.py` | `nco_documents.json`, `nco_metadata.json` |
| 2 | `scripts/05_searchGN.py` | `nco_graph.json` (graph network keywords) |
| 3 | `scripts/02_generateEmbedding.py` | `nco_embeddings.npy` |
| 4 | `scripts/03_build_faiss_index.py` | `nco_faiss.index` |

Run all steps at once:

```bash
cd search-engine-api
python run_pipeline.py
```

Or run individual steps from the `search-engine-api` root:

```bash
python scripts/01_preparation.py
python scripts/05_searchGN.py
python scripts/02_generateEmbedding.py
python scripts/03_build_faiss_index.py
```

### Search runtime

| Script | Purpose |
|--------|---------|
| `scripts/06_searchapp.py` | Core search engine (FAISS + GN reranking + PIGS) |
| `scripts/04_search.py` | CLI test for basic FAISS search |
| `api.py` | Flask REST API |

### Utilities

- `utils/translation_service.py` — multilingual query translation
- `utils/dynamic_prompts.py` — search suggestion prompts

## API endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| POST | `/api/search` | Search occupations |
| POST | `/api/translate` | Translate text |
| GET | `/api/languages` | Supported languages |

### Search examples

```bash
# Semantic search
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "plumber", "top_k": 5}'

# NCO code lookup
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "7215.0100", "search_mode": "nco"}'

# Hindi query with language hint
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "शिक्षक", "user_language": "hi", "top_k": 5}'
```

## Quick start (local)

```bash
cd search-engine-api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Optional: rebuild search assets from CSV
python run_pipeline.py

# Start API
python api.py
```

## Docker deployment

Pre-built models and data are included, so the container works without running the pipeline first.

```bash
cd search-engine-api
docker build -t nco-search-api .
docker run -p 5000:5000 nco-search-api
```

Or with Docker Compose:

```bash
docker compose up --build
```

To rebuild assets inside a running container (e.g. after updating the CSV):

```bash
docker exec -it <container_id> python run_pipeline.py
docker restart <container_id>
```

First startup may take 1–2 minutes while the embedding model loads.

## Test scripts

```bash
# Test API search accuracy (API must be running)
python scripts/test_queries.py

# Validate pipeline outputs and data integrity
python scripts/test_implementation.py
```

## Folder structure

```
search-engine-api/
├── api.py                    # Flask API entrypoint
├── run_pipeline.py           # Full pipeline orchestrator
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── scripts/
│   ├── 01_preparation.py     # CSV → documents + metadata
│   ├── 02_generateEmbedding.py
│   ├── 03_build_faiss_index.py
│   ├── 04_search.py          # CLI search test
│   ├── 05_searchGN.py        # Graph network builder
│   ├── 06_searchapp.py       # Core search engine
│   ├── test_queries.py
│   └── test_implementation.py
├── utils/
├── data/
│   ├── raw/nco_dataset_v3.csv
│   └── processed/
└── models/
    ├── nco_embeddings.npy
    └── nco_faiss.index
```

## Pipeline flow

```
nco_dataset_v3.csv
       │
       ▼
01_preparation.py ──► nco_documents.json + nco_metadata.json
       │
       ▼
05_searchGN.py ──────► nco_graph.json
       │
       ▼
02_generateEmbedding.py ──► nco_embeddings.npy
       │
       ▼
03_build_faiss_index.py ──► nco_faiss.index
       │
       ▼
06_searchapp.py / api.py ──► REST API search
```
