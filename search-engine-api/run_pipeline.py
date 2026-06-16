#!/usr/bin/env python3
"""
Run the full NCO search engine data pipeline.

Steps:
  1. Prepare documents and metadata from CSV
  2. Build graph network (GN) for keyword reranking
  3. Generate SBERT embeddings
  4. Build FAISS index

Run from the search-engine-api root:
    python run_pipeline.py
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / "scripts"

STEPS = [
    ("01_preparation.py", "Prepare documents and metadata from CSV"),
    ("05_searchGN.py", "Build graph network for reranking"),
    ("02_generateEmbedding.py", "Generate SBERT embeddings"),
    ("03_build_faiss_index.py", "Build FAISS index"),
]


def run_step(script_name, description):
    script_path = SCRIPTS / script_name
    if not script_path.exists():
        print(f"ERROR: Missing script {script_path}")
        sys.exit(1)

    print(f"\n{'=' * 60}")
    print(f"STEP: {description}")
    print(f"Script: {script_name}")
    print("=" * 60)

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=ROOT,
        check=False,
    )
    if result.returncode != 0:
        print(f"\nPipeline failed at {script_name} (exit code {result.returncode})")
        sys.exit(result.returncode)


def main():
    print("NCO Search Engine — Full Pipeline")
    print(f"Working directory: {ROOT}")

    csv_path = ROOT / "data" / "raw" / "nco_dataset_v3.csv"
    if not csv_path.exists():
        print(f"ERROR: Input CSV not found: {csv_path}")
        sys.exit(1)

    for script_name, description in STEPS:
        run_step(script_name, description)

    print(f"\n{'=' * 60}")
    print("Pipeline completed successfully.")
    print("Outputs:")
    print("  - data/processed/nco_documents.json")
    print("  - data/processed/nco_metadata.json")
    print("  - data/processed/nco_graph.json")
    print("  - models/nco_embeddings.npy")
    print("  - models/nco_faiss.index")
    print("=" * 60)
    print("\nStart the API with: python api.py")


if __name__ == "__main__":
    main()
