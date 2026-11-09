import os
import sys

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_DIR not in sys.path:
    sys.path.append(PROJECT_DIR)

from database import db_store
from migrate_to_postgres import build_graph


if __name__ == "__main__":
    db_store.init_db()
    documents, metadata = db_store.load_search_documents()
    graph = build_graph(documents, metadata)
    db_store.save_graph(graph)
    print(f"Created graph with {len(graph)} nodes in PostgreSQL")
