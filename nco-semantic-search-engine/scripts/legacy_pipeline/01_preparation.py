import os
import sys

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_DIR not in sys.path:
    sys.path.append(PROJECT_DIR)

from database import db_store
from migrate_to_postgres import build_documents_and_metadata


if __name__ == "__main__":
    db_store.init_db()
    _, rows = db_store.load_csv_rows()
    documents, metadata = build_documents_and_metadata(rows)
    db_store.save_search_documents(documents, metadata)
    print(f"Created {len(documents)} semantic documents in PostgreSQL")
