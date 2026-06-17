import json
import os
import re
import sqlite3
import sys

from dotenv import load_dotenv
load_dotenv()  # Load .env before db_store reads DATABASE_URL

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_DIR not in sys.path:
    sys.path.append(PROJECT_DIR)

from database import db_store


CSV_PATH = os.path.join(PROJECT_DIR, "data", "raw", "nco_dataset_v6_final.csv")
PROMPT_HISTORY_PATH = os.path.join(PROJECT_DIR, "data", "processed", "prompt_history.json")
ADMIN_DB_PATH = os.path.join(PROJECT_DIR, "data", "admin.db")
MODEL_NAME = "intfloat/multilingual-e5-base"   # ⚠️ MUST match utils/searchapp.py MODEL_NAME (768 dims)
CORPUS_PREFIX = "passage: "   # multilingual-e5 requires this prefix for documents

# Auto-arrange dataset file if present in the root folder
import shutil
_root_csv = os.path.join(PROJECT_DIR, 'nco_dataset_v6_final.csv')
_target_csv = CSV_PATH
if os.path.exists(_root_csv):
    os.makedirs(os.path.dirname(_target_csv), exist_ok=True)
    try:
        shutil.move(_root_csv, _target_csv)
        print(f"Automatically moved {_root_csv} to {_target_csv}")
    except Exception as e:
        print(f"Failed to move CSV automatically: {e}")

# Auto-generate decoupled frontend assets
_src_index = os.path.join(PROJECT_DIR, 'templates', 'index.html')
_dst_index = os.path.join(PROJECT_DIR, 'frontend', 'index.html')
if os.path.exists(_src_index):
    os.makedirs(os.path.dirname(_dst_index), exist_ok=True)
    try:
        with open(_src_index, 'r', encoding='utf-8') as f:
            content = f.read()
        content = content.replace("{{ url_for('static', filename='gov-style.css') }}", "css/gov-style.css")
        content = content.replace('{{ url_for("static", filename="gov-style.css") }}', 'css/gov-style.css')
        if 'js/config.js' not in content:
            content = content.replace('</head>', '  <script src="js/config.js"></script>\n  </head>')
        content = re.sub(r'fetch\("(/api/[^"]*)"\)', r'fetch(window.API_BASE_URL + "\1")', content)
        content = re.sub(r'fetch\("(/api/[^"]*)",', r'fetch(window.API_BASE_URL + "\1",', content)
        content = re.sub(r"fetch\('(/api/[^']*)'\)", r"fetch(window.API_BASE_URL + '\1')", content)
        content = re.sub(r"fetch\('(/api/[^']*)',", r"fetch(window.API_BASE_URL + '\1',", content)
        content = re.sub(r'fetch\(`(/api/[^`]*)`\)', r'fetch(`${window.API_BASE_URL || ""}\1`)', content)
        content = re.sub(r'fetch\(`(/api/[^`]*)`,', r'fetch(`${window.API_BASE_URL || ""}\1`,', content)
        with open(_dst_index, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Automatically generated {_dst_index} from {_src_index}")
    except Exception as e:
        print(f"Failed to generate frontend/index.html automatically: {e}")

_src_admin = os.path.join(PROJECT_DIR, 'templates', 'admin', 'dashboard.html')
_dst_admin = os.path.join(PROJECT_DIR, 'frontend', 'admin.html')
if os.path.exists(_src_admin):
    os.makedirs(os.path.dirname(_dst_admin), exist_ok=True)
    try:
        with open(_src_admin, 'r', encoding='utf-8') as f:
            content = f.read()
        if 'js/config.js' not in content:
            content = content.replace('</head>', '  <script src="js/config.js"></script>\n  </head>')
        content = re.sub(r'fetch\("(/admin/api/[^"]*)"\)', r'fetch(window.API_BASE_URL + "\1")', content)
        content = re.sub(r'fetch\("(/api/[^"]*)"\)', r'fetch(window.API_BASE_URL + "\1")', content)
        content = re.sub(r'fetch\("(/admin/api/[^"]*)",', r'fetch(window.API_BASE_URL + "\1",', content)
        content = re.sub(r'fetch\("(/api/[^"]*)",', r'fetch(window.API_BASE_URL + "\1",', content)
        content = re.sub(r"fetch\('(/admin/api/[^']*)'\)", r"fetch(window.API_BASE_URL + '\1')", content)
        content = re.sub(r"fetch\('(/api/[^']*)'\)", r"fetch(window.API_BASE_URL + '\1')", content)
        content = re.sub(r"fetch\('(/admin/api/[^']*)',", r"fetch(window.API_BASE_URL + '\1',", content)
        content = re.sub(r"fetch\('(/api/[^']*)',", r"fetch(window.API_BASE_URL + '\1',", content)
        content = re.sub(r'fetch\(`(/admin/api/[^`]*)`\)', r'fetch(`${window.API_BASE_URL || ""}\1`)', content)
        content = re.sub(r'fetch\(`(/api/[^`]*)`\)', r'fetch(`${window.API_BASE_URL || ""}\1`)', content)
        content = re.sub(r'fetch\(`(/admin/api/[^`]*)`,', r'fetch(`${window.API_BASE_URL || ""}\1`,', content)
        content = re.sub(r'fetch\(`(/api/[^`]*)`,', r'fetch(`${window.API_BASE_URL || ""}\1`,', content)
        with open(_dst_admin, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Automatically generated {_dst_admin} from {_src_admin}")
    except Exception as e:
        print(f"Failed to generate frontend/admin.html automatically: {e}")

_src_css = os.path.join(PROJECT_DIR, 'static', 'gov-style.css')
_dst_css = os.path.join(PROJECT_DIR, 'frontend', 'css', 'gov-style.css')
if os.path.exists(_src_css):
    os.makedirs(os.path.dirname(_dst_css), exist_ok=True)
    try:
        shutil.copy2(_src_css, _dst_css)
        print(f"Automatically copied {_src_css} to {_dst_css}")
    except Exception as e:
        print(f"Failed to copy CSS: {e}")



def safe_text(value):
    if value is None:
        return ""
    return str(value).strip()


def build_documents_and_metadata(rows):
    documents = []
    metadata = []
    for idx, row in enumerate(rows):
        row_id = int(row.get("_row_id") or idx)
        doc = f"""
Occupation Title: {safe_text(row.get('Occupational Title'))}
NCO 2015 Code: {safe_text(row.get('NCO 2015'))}

Hierarchy:
Division: {safe_text(row.get('Division'))}
Sub Division: {safe_text(row.get('Sub Division'))}
Group: {safe_text(row.get('Group'))}
Family: {safe_text(row.get('Family'))}

Occupation Description:
{safe_text(row.get('Occupation Description'))}

Family Description:
{safe_text(row.get('Family Description'))}

Group Description:
{safe_text(row.get('Group Description'))}
""".strip()
        documents.append(doc)
        metadata.append({
            "row_id": row_id,
            "nco_2015": safe_text(row.get("NCO 2015")),
            "occupation_title": safe_text(row.get("Occupational Title")),
        })
    return documents, metadata


def build_graph(documents, metadata):
    graph = {}
    for idx, item in enumerate(metadata):
        code = item["nco_2015"]
        desc = documents[idx].lower() if idx < len(documents) else ""
        words = re.findall(r"\b[a-z]{3,}\b", desc)
        keywords = list(set(words))
        sector = "unknown"
        if "division:" in desc:
            for line in desc.split("\n"):
                if line.strip().startswith("division:"):
                    sector = line.split(":", 1)[1].strip().title()
                    break
        graph[code] = {"sector": sector, "keywords": keywords}
    return graph


def import_admin_settings():
    if not os.path.exists(ADMIN_DB_PATH):
        return
    conn = sqlite3.connect(ADMIN_DB_PATH)
    try:
        cur = conn.execute("SELECT key, value FROM admin_settings")
        for key, value in cur.fetchall():
            db_store.set_admin_setting(key, value)
    except sqlite3.Error:
        return
    finally:
        conn.close()


def rebuild_search_assets():
    _, rows = db_store.load_csv_rows()
    documents, metadata = build_documents_and_metadata(rows)
    db_store.save_search_documents(documents, metadata)

    # Save documents and metadata JSON files locally as well
    processed_dir = os.path.join(PROJECT_DIR, "data", "processed")
    os.makedirs(processed_dir, exist_ok=True)
    with open(os.path.join(processed_dir, "nco_documents.json"), "w", encoding="utf-8") as f:
        json.dump(documents, f, indent=2, ensure_ascii=False)
    with open(os.path.join(processed_dir, "nco_metadata.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    graph = build_graph(documents, metadata)
    db_store.save_graph(graph)

    # Save graph JSON file locally as well
    with open(os.path.join(processed_dir, "nco_graph.json"), "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)

    print("Loading SBERT model...")
    model = SentenceTransformer(MODEL_NAME)
    print("Generating embeddings with 'passage: ' prefix...")
    prefixed_docs = [CORPUS_PREFIX + doc for doc in documents]
    embeddings = model.encode(
        prefixed_docs,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    db_store.save_embeddings(embeddings)

    print("Building FAISS index...")
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    serialized_index = faiss.serialize_index(index)
    db_store.save_asset("nco_faiss.index", bytes(serialized_index), "application/x-faiss")


def main():
    print("Initializing PostgreSQL schema...")
    db_store.init_db()

    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(f"Missing source CSV: {CSV_PATH}")

    print("Importing occupations from CSV...")
    db_store.replace_occupations_from_csv(CSV_PATH)

    print("Importing prompt history JSON...")
    db_store.replace_prompt_history_from_json(PROMPT_HISTORY_PATH)

    print("Importing admin settings from SQLite...")
    import_admin_settings()

    print("Building PostgreSQL-backed search assets...")
    rebuild_search_assets()

    print("Migration complete.")
    print(f"Database URL: {db_store.DATABASE_URL}")

    # Cleanup unwanted legacy files that are now stored in PostgreSQL
    print("Cleaning up unwanted legacy files...")
    legacy_files = [
        os.path.join(PROJECT_DIR, "data", "raw", "data_with_descriptions.csv"),
        os.path.join(PROJECT_DIR, "models", "nco_embeddings.npy"),
        os.path.join(PROJECT_DIR, "models", "nco_faiss.index")
    ]
    for fpath in legacy_files:
        if os.path.exists(fpath):
            try:
                os.remove(fpath)
                print(f"Removed unwanted legacy file: {fpath}")
            except Exception as e:
                print(f"Failed to remove {fpath}: {e}")


if __name__ == "__main__":
    main()
