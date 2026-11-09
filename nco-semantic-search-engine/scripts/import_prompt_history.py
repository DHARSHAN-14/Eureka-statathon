"""
One-shot script: truncate prompt_history and import from a JSON file.

Usage:
    python scripts/import_prompt_history.py "C:\path\to\prompt_history.json"
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from database import db_store

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/import_prompt_history.py <path_to_json>")
        sys.exit(1)

    json_path = sys.argv[1]
    if not os.path.exists(json_path):
        print(f"File not found: {json_path}")
        sys.exit(1)

    print(f"Importing from: {json_path}")
    db_store.replace_prompt_history_from_json(json_path)
    print("Done. prompt_history table replaced with data from JSON.")
