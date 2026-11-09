# README.md

## Introduction
This project is a Flask-based AI semantic search system for the **National Classification of Occupations (NCO)**. It helps users find the right NCO occupation/code from natural-language queries and supports multilingual input with translation.

The application has two major surfaces:
- **Public Search UI** (`/`): semantic search, NCO-code search mode, translation-aware querying, and guided prompt suggestions.
- **Admin Dashboard** (`/admin`): real-time analytics and controlled occupation database management (add/edit/delete with password protection and strict NCO validation).

## Key Features
- Hybrid semantic retrieval (SBERT + FAISS + graph keyword signals)
- NCO code normalization and direct lookup mode
- Prompt Intelligence (PIGS) suggestions for better query quality
- Multi-language query handling with ambiguity prompts
- Admin CRUD with strict format/duplicate validations:
  - NCO 2015: `XXXX.XXXX`
  - NCO 2004: `XXXX.XX`
- PostgreSQL-backed storage for occupations, admin settings, prompt history, semantic documents, graph data, embeddings, and FAISS index bytes

## Quick Start
1. Create a PostgreSQL database, for example `statathon_nco`.
2. Create a `.env` file in the project root with your database credentials and admin password:
   ```env
   DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/statathon_nco
   ADMIN_PASSWORD=your_secure_admin_password
   SECRET_KEY=your_random_secret_key
   ```
   > **Note:** The `.env` file is git-ignored and never committed. `ADMIN_PASSWORD` is hashed with PBKDF2-SHA256 and stored in PostgreSQL on first startup — the plaintext is never persisted. Do not use `set` or `$env:` — the app loads credentials automatically via `python-dotenv`.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Import the current CSV/JSON/SQLite data and build search assets:
   ```bash
   python scripts/migrate_to_postgres.py
   ```
5. Run server:
   ```bash
   python app.py
   ```
6. Open:
   - `http://127.0.0.1:5000/`
   - `http://127.0.0.1:5000/admin`

## Documentation
For deep technical architecture, routes, data flow, validations, status, and maintenance notes, see:
- `docs/PROJECT_DOCUMENTATION.md`
