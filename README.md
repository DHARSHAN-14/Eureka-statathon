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

## Quick Start
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run server:
   ```bash
   python app.py
   ```
3. Open:
   - `http://127.0.0.1:5000/`
   - `http://127.0.0.1:5000/admin`

## Documentation
For deep technical architecture, routes, data flow, validations, status, and maintenance notes, see:
- `PROJECT_DOCUMENTATION.md`
