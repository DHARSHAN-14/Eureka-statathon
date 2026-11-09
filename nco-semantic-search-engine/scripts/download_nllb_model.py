"""
Download and convert NLLB-200-distilled-600M to CTranslate2 format.

Usage:
    python scripts/download_nllb_model.py

This script:
  1. Downloads facebook/nllb-200-distilled-600M from HuggingFace Hub
  2. Converts it to CTranslate2 int8 format (~150 MB final size)
  3. Saves it to models/nllb-ct2/ with the sentencepiece tokenizer

Requirements (already handled by pip):
  - ctranslate2 >= 4.0
  - sentencepiece
  - transformers
  - huggingface_hub
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

ROOT_DIR   = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT_DIR / "models" / "nllb-ct2"
HF_CACHE   = ROOT_DIR / "models" / ".hf_cache"
MODEL_NAME = "facebook/nllb-200-distilled-600M"
QUANTIZE   = "int8"


def ensure_packages():
    required = {"ctranslate2", "sentencepiece", "transformers", "huggingface_hub"}
    for pkg in required:
        try:
            __import__(pkg.replace("-", "_"))
        except ImportError:
            print(f"  Installing {pkg}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", pkg])


def model_already_exists() -> bool:
    sp  = OUTPUT_DIR / "sentencepiece.bpe.model"
    mdl = OUTPUT_DIR / "model.bin"
    return sp.exists() and mdl.exists()


def main():
    print(f"\n{'='*60}")
    print(f"  NLLB-200 Model Setup")
    print(f"{'='*60}")
    print(f"  Model  : {MODEL_NAME}")
    print(f"  Output : {OUTPUT_DIR}")
    print(f"  Quant  : {QUANTIZE}")
    print(f"{'='*60}\n")

    ensure_packages()

    import ctranslate2
    from huggingface_hub import snapshot_download

    if model_already_exists():
        print(f"[OK] Model already present at {OUTPUT_DIR}")
        print("    Delete the directory to force a re-download.\n")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    HF_CACHE.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Step 1: Download model weights from HuggingFace
    # ------------------------------------------------------------------ #
    print("[1/3] Downloading model from HuggingFace Hub...")
    print("      (~1.2 GB download, may take a few minutes)\n")
    local_model_path = snapshot_download(
        repo_id=MODEL_NAME,
        cache_dir=str(HF_CACHE),
        ignore_patterns=["*.msgpack", "*.h5", "flax_model*", "tf_model*", "rust_model*"],
    )
    print(f"\n[OK] Model downloaded to: {local_model_path}\n")

    # ------------------------------------------------------------------ #
    # Step 2: Convert to CTranslate2 format
    # ------------------------------------------------------------------ #
    print(f"[2/3] Converting to CTranslate2 ({QUANTIZE}) format...")
    converter = ctranslate2.converters.TransformersConverter(
        model_name_or_path=local_model_path,
        low_cpu_mem_usage=True,
    )
    converter.convert(
        output_dir=str(OUTPUT_DIR),
        quantization=QUANTIZE,
        force=True,
    )
    print(f"[OK] Converted model saved to {OUTPUT_DIR}\n")

    # ------------------------------------------------------------------ #
    # Step 3: Copy the sentencepiece tokenizer
    # ------------------------------------------------------------------ #
    print("[3/3] Copying sentencepiece tokenizer...")
    sp_src = Path(local_model_path) / "sentencepiece.bpe.model"
    if not sp_src.exists():
        # Try recursive search in cache
        candidates = list(Path(local_model_path).rglob("sentencepiece.bpe.model"))
        if candidates:
            sp_src = candidates[0]

    if not sp_src.exists():
        print(f"[!] sentencepiece.bpe.model not found in {local_model_path}")
        print("    Translation will not work — check the HuggingFace cache manually.")
        sys.exit(1)

    shutil.copy2(sp_src, OUTPUT_DIR / "sentencepiece.bpe.model")
    print(f"[OK] Sentencepiece model copied.\n")

    # ------------------------------------------------------------------ #
    # Done
    # ------------------------------------------------------------------ #
    print(f"{'='*60}")
    print(f"  Setup complete! Files in {OUTPUT_DIR}:")
    for f in sorted(OUTPUT_DIR.iterdir()):
        size_mb = f.stat().st_size / 1_048_576
        print(f"    {f.name:<40} {size_mb:>7.1f} MB")
    print(f"{'='*60}\n")
    print("  Next step: PREFERRED_TRANSLATION_SERVICE=nllb is set in .env\n")


if __name__ == "__main__":
    main()
