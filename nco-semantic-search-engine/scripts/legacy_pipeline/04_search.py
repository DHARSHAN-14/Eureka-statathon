import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
if SCRIPT_DIR not in sys.path:
    sys.path.append(SCRIPT_DIR)
if PROJECT_DIR not in sys.path:
    sys.path.append(PROJECT_DIR)

import importlib.util


spec = importlib.util.spec_from_file_location("searchapp", os.path.join(SCRIPT_DIR, "06_searchapp.py"))
searchapp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(searchapp)


if __name__ == "__main__":
    while True:
        query = input("Enter occupation query (or 'exit'): ").strip()
        if query.lower() == "exit":
            break
        results = searchapp.search(query)
        searchapp.display_results(query, results)
