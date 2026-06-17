# PROJECT_DOCUMENTATION.md

## 1) Project Overview
This project is an AI-assisted **NCO occupation search and management system** built with Flask.

Primary goals:
- Map free-text job queries to **NCO 2015** occupations using semantic retrieval.
- Support multilingual input via translation.
- Provide an admin dashboard for analytics and controlled CRUD over occupation data.

Core runtime entrypoint:
- `app.py`

Current runtime mode:
- Flask dev server on port `5000` (`debug=True` in `app.py`).

---

## 2) Tech Stack
- Backend: Python, Flask
- Retrieval/ML: `sentence-transformers` (`BAAI/bge-small-en-v1.5`), `faiss-cpu`, `numpy`
- Data utilities: `pandas`, `csv`, `json`
- Translation + language detection: `requests`, `langdetect`
- Storage: PostgreSQL for occupations, admin settings/password hash, prompt history, semantic documents, graph data, embeddings, and serialized FAISS index bytes
- Frontend: HTML/CSS/Vanilla JS + Bootstrap + Chart.js

Dependencies declared in `requirements.txt`:
- `pandas`
- `numpy`
- `flask`
- `sentence-transformers`
- `faiss-cpu`
- `langdetect`
- `requests`

---

## 3) Repository Structure (Functional)
- `app.py`: Main Flask app, API routes, admin validation, data mutation, search asset rebuilds
- `db_store.py`: PostgreSQL schema and storage helpers
- `scripts/migrate_to_postgres.py`: one-time importer from the previous CSV/JSON/SQLite files into PostgreSQL
- `templates/index.html`: User search UI (general search + NCO search + voice + language flow)
- `templates/admin/dashboard.html`: Admin dashboard (analytics charts + database management CRUD)
- `static/gov-style.css`: Main user UI styling
- `scripts/01_preparation.py`: PostgreSQL occupations to semantic documents + metadata
- `scripts/02_generateEmbedding.py`: Generate embeddings and store them in PostgreSQL
- `scripts/03_build_faiss_index.py`: Build FAISS index and store it in PostgreSQL
- `scripts/04_search.py`: CLI semantic search test utility
- `scripts/05_searchGN.py`: Build simple graph-network keyword map
- `scripts/06_searchapp.py`: Runtime hybrid search implementation + PIGS helper
- `utils/translation_service.py`: language detection + translation chain
- `utils/dynamic_prompts.py`: dynamic prompt generation based on occupation title/category
- `utils/analyze_occupations.py`: exploratory analysis utility
- `utils/debug_search.py`: quick debug search utility
- `data/raw/nco_dataset_v6_final.csv`: previous import source for migration
- `data/processed/*.json`: previous import source for migration/history
- `models/*`: legacy local artifacts no longer used by runtime
- `data/admin.db`: previous admin settings source for migration

---

## 4) Data Model and Artifacts
### Primary source-of-truth data
- PostgreSQL table: `occupations`
- Previous CSV import source: `data/raw/nco_dataset_v6_final.csv`
- Important columns used:
  - `S No`
  - `Occupational Title`
  - `NCO 2015`
  - `NCO 2004`
  - `Division`
  - `Sub Division`
  - `Group`
  - `Family`
  - `Division Description`
  - `Sub Division Description`
  - `Group Description`
  - `Family Description`
  - `Occupation Description`

### Derived/search artifacts
- PostgreSQL table: `search_documents`
- PostgreSQL table: `nco_graph`
- PostgreSQL table: `search_assets`
  - `nco_embeddings.npy`
  - `nco_faiss.index`

### Operational telemetry
- PostgreSQL table: `prompt_history` (search history, top result details, query metadata)

### Admin settings
- PostgreSQL table: `admin_settings(key TEXT PRIMARY KEY, value TEXT)`
- Password stored as PBKDF2 hash with salt in format: `salt$digest`

---

## 5) Search Architecture
### Runtime module loading
`app.py` dynamically loads `scripts/06_searchapp.py` at startup.

### Hybrid scoring in `06_searchapp.py`
For each query:
1. Encode query using SBERT/BGE model (`BAAI/bge-small-en-v1.5`) with query instruction prepended.
2. Search two FAISS indexes:
   - Full occupation document index
   - Title-only index
3. For each candidate, compute:
   - semantic score
   - title score
   - graph overlap score from `nco_graph.json`
4. Blend with weights and boosts:
   - `ALPHA=0.7`, `BETA=0.3`
   - score multiplier and title overlap boost
5. Return top-k sorted by final score.

### NCO direct search mode
`/api/search` supports `search_mode: "nco"` and performs exact normalized match against NCO 2015 codes.

---

## 6) Prompt Intelligence (PIGS)
PIGS logic is exposed from `06_searchapp.py` and used in `app.py` response generation.

It:
- Computes hierarchy-level similarity signals (division/sub-division/group/family context)
- Generates friendly guidance suggestions
- Combines with `utils/dynamic_prompts.py` examples for prompt refinement

Returned in `/api/search` under key `pigs`.

---

## 7) Translation and Language Handling
Implemented in `utils/translation_service.py`.

Flow:
- Detect language confidence using `langdetect`.
- If ambiguous and user language not confirmed, backend sends `language_ambiguity` object.
- Translation strategy:
  - MyMemory first (fast)
  - LibreTranslate fallback endpoints
  - Optional Bhashini integration (credentials required)

`/api/translate` is available for explicit translation calls.

---

## 8) Flask Routes and API Contracts
## UI routes
- `GET /` -> `templates/index.html`
- `GET /admin` -> `templates/admin/dashboard.html`

## Public API
- `POST /api/search`
  - Input: `query`, optional `user_language`, `search_mode`, `top_k`
  - Modes:
    - `general`: semantic search
    - `nco`: exact NCO code lookup
  - Output includes results, translation notice, ambiguity flags, pigs details, counts

- `POST /api/translate`
  - Input: `text`, `source_lang`, `target_lang`, `preferred_service`

- `GET /api/languages`
  - Returns supported language map

## Admin API
- `GET /admin/api/prompt-history?limit=...&occupation_title=...`
- `GET /admin/api/occupations`
- `POST /admin/api/occupations` (password protected)
- `PUT /admin/api/occupations/<row_id>` (password protected)
- `DELETE /admin/api/occupations/<row_id>` (password protected)

Legacy/aux analytics endpoints still present:
- `/admin/api/analytics/divisions`
- `/admin/api/analytics/confidence`
- `/admin/api/analytics/top-occupations`
- `/admin/api/analytics/search-trend`
- `/admin/api/analytics/languages`
- `/admin/api/analytics/low-confidence`

Note: current admin charts primarily consume `/admin/api/prompt-history` directly.

---

## 9) Admin Security and Validation (Current State)
## Password protection
- Add, Edit, Delete all require `admin_password`.
- First successful password usage initializes and locks admin password hash in SQLite.

## NCO format rules enforced backend-side
- NCO 2015: `XXXX.XXXX` mandatory on add/edit
- NCO 2004: `XXXX.XX`
  - optional on add
  - required on edit only when existing row already has an NCO 2004 code

## Required field validation
On add/edit:
- Occupation Title
- Division
- Sub Division
- Group
- Family
- Occupation Description

## Duplicate prevention
- Duplicate NCO 2015 blocked
- Duplicate NCO 2004 blocked when provided

## Rebuild behavior after successful mutation
Add/Edit/Delete triggers:
1. CSV rewrite
2. Rebuild semantic documents + metadata
3. Rebuild graph JSON
4. Re-encode embeddings
5. Rebuild FAISS index

This guarantees consistency but can be compute-heavy during frequent edits.

---

## 10) Admin Frontend Behavior (Current)
File: `templates/admin/dashboard.html`

### Analytics tab
- Replaced earlier static analysis blocks with 6 chart cards.
- Uses Chart.js with periodic refresh logic.
- Layout constrained to fixed chart-card heights to prevent runaway page growth.

### Database Management tab
- Occupation table with search/filter/pagination.
- Add/Edit modals include segmented NCO input UX:
  - NCO 2015: first 4 digits + second 4 digits
  - NCO 2004: first 4 digits + second 2 digits
- Edit modal behavior:
  - If row has NCO 2004 code, editable section shown
  - If missing, NCO 2004 edit section hidden/disabled
- Cascading dropdowns implemented:
  - Division -> Sub Division -> Group -> Family

### Validation UX
- Required field checks in JS before submission
- Numeric sanitization and fixed-length checks for segmented NCO parts
- Server errors displayed via notification (includes wrong password/duplicate/format errors)

---

## 11) End-to-End Request Flows
## Search flow
1. User submits query from `index.html`.
2. Backend optionally translates query.
3. Search module returns ranked results.
4. Backend appends prompt history entry.
5. UI renders ranked results + optional PIGS guidance.

## Admin add/edit/delete flow
1. User fills modal and enters admin password.
2. Frontend validates required fields + NCO segmentation.
3. API validates again (authoritative).
4. On success, CSV and search assets rebuild.
5. UI refreshes occupation table and analytics.

---

## 12) Known Gaps / Risks
- Full asset rebuild on each admin mutation may be slow for large datasets.
- `dashboard.html` contains duplicate `refreshAnalytics` function declarations and legacy fragments from earlier iterations; behavior works but file can be refactored for maintainability.
- Some text in templates/scripts appears mojibake-encoded in source comments/labels; functional impact is minimal but readability can improve.
- Flask app currently runs in debug mode by default in `__main__`.

---

## 13) Runbook
## Local setup
1. Create/activate Python env.
2. Create PostgreSQL database and set `DATABASE_URL`, for example:
   ```bash
   set DATABASE_URL=postgresql://postgres:postgres@localhost:5432/statathon_nco
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the one-time migration/import:
   ```bash
   python scripts/migrate_to_postgres.py
   ```
5. Run:
   ```bash
   python app.py
   ```
6. Open:
   - App: `http://127.0.0.1:5000/`
   - Admin: `http://127.0.0.1:5000/admin`

## Rebuild pipeline manually
```bash
python scripts/01_preparation.py
python scripts/05_searchGN.py
python scripts/02_generateEmbedding.py
python scripts/03_build_faiss_index.py
```

---

## 14) Current Status Snapshot
As of latest changes in this workspace:
- Admin analytics redesigned into chart-based real-time dashboard.
- Chart expansion/infinite page growth issue addressed with constrained card/canvas sizing.
- Occupation add/edit module upgraded with:
  - password protection on edit
  - segmented NCO 2015 and NCO 2004 inputs
  - NCO format enforcement
  - duplicate checks
  - required hierarchy validations
  - conditional NCO 2004 edit visibility
- Existing search APIs and core architecture preserved.

---

## 15) Suggested Next Engineering Tasks
1. Refactor `templates/admin/dashboard.html` JS into modular files.
2. Add automated tests for admin API validations and duplicate handling.
3. Move expensive rebuild operations to async/background jobs.
4. Add role-based auth/session guard for `/admin` route.
5. Add structured logging and health-check endpoint.
