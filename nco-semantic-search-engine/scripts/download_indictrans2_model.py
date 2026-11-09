"""
Download and set up IndicTrans2 Indic-to-English distilled 200M model in CTranslate2 format.

Usage:
    python scripts/download_indictrans2_model.py
"""

import os
import sys
import shutil
from pathlib import Path

ROOT_DIR   = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT_DIR / "models" / "indictrans2-ct2"
HF_CACHE   = ROOT_DIR / "models" / ".hf_cache"
MODEL_NAME = "adalat-ai/ct2-rotary-indictrans2-indic-en-dist-200M"

def ensure_packages():
    required = {"ctranslate2", "sentencepiece", "huggingface_hub", "IndicTransToolkit"}
    for pkg in required:
        try:
            __import__(pkg.replace("-", "_"))
        except ImportError:
            import subprocess
            print(f"  Installing {pkg}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", pkg])

def model_already_exists() -> bool:
    bin_file = OUTPUT_DIR / "model.bin"
    src_vocab = OUTPUT_DIR / "source_vocabulary.json"
    tgt_vocab = OUTPUT_DIR / "target_vocabulary.json"
    src_spm = OUTPUT_DIR / "vocab" / "model.SRC"
    tgt_spm = OUTPUT_DIR / "vocab" / "model.TGT"
    return bin_file.exists() and src_vocab.exists() and tgt_vocab.exists() and src_spm.exists() and tgt_spm.exists()

def main():
    print(f"\n{'='*60}")
    print(f"  IndicTrans2 Model Setup (CTranslate2)")
    print(f"{'='*60}")
    print(f"  Model  : {MODEL_NAME}")
    print(f"  Output : {OUTPUT_DIR}")
    print(f"{'='*60}\n")

    ensure_packages()

    from huggingface_hub import snapshot_download

    if model_already_exists():
        print(f"[OK] Model already present at {OUTPUT_DIR}")
        print("    Delete the directory to force a re-download.\n")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    HF_CACHE.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Step 1: Download model from HuggingFace
    # ------------------------------------------------------------------ #
    print("[1/2] Downloading model from HuggingFace Hub...")
    print("      (~850 MB download, may take a few minutes)\n")
    local_model_path = snapshot_download(
        repo_id=MODEL_NAME,
        cache_dir=str(HF_CACHE),
    )
    print(f"\n[OK] Model downloaded to HuggingFace cache.\n")

    # ------------------------------------------------------------------ #
    # Step 2: Copy model files to models/indictrans2-ct2/
    # ------------------------------------------------------------------ #
    print("[2/2] Extracting and setting up CTranslate2 files...")
    src_ct2_dir = Path(local_model_path) / "indic-en-200m-ct2" / "ctranslate2_model"
    
    if not src_ct2_dir.exists():
        # Try recursive search in cache
        candidates = list(Path(local_model_path).rglob("ctranslate2_model"))
        if candidates:
            src_ct2_dir = candidates[0]

    if not src_ct2_dir.exists():
        print(f"[!] ctranslate2_model directory not found in {local_model_path}")
        print("    Setup failed.")
        sys.exit(1)

    # Copy files
    for item in src_ct2_dir.iterdir():
        dest_path = OUTPUT_DIR / item.name
        if item.is_dir():
            if dest_path.exists():
                shutil.rmtree(dest_path)
            shutil.copytree(item, dest_path)
        else:
            shutil.copy2(item, dest_path)

    print(f"[OK] Converted model saved to {OUTPUT_DIR}\n")

    # ------------------------------------------------------------------ #
    # Done
    # ------------------------------------------------------------------ #
    print(f"{'='*60}")
    print(f"  Setup complete! Files in {OUTPUT_DIR}:")
    for f in sorted(OUTPUT_DIR.rglob("*")):
        if f.is_file():
            rel_path = f.relative_to(OUTPUT_DIR)
            size_mb = f.stat().st_size / 1_048_576
            print(f"    {str(rel_path):<40} {size_mb:>7.1f} MB")
    print(f"{'='*60}\n")
    print("  Next step: Update your .env to use the new model path.\n")

if __name__ == "__main__":
    main()
