# NCO Semantic Search System — Production Documentation

**Version:** 1.0.0  
**Authors:** Kabhilan R, Team Eureka  
**Last Reviewed:** 2026-06-11  
**Intended Audience:** Developers, system administrators, and evaluators  
**Document Status:** Approved  

---

## Revision History

| Version | Date | Author | Summary of Changes |
|---------|------|--------|---------------------|
| 1.0.0 | 2026-06-11 | Kabhilan R | Initial production-grade documentation covering architecture, setup, operations, API surface, admin workflows, security posture, and release notes. |
| 0.9.0 | 2026-06-08 | Kabhilan R | Internal draft — tech stack finalization and PostgreSQL migration documentation. |
| 0.8.0 | 2026-06-05 | Kabhilan R | Hybrid search engine (SBERT + FAISS + TF-IDF) integration and PIGS prompt intelligence layer. |

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Prerequisites and Requirements](#2-prerequisites-and-requirements)
3. [Installation and Setup](#3-installation-and-setup)
4. [Usage Guide](#4-usage-guide)
5. [Configuration Reference](#5-configuration-reference)
6. [Architecture and Data Flow](#6-architecture-and-data-flow)
7. [API and Integration Reference](#7-api-and-integration-reference)
8. [Security and Compliance](#8-security-and-compliance)
9. [Troubleshooting and Error Reference](#9-troubleshooting-and-error-reference)
10. [Runbook and Operations Guide](#10-runbook-and-operations-guide)
11. [Glossary and Definitions](#11-glossary-and-definitions)
12. [Release Notes — Version 1.0.0](#12-release-notes--version-100)

---

## 1. Executive Summary

### What is this?

The NCO Semantic Search System is an AI-powered occupation classification tool that maps natural-language job descriptions to India's **National Classification of Occupations (NCO)** codes. It was built for the Eureka Statathon competition and has since been hardened for production deployment.

Rather than forcing users to manually browse thousands of occupation entries, this system accepts plain-English queries (or queries in any of 11 supported Indian languages) and returns the most relevant NCO occupation codes with full hierarchical context — Division, Sub-Division, Group, Family, and Occupation Description.

### What problem does it solve?

India's NCO framework contains thousands of occupation entries spread across a complex four-level hierarchy. Finding the right code for a given job description has traditionally required expert knowledge and manual table lookups. This system automates that process through hybrid semantic retrieval, making occupation classification accessible to anyone who can describe a job in their own words.

### Who is the primary user?

- **Public users** — Government clerks, HR professionals, researchers, job seekers, or census workers who need to classify occupations against the NCO 2015 or NCO 2004 standards.
- **Administrators** — Data custodians who maintain the occupation database, monitor search analytics, and ensure data quality.

### Scope

This document covers the complete system as deployed: backend, frontend, database schema, search pipeline, translation layer, admin dashboard, API contracts, security model, deployment procedures, and operational runbooks.

It does **not** cover the competition submission materials (the PDF presentations in the `documents/` folder), nor does it cover the legacy SQLite/CSV pipeline that has been fully superseded by the PostgreSQL architecture.

### Related Documents

- `README.md` — Quick-start guide for developers.
- `PROJECT_DOCUMENTATION.md` — Internal technical reference (predecessor to this document).
- `AWS_TROUBLESHOOTING_GUIDE.md` — EC2-specific disk, pip, and venv troubleshooting.
- `GITHUB_AWS_WORKFLOW.md` — Git-to-EC2 deployment workflow using SSH deploy keys.

---

## 2. Prerequisites and Requirements

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 2 cores | 4 cores |
| RAM | 4 GB | 8 GB |
| Disk | 10 GB free | 20 GB free |
| OS | Windows 10+, Ubuntu 20.04+, macOS 12+ | Ubuntu 22.04 LTS |

The SBERT model download (~130 MB) and embedding generation are the most resource-intensive operations. On a 2-core EC2 instance, initial embedding generation for the full dataset takes approximately 2–3 minutes.

### Software Dependencies

| Dependency | Purpose |
|------------|---------|
| Python 3.10 or later | Runtime language |
| PostgreSQL 13 or later | Primary data store for occupations, search assets, prompt history, and admin settings |
| pip (bundled with Python) | Package manager |

### Python Package Dependencies

| Package | Purpose |
|---------|---------|
| flask | Web framework and routing |
| flask-cors | Cross-origin resource sharing for decoupled frontend |
| sentence-transformers | SBERT model loading and embedding generation |
| faiss-cpu | Facebook AI Similarity Search for vector retrieval |
| numpy | Numerical operations on embedding arrays |
| pandas | Data manipulation (CSV import and migration) |
| psycopg2-binary | PostgreSQL driver with connection pooling |
| python-dotenv | Environment variable loading from `.env` files |
| langdetect | Statistical language detection for multilingual queries |
| deep-translator | Google Translate fallback for translation |
| requests | HTTP client for Bhashini translation API |

### Required Access and Credentials

- **PostgreSQL database credentials** — A running PostgreSQL instance with a database (default: `statathon_nco`). The connection string goes in the `.env` file.
- **Bhashini API credentials** (optional) — For Indian language translation via the government Bhashini API. Set `BHASHINI_API_KEY` and `BHASHINI_USER_ID` in the environment if available. Without these, the system falls back to Google Translate.
- **Admin password** — Set on first use. The first password submitted through any admin write operation becomes the permanent admin password (stored as a PBKDF2-HMAC-SHA256 hash).

### Assumed Reader Knowledge

This document assumes familiarity with Python web applications, basic SQL, command-line environments, and REST API concepts. No machine learning expertise is required to set up, operate, or maintain the system.

### Network Constraints

- The server must be able to download the SBERT model (`BAAI/bge-small-en-v1.5`) from Hugging Face on first startup. Subsequent startups load the cached model from disk.
- Translation features require outbound HTTPS access to Google Translate and/or the Bhashini API. If the server is air-gapped, translation will gracefully degrade — queries will be searched in their original language.

---

## 3. Installation and Setup

### Step 1 — Clone the Repository

Obtain the project source from your Git remote. The working branch used in production is `Kabhilan`.

### Step 2 — Create a PostgreSQL Database

Using your preferred PostgreSQL client, create a new database. The default expected name is `statathon_nco`. The application will create all necessary tables automatically on first startup.

### Step 3 — Configure Environment Variables

Create a `.env` file in the project root directory. This file is read by `python-dotenv` on application startup and must never be committed to version control (it is already listed in `.gitignore`).

Required variable:
- `DATABASE_URL` — Full PostgreSQL connection string in the format `postgresql://user:password@host:port/database`.

Optional variables:
- `BHASHINI_API_KEY` — API key for the Bhashini translation service.
- `BHASHINI_USER_ID` — User identifier for the Bhashini translation service.

Do not set database credentials using shell environment variables or inline assignments. The application exclusively reads from the `.env` file via `python-dotenv`.

### Step 4 — Install Python Dependencies

Use pip to install all required packages from the `requirements.txt` file in the project root. If deploying on a server, ensure you install into the correct virtual environment — packages installed globally will not be visible to the application if it runs inside a venv.

### Step 5 — Import Data and Build Search Assets

Run the one-time migration script located at `scripts/migrate_to_postgres.py`. This script performs the following in sequence:

1. Initializes the PostgreSQL schema (creates all tables if they do not exist).
2. Imports occupation data from the CSV file at `data/raw/nco_dataset_v6_final.csv`.
3. Imports prompt history from `data/processed/prompt_history.json` (if present).
4. Migrates admin settings from the legacy SQLite database `data/admin.db` (if present).
5. Generates semantic documents and metadata for each occupation.
6. Builds the keyword graph network.
7. Downloads the SBERT model, encodes all documents into embeddings, and stores them in PostgreSQL.
8. Builds the FAISS index and stores the serialized index bytes in PostgreSQL.
9. Cleans up legacy files that are no longer needed.

This step takes 2–5 minutes depending on hardware, primarily due to SBERT model download (first run only) and embedding generation.

### Step 6 — Start the Server

Run `app.py` to start the Flask development server on port 5000. On startup, the application:

1. Loads environment variables from `.env`.
2. Initializes the PostgreSQL connection pool (2–20 connections).
3. Auto-moves any CSV file found in the project root to `data/raw/`.
4. Auto-generates decoupled frontend assets from the Flask templates.
5. Dynamically loads the search engine module from `scripts/06_searchapp.py`.
6. Loads the SBERT model, FAISS indexes, TF-IDF indexes, and occupation metadata into memory.

### Step 7 — Verify the Installation

After startup completes without errors:

- Open the public search interface at `http://127.0.0.1:5000/` — you should see the occupation search page with a search bar and prompt suggestions.
- Open the admin dashboard at `http://127.0.0.1:5000/admin` — you should see analytics charts and a database management tab.
- Try a test search query such as "software engineer" — you should receive ranked results with NCO codes and hierarchy details.

### Platform-Specific Notes

**Windows:** PostgreSQL must be running as a Windows service or manually started before launching the application. Use PowerShell or Command Prompt to run Python commands.

**Linux (Ubuntu/EC2):** On production servers, run the application behind Gunicorn or a similar WSGI server. The `nco-backend` systemd service should point to the virtual environment's Python binary. See `GITHUB_AWS_WORKFLOW.md` for the full EC2 deployment procedure.

**macOS:** PostgreSQL can be installed via Homebrew. All other steps are identical to Linux.

---

## 4. Usage Guide

### Public Search Interface

The public search interface is the primary user-facing surface. It is served at the root URL and provides several search modes and features.

#### General Semantic Search

The default search mode. Users type a natural-language description of a job or occupation, and the system returns the most relevant NCO occupation codes ranked by relevance score.

The search pipeline works in three stages:
1. **TF-IDF fast path** — If the query closely matches an occupation title (above a 0.65 confidence threshold), results are returned instantly without invoking the neural model. This makes exact or near-exact title lookups sub-millisecond.
2. **Full hybrid search** — For broader queries, the system encodes the query using the SBERT model, searches both the full-document and title-only FAISS indexes, computes TF-IDF overlap scores, and blends results using a weighted formula (70% semantic similarity, 30% TF-IDF keyword relevance).
3. **PIGS analysis** — The Prompt Intelligence and Guidance System analyzes the query against the NCO hierarchy and generates suggestions to help users refine ambiguous queries.

Results are returned with the following context for each match:
- Occupation title and NCO 2015 code
- NCO 2004 code (when available)
- Full hierarchy: Division, Sub-Division, Group, Family
- Occupation, Family, and Group descriptions
- Relevance scores (semantic, title match, keyword overlap, final blended score)

#### NCO Code Direct Lookup

Users can switch to NCO code search mode to look up a specific occupation by its NCO 2015 code. The system normalizes the input (handling missing dots, extra spaces, and varying digit counts) and returns an exact match.

Accepted NCO 2015 format: `XXXX.XXXX` (four digits, dot, four digits).  
Accepted NCO 2004 format: `XXXX.XX` (four digits, dot, two digits).

#### Multilingual Search

Users can select their language from a dropdown of 11 supported languages. When a non-English language is selected, the query is translated to English before searching. The translation chain prioritizes the Bhashini API (optimized for Indian languages) and falls back to Google Translate if Bhashini is unavailable.

Supported languages: English, Hindi, Tamil, Telugu, Bengali, Marathi, Gujarati, Kannada, Malayalam, Punjabi, and Urdu.

A translation notice is displayed alongside results when translation occurs, showing both the original and translated query text.

#### Prompt Intelligence and Guidance (PIGS)

When search results indicate ambiguity (low confidence or tight score clustering), the system provides:
- **Hierarchy-level similarity scores** — How well the query matches at Division, Sub-Division, Group, and Family levels.
- **Refinement suggestions** — Actionable advice like "You can add the job family: Electrical Engineering Technicians" or "Try describing the main responsibilities of the role."
- **Dynamic prompt examples** — Auto-generated example queries based on the category and domain of the top result (e.g., leadership, technical, healthcare, creative templates).

#### Directory Browsing

Submitting an empty query triggers directory mode, which returns a paginated listing of all occupations in the database. This is useful for browsing the full NCO taxonomy without a specific search target.

### Admin Dashboard

The admin dashboard is served at `/admin` and provides two major functional tabs.

#### Analytics Tab

Six real-time chart cards powered by Chart.js:
1. **Divisions distribution** — Bar chart showing occupation counts by Division (top 10).
2. **Confidence distribution** — Doughnut chart breaking searches into High (>85%), Medium (60–85%), and Low (<60%) confidence buckets.
3. **Top searched occupations** — Bar chart of the most frequently returned NCO codes.
4. **Search trend** — Line chart showing daily search volume over the past 7 days.
5. **Language distribution** — Chart showing the breakdown of queries by detected language.
6. **Low confidence queries** — Table listing the most common queries that returned low-confidence results, with average confidence scores.

Charts refresh automatically to reflect real-time search telemetry.

#### Database Management Tab

A full CRUD interface for managing the occupation database:
- **View** — Searchable, filterable, paginated table of all occupations.
- **Add** — Modal form with segmented NCO code input (4+4 digits for NCO 2015, 4+2 digits for NCO 2004), required field validation, and cascading hierarchy dropdowns (Division → Sub-Division → Group → Family).
- **Edit** — Pre-populated modal with all fields. NCO 2004 editing is conditionally shown only when the existing record already has an NCO 2004 code.
- **Delete** — Confirmation-gated deletion with password verification.

Every write operation (add, edit, delete) requires the admin password and triggers a full rebuild of search assets — embeddings, FAISS indexes, TF-IDF indexes, graph data, and metadata — to maintain search consistency.

---

## 5. Configuration Reference

### Environment Variables

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `DATABASE_URL` | String | Yes | `postgresql://postgres:postgres@localhost:5432/statathon_nco` | PostgreSQL connection string. |
| `BHASHINI_API_KEY` | String | No | None | API key for the Bhashini translation service. |
| `BHASHINI_USER_ID` | String | No | None | User identifier for the Bhashini translation service. |

### Search Engine Parameters

These constants are defined in `scripts/06_searchapp.py` and control the behavior of the hybrid search pipeline.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `MODEL_NAME` | String | `BAAI/bge-small-en-v1.5` | Sentence-BERT model used for embedding generation. |
| `DEFAULT_TOP_K` | Integer | 5 | Default number of results returned per query. |
| `MAX_TOP_K` | Integer | 100 | Maximum allowed value for the `top_k` parameter. |
| `CANDIDATE_K` | Integer | 50 | Number of FAISS candidates retrieved before re-ranking. |
| `TITLE_CANDIDATE_K` | Integer | 50 | Number of title-index candidates retrieved before re-ranking. |
| `CONFIDENCE_THRESHOLD` | Float | 0.45 | Below this score, a low-confidence warning is triggered. |
| `ALPHA` | Float | 0.7 | Weight applied to the semantic (SBERT) similarity score. |
| `BETA` | Float | 0.3 | Weight applied to the TF-IDF keyword overlap score. |
| `TFIDF_FAST_PATH_THRESHOLD` | Float | 0.65 | TF-IDF score above which the expensive SBERT encoding is skipped entirely. |

### Database Connection Pool

Defined in `db_store.py`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `minconn` | 2 | Minimum number of connections kept alive in the pool. |
| `maxconn` | 20 | Maximum number of connections the pool will create. |

### Flask Application

| Parameter | Default | Description |
|-----------|---------|-------------|
| `debug` | True | Flask debug mode. Must be set to False in production. |
| `port` | 5000 | Port the development server listens on. |
| CORS | Enabled globally | Cross-origin requests are allowed from any origin. |

### Translation Cache

The translation service maintains an in-memory LRU cache of up to 2,048 entries. When the cache exceeds this size, it is fully cleared. There is no time-based expiration.

---

## 6. Architecture and Data Flow

### High-Level Architecture

The system follows a three-tier architecture:

**Presentation Layer** — Flask-rendered HTML templates (Jinja2) with vanilla JavaScript, Bootstrap for layout, and Chart.js for analytics visualization. A decoupled frontend variant is auto-generated on startup for static hosting scenarios.

**Application Layer** — A Flask backend (`app.py`) that handles routing, request validation, password verification, translation orchestration, and search coordination. The search engine (`scripts/06_searchapp.py`) is loaded as a dynamic module at startup and operates as an in-memory service with PostgreSQL-backed data.

**Data Layer** — PostgreSQL stores all persistent state: occupation records, search documents, graph networks, FAISS index bytes, embedding arrays, prompt history telemetry, and admin settings. A threaded connection pool manages database access.

### Data Flow — Search Request

1. User submits a query through the search interface.
2. Flask receives the POST request at `/api/search`.
3. If a non-English language is selected, the query is translated to English via the Bhashini/Google translation chain.
4. The search engine first attempts the TF-IDF fast path against occupation titles.
5. If the fast path confidence is below threshold, the full SBERT + FAISS hybrid pipeline executes.
6. Results are blended, re-ranked, and filtered to the requested top-k.
7. The PIGS module analyzes the query against the result hierarchy and generates refinement suggestions.
8. The query, result metadata, confidence score, and detected language are logged to the `prompt_history` table.
9. The response (results, PIGS analysis, translation notice) is returned as JSON.

### Data Flow — Admin Write Operation

1. Admin submits an add/edit/delete request with their password.
2. Flask validates the password against the stored PBKDF2 hash.
3. Input validation runs: required fields, NCO format rules, duplicate checks.
4. The occupation record is inserted, updated, or deleted in PostgreSQL.
5. A full search asset rebuild triggers: new semantic documents, embeddings, FAISS indexes, TF-IDF indexes, and graph data are generated and stored.
6. The search engine's in-memory state is hot-reloaded via `reload_from_db()`.
7. The response confirms success or returns a structured error.

### Technology Stack

| Layer | Technology | Version/Model |
|-------|-----------|---------------|
| Runtime | Python | 3.10+ |
| Web Framework | Flask | Latest stable |
| Database | PostgreSQL | 13+ |
| Embedding Model | SBERT (BAAI/bge-small-en-v1.5) | 384-dimensional embeddings |
| Vector Search | FAISS (IndexFlatIP) | Inner product similarity |
| Keyword Search | Custom TF-IDF engine | Pure Python, zero external dependencies |
| Translation | Bhashini API + Google Translate | Cascading fallback |
| Language Detection | langdetect | Statistical n-gram detection |
| Frontend | HTML/CSS/JS + Bootstrap + Chart.js | Vanilla, no build step |

### Database Schema

**`occupations`** — Primary occupation data. Each row represents one NCO occupation with title, codes (NCO 2015 and NCO 2004), hierarchy fields, descriptions, and timestamps.

**`search_documents`** — Pre-computed semantic documents and metadata for each occupation, linked by foreign key to the occupations table with cascade delete.

**`nco_graph`** — Keyword graph network. Maps each NCO code to its sector classification and an array of extracted keywords.

**`search_assets`** — Binary storage for serialized FAISS indexes and NumPy embedding arrays.

**`prompt_history`** — Append-only telemetry log capturing every search query, translation status, top result, confidence, detected language, and client IP.

**`admin_settings`** — Key-value store for administrative configuration, including the hashed admin password.

---

## 7. API and Integration Reference

### Public Endpoints

#### POST /api/search

Performs a semantic search or NCO code lookup.

**Request body (JSON):**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `query` | String | Yes | — | The search query text. Empty string triggers directory browsing mode. |
| `search_mode` | String | No | `general` | Search mode. `general` for semantic search, `nco` for exact code lookup. |
| `user_language` | String | No | None | ISO language code of the query language (e.g., `hi`, `ta`, `te`). Triggers translation when not `en`. |
| `top_k` | Integer | No | 5 | Number of results to return. Range: 1–100. |
| `page` | Integer | No | 1 | Page number for directory browsing mode (empty query). |
| `per_page` | Integer | No | 50 | Results per page for directory browsing. Range: 1–200. |

**Response body (JSON) — Search mode:**

| Field | Type | Description |
|-------|------|-------------|
| `results` | Array | Ranked occupation results with scores and details. |
| `suggestion` | String or null | Dynamic prompt suggestions for ambiguous queries. |
| `translation_notice` | Object or null | Contains `original`, `translated`, and `message` when translation occurred. |
| `language_ambiguity` | Object or null | Present when language detection is uncertain. |
| `pigs` | Object or null | Prompt Intelligence output: `level_scores`, `suggestions`, `prompt_examples`. |
| `top_k` | Integer | The effective top-k value used. |
| `returned_count` | Integer | Actual number of results returned. |

**Response body (JSON) — Directory mode:**

| Field | Type | Description |
|-------|------|-------------|
| `results` | Array | Paginated occupation listing. |
| `directory_mode` | Boolean | Always `true` in this mode. |
| `total_count` | Integer | Total number of occupations in the database. |
| `page` | Integer | Current page number. |
| `per_page` | Integer | Page size. |

**HTTP status codes:** 200 (success), 400 (invalid input), 500 (server error).

#### POST /api/translate

Translates text between supported languages.

**Request body:** `text` (required), `source_lang` (default: `auto`), `target_lang` (default: `en`), `preferred_service` (default: `lingua`).

**Response body:** `original_text`, `translated_text`, `source_lang`, `target_lang`, `service_used`.

#### GET /api/languages

Returns a map of supported language codes and their display names.

### Admin Endpoints

All write endpoints require `admin_password` in the request body.

#### GET /admin/api/occupations

Returns the full list of occupations with all fields.

#### POST /admin/api/occupations

Adds a new occupation. Required fields: `occupation_title`, `nco_code` (NCO 2015 format), `division`, `sub_division`, `group`, `family`, `description`. Optional: `nco_2004_code`, hierarchy descriptions.

Returns 400 for validation errors, 403 for incorrect password.

#### PUT /admin/api/occupations/{row_id}

Updates an existing occupation. Same required fields as POST. The NCO 2004 code is required on update only if the existing record already has one.

#### DELETE /admin/api/occupations/{row_id}

Deletes an occupation by its row ID. Requires `admin_password`.

#### GET /admin/api/prompt-history

Returns search telemetry records. Optional query parameters: `limit` (1–500, default 100), `occupation_title` (filter by specific occupation).

### Analytics Endpoints

| Endpoint | Returns |
|----------|---------|
| `GET /admin/api/analytics/divisions` | Top 10 divisions by occupation count. |
| `GET /admin/api/analytics/confidence` | High/Medium/Low confidence distribution. |
| `GET /admin/api/analytics/top-occupations` | Top 10 most frequently searched NCO codes. |
| `GET /admin/api/analytics/search-trend` | Daily search volume for the past 7 days. |
| `GET /admin/api/analytics/languages` | Search query language distribution. |
| `GET /admin/api/analytics/low-confidence` | Top 10 low-confidence queries with average scores. |

---

## 8. Security and Compliance

### Authentication Model

The system uses a single-password admin authentication model. There is no session management, no role-based access control, and no token-based authentication.

- The admin password is set on first use — the first password submitted through any admin write operation becomes the permanent password.
- The password is hashed using PBKDF2-HMAC-SHA256 with a 16-byte random salt and 200,000 iterations.
- The hash is stored in the `admin_settings` table in the format `salt$digest`.
- Password verification uses constant-time comparison (`secrets.compare_digest`) to prevent timing attacks.

**Limitation:** There is no password reset mechanism. If the admin password is lost, the `admin_settings` table must be manually cleared in PostgreSQL.

### Data Sensitivity

- **Occupation data** — Public government classification data. No sensitivity restrictions.
- **Prompt history** — Contains search queries and client IP addresses. This constitutes usage telemetry and should be treated with standard data handling practices.
- **Admin password hash** — Sensitive. Stored securely in PostgreSQL, never logged, never returned in API responses.
- **`.env` file** — Contains database credentials. Must never be committed to version control. Already excluded via `.gitignore`.

### Secrets Management

- Database credentials are stored exclusively in the `.env` file, loaded via `python-dotenv`.
- Bhashini API credentials are optional environment variables.
- No secrets are hard-coded in the source code.
- The `.gitignore` excludes `.env`, `*.pem`, and other sensitive file patterns.

### Known Security Considerations

- The Flask development server runs with `debug=True` by default. This must be disabled in production deployments and replaced with a production WSGI server like Gunicorn.
- CORS is enabled globally without origin restrictions. For production, restrict the `Access-Control-Allow-Origin` header to known frontend domains.
- The admin endpoints do not use session tokens — the password must be sent with every write request. This is acceptable for internal tools but is not suitable for public-facing admin interfaces.
- No rate limiting is implemented on any endpoint.

---

## 9. Troubleshooting and Error Reference

### Application Startup Errors

**Error:** `RuntimeError: Failed to load search module`  
**Cause:** The search engine script at `scripts/06_searchapp.py` could not be located or contains import errors.  
**Resolution:** Verify the file exists and that all dependencies (sentence-transformers, faiss-cpu, numpy) are installed in the active Python environment.

**Error:** `RuntimeError: No search metadata found in PostgreSQL. Run scripts/migrate_to_postgres.py first.`  
**Cause:** The `search_documents` table is empty. The migration script has not been run or the database was reset.  
**Resolution:** Run the migration script to populate the database from the CSV source.

**Error:** `RuntimeError: No FAISS index found in PostgreSQL. Run scripts/migrate_to_postgres.py first.`  
**Cause:** The FAISS index has not been built and stored in the `search_assets` table.  
**Resolution:** Run the migration script. If the issue persists, check that faiss-cpu is correctly installed.

**Error:** `psycopg2.OperationalError: could not connect to server`  
**Cause:** PostgreSQL is not running, the connection string is incorrect, or the database does not exist.  
**Resolution:** Verify PostgreSQL is running, check the `DATABASE_URL` in `.env`, and confirm the database name matches.

### Runtime Errors

**Error:** `Translation failed: [exception details]`  
**Cause:** The Bhashini API is unreachable or returned an error, and the Google Translate fallback also failed.  
**Resolution:** Check outbound HTTPS connectivity. If both translation services are down, the query will be searched in its original language — search will still work, but results may be less relevant for non-English queries.

**Error:** Admin API returns `403 — Invalid password`  
**Cause:** The submitted password does not match the stored hash.  
**Resolution:** Verify the correct password. There is no password reset UI — if the password is lost, delete the `admin_password_hash` row from the `admin_settings` table in PostgreSQL to allow re-initialization.

**Error:** Admin API returns `400 — NCO 2015 code already exists`  
**Cause:** A duplicate NCO 2015 code was submitted during an add or edit operation.  
**Resolution:** Each NCO 2015 code must be unique across all occupations. Check the existing database for the conflicting code.

### Deployment Errors (AWS EC2)

See `AWS_TROUBLESHOOTING_GUIDE.md` for detailed coverage of:
- Disk space exhaustion during pip installs.
- Packages not found due to virtual environment isolation.
- The dangers of running `pip install -r requirements.txt` without pinned versions.
- The `externally-managed-environment` error on newer Ubuntu versions.

### Log Locations

- **Application logs** — Flask prints to stdout/stderr. On EC2 with systemd, view logs via `journalctl -u nco-backend`.
- **Translation logs** — The translation service uses Python's `logging` module at INFO level, writing to stdout.
- **PostgreSQL logs** — Default location varies by installation. On Ubuntu: `/var/log/postgresql/`.

### Escalation Path

For issues not covered here:
1. Check the existing troubleshooting guides (`AWS_TROUBLESHOOTING_GUIDE.md`, `GITHUB_AWS_WORKFLOW.md`).
2. Review the PostgreSQL logs for database-level errors.
3. Contact the project maintainer (Kabhilan R) with the error message, relevant log output, and steps to reproduce.

---

## 10. Runbook and Operations Guide

### Deployment Procedure

**Local development:**
1. Ensure PostgreSQL is running.
2. Activate the virtual environment.
3. Run `python app.py`.

**AWS EC2 production:**
1. SSH into the EC2 instance.
2. Navigate to `/var/www/nco-backend`.
3. Pull latest code: `git pull origin Kabhilan`.
4. Activate the virtual environment: `source venv/bin/activate`.
5. Install any new dependencies: `pip install -r requirements.txt`.
6. Restart the service: `sudo systemctl restart nco-backend`.

See `GITHUB_AWS_WORKFLOW.md` for the full Git-to-EC2 workflow including SSH deploy key setup.

### Rollback Procedure

1. Identify the last known working commit via `git log`.
2. Check out the working commit: `git checkout <commit-hash>`.
3. Restart the service.
4. If the database schema changed between versions, restore from the most recent PostgreSQL backup.

### Search Asset Rebuild

Search assets (embeddings, FAISS indexes, TF-IDF indexes, graph data) are automatically rebuilt after every admin write operation. To trigger a manual rebuild:

1. Run the migration script, which will re-import all CSV data and rebuild all assets.
2. Alternatively, add/edit/delete any occupation through the admin interface — this triggers a full rebuild.

The rebuild process takes 30–120 seconds depending on dataset size and hardware.

### Health Monitoring

The system does not currently expose a dedicated health check endpoint. To verify operational status:

- **Application** — Send a GET request to `/`. A 200 response confirms the Flask server is running.
- **Search engine** — Send a POST to `/api/search` with a test query. A successful response with results confirms the full pipeline (SBERT model, FAISS index, PostgreSQL) is operational.
- **Database** — Connect directly to PostgreSQL and query the `occupations` table.

### Backup and Restore

**Database backup:**
Use `pg_dump` to create a full backup of the `statathon_nco` database. This captures all occupation data, search assets (as binary blobs), prompt history, and admin settings.

**Database restore:**
Use `pg_restore` or `psql` to restore from a dump file. After restoration, restart the application to reload all in-memory search assets from the database.

**Critical tables to back up:**
- `occupations` — Primary data, irreplaceable if the source CSV is not available.
- `admin_settings` — Contains the hashed admin password.
- `prompt_history` — Search telemetry history.

The `search_documents`, `nco_graph`, and `search_assets` tables can be regenerated from the occupation data and do not strictly need to be backed up.

### Incident Response

1. **Service is down** — Check `systemctl status nco-backend` (EC2) or process status (local). Review logs for crash reason. Restart the service.
2. **Search returns no results** — The FAISS index or search documents may be corrupt. Run the migration script to rebuild all assets.
3. **High latency on searches** — Check CPU and memory usage. The SBERT model encoding is the bottleneck. Consider increasing the TF-IDF fast-path threshold to bypass SBERT for more queries.
4. **Database connection errors** — Check PostgreSQL connection pool status. The pool maximum is 20 connections — if exceeded under load, increase `maxconn` in `db_store.py`.

---

## 11. Glossary and Definitions

| Term | Definition |
|------|-----------|
| **NCO** | National Classification of Occupations — India's standardized framework for classifying occupations. The current version is NCO 2015. |
| **NCO 2015** | The 2015 revision of the National Classification of Occupations. Uses an 8-digit code format: `XXXX.XXXX`. |
| **NCO 2004** | The previous 2004 revision. Uses a 6-digit code format: `XXXX.XX`. Maintained for backward compatibility. |
| **Division** | The broadest level of the NCO hierarchy (Level 1). Examples: "Managers", "Professionals", "Technicians". |
| **Sub-Division** | Level 2 of the NCO hierarchy, nested within a Division. |
| **Group** | Level 3 of the NCO hierarchy, nested within a Sub-Division. |
| **Family** | Level 4 of the NCO hierarchy, the most specific grouping above individual occupations. |
| **SBERT** | Sentence-BERT — a family of transformer models fine-tuned for sentence-level embeddings. This system uses the `BAAI/bge-small-en-v1.5` variant. |
| **FAISS** | Facebook AI Similarity Search — a library for efficient similarity search and clustering of dense vectors. |
| **TF-IDF** | Term Frequency–Inverse Document Frequency — a statistical measure of word importance in a document corpus. Used here for fast keyword matching. |
| **PIGS** | Prompt Intelligence and Guidance System — the module that analyzes query specificity and generates refinement suggestions. |
| **Bhashini** | India's national AI translation platform operated by MeitY (Ministry of Electronics and IT). Provides high-quality translation for Indian languages. |
| **PBKDF2** | Password-Based Key Derivation Function 2 — the key-stretching algorithm used to hash the admin password. |
| **CRUD** | Create, Read, Update, Delete — the four basic operations on persistent data. |
| **CORS** | Cross-Origin Resource Sharing — an HTTP mechanism that allows a frontend hosted on one domain to make requests to a backend on another domain. |

---

## 12. Release Notes — Version 1.0.0

**Version:** 1.0.0  
**Release Date:** 2026-06-11  
**Release Type:** General Availability  
**Compatibility:** This is the initial production release. No prior versions exist.  
**Urgency:** Routine release — no security patches.

---

### Breaking Changes

**Migration from CSV/SQLite to PostgreSQL**

All previous data storage (CSV files, SQLite databases, local JSON files) has been replaced by PostgreSQL as the single source of truth. Users migrating from the development prototype must run the `migrate_to_postgres.py` script to import existing data.

This is a one-way migration. The application no longer reads from or writes to local CSV, SQLite, or JSON files for operational data. The migration script handles the full transition automatically.

---

### New Features

**Hybrid Semantic Search Engine**

A three-stage retrieval pipeline that combines neural embeddings (SBERT), vector search (FAISS), and keyword matching (TF-IDF) to deliver highly relevant occupation classifications from natural-language queries. Supports configurable result counts (1–100) and two search modes: general semantic search and direct NCO code lookup.

Affects all users. Documented in Sections 4 and 6.

**Multilingual Query Support**

Search queries can now be submitted in 11 Indian languages. The system detects the query language and translates it to English before searching, using the Bhashini API with Google Translate as a fallback.

Supported: English, Hindi, Tamil, Telugu, Bengali, Marathi, Gujarati, Kannada, Malayalam, Punjabi, Urdu.

Affects all users.

**Prompt Intelligence and Guidance System (PIGS)**

An intelligent query analysis layer that evaluates how well a user's search query matches the NCO hierarchy at each level (Division, Sub-Division, Group, Family) and provides actionable suggestions to refine ambiguous queries.

Affects all users.

**Admin Dashboard with Real-Time Analytics**

A password-protected admin interface with six real-time analytics charts (division distribution, confidence distribution, top occupations, search trends, language breakdown, low-confidence queries) and a full CRUD interface for occupation management.

Affects administrators only.

**NCO Code Validation and Normalization**

Strict format enforcement for NCO codes: NCO 2015 requires `XXXX.XXXX` format, NCO 2004 requires `XXXX.XX` format. The system normalizes various input formats (missing dots, extra spaces, inconsistent digit counts) to the canonical form.

Affects administrators performing data entry.

**Decoupled Frontend Generation**

On startup, the application auto-generates a standalone frontend variant in the `frontend/` directory by transforming Flask template syntax into static HTML and rewriting API fetch calls to use a configurable base URL. This enables hosting the frontend independently from the Flask backend (e.g., on S3 or a CDN).

Affects deployment architects.

---

### Bug Fixes and Improvements

- **Duplicate NCO code prevention** — Both NCO 2015 and NCO 2004 codes are now checked for uniqueness before any add or edit operation, preventing data integrity issues.
- **Admin chart expansion issue** — Fixed a layout problem where analytics charts grew unbounded, causing excessive page height. Charts are now constrained to fixed card dimensions.
- **Password security hardening** — Replaced the previous plaintext password storage with PBKDF2-HMAC-SHA256 hashing (200,000 iterations, random 16-byte salt) and constant-time comparison.
- **Search asset rebuild reliability** — The in-memory search engine state is now hot-reloaded after every data mutation, eliminating stale-index issues that required server restarts.
- **TF-IDF fast path optimization** — Exact and near-exact occupation title matches now bypass the expensive SBERT model encoding entirely, reducing response time from approximately 200ms to sub-millisecond for these queries.
- **Translation caching** — Added an in-memory translation cache (2,048 entries) to avoid redundant external API calls for repeated queries.
- **Query embedding caching** — SBERT query embeddings are cached (256 entries) to avoid redundant model inference when the same query is searched multiple times within a session.

---

### Deprecations and Removals

**SQLite admin database (`data/admin.db`)**  
Deprecated. Admin settings are now stored in PostgreSQL. The migration script imports existing SQLite settings. The SQLite file is listed in `.gitignore` and will not be created by new installations.

**Local file-based storage**  
Removed. Embeddings, FAISS indexes, graph data, and search documents are no longer stored as local files (`models/`, `data/processed/`). All search assets are stored as binary blobs in PostgreSQL. The migration script cleans up legacy files. The `models/` and `data/processed/` directories are listed in `.gitignore`.

**Legacy pipeline scripts**  
The individual pipeline scripts (`01_preparation.py` through `05_searchGN.py`) have been moved to `scripts/legacy_pipeline/`. They are retained for reference but are not used by the current runtime. All pipeline operations are now performed by `migrate_to_postgres.py` and the inline rebuild functions in `app.py`.

---

### Known Issues

- **Full asset rebuild on every mutation** — Each add, edit, or delete operation triggers a complete re-encoding of all occupation embeddings and rebuilds all FAISS indexes. For the current dataset size (~2,000 occupations), this takes 30–120 seconds. This is acceptable for occasional edits but would become a bottleneck for bulk data imports. A partial/incremental rebuild mechanism is not yet implemented.

- **Flask debug mode enabled by default** — The `app.py` entry point runs with `debug=True`. Production deployments must use a WSGI server (Gunicorn, uWSGI) with debug mode disabled.

- **No session-based admin authentication** — The admin password must be sent with every write request. There is no session management or token-based authentication.

- **Admin dashboard HTML size** — The `templates/admin/dashboard.html` file is approximately 200 KB of inline HTML, CSS, and JavaScript. It functions correctly but would benefit from modularization into separate JS files.

- **No automated tests** — The project does not include a test suite. API validation logic, search ranking behavior, and admin workflows should be covered by automated tests before further development.

---

### Upgrade Instructions

This is the initial release. No upgrade path from a prior version is necessary. For fresh installations, follow Section 3 (Installation and Setup) of this document.

For users migrating from the development prototype:

1. Ensure PostgreSQL is installed and a database is created.
2. Set the `DATABASE_URL` in the `.env` file.
3. Run the migration script (`scripts/migrate_to_postgres.py`) to import all existing data.
4. Start the application. All legacy files will be cleaned up automatically.

---

*This document is the authoritative reference for the NCO Semantic Search System. It is maintained alongside the codebase and updated with each release. If you find an inaccuracy, please report it to the project maintainer.*
