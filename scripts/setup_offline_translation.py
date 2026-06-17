import os
import shutil
import subprocess
import sys

def main():
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    models_dir = os.path.join(project_dir, "models")
    output_dir = os.path.join(models_dir, "nllb-ct2")
    
    print("=== NLLB-200 Offline Translation Setup ===")
    
    # 1. Create models directory
    os.makedirs(models_dir, exist_ok=True)
    
    # 2. Check if model already exists
    if os.path.exists(os.path.join(output_dir, "model.bin")) and os.path.exists(os.path.join(output_dir, "shared_vocabulary.json")):
        print(f"Model already exists at: {output_dir}")
        print("Checking for tokenizer model file...")
        sp_target = os.path.join(output_dir, "sentencepiece.bpe.model")
        if not os.path.exists(sp_target):
            # Try to locate in cache and copy
            try:
                from huggingface_hub import snapshot_download
                local_model_dir = snapshot_download(
                    repo_id="facebook/nllb-200-distilled-600M",
                    ignore_patterns=["*.msgpack", "*.h5", "*.ot", "rust_model.ot"]
                )
                sp_source = os.path.join(local_model_dir, "sentencepiece.bpe.model")
                if os.path.exists(sp_source):
                    shutil.copy(sp_source, sp_target)
                    print(f"Copied sentencepiece model to {sp_target}")
            except Exception as e:
                print(f"Warning: Could not copy tokenizer from cache: {e}")
        else:
            print("Tokenizer model file already exists. Skipping download and conversion.")
            return
        
    print(f"Target model directory: {output_dir}")
    print("Downloading 'facebook/nllb-200-distilled-600M' using huggingface_hub...")
    print("Note: This will download ~1.1GB, please be patient.")
    
    try:
        from huggingface_hub import snapshot_download
        local_model_dir = snapshot_download(
            repo_id="facebook/nllb-200-distilled-600M",
            ignore_patterns=["*.msgpack", "*.h5", "*.ot", "rust_model.ot"]
        )
        print(f"Model downloaded to Hugging Face cache: {local_model_dir}")
    except Exception as e:
        print(f"Error downloading model: {e}")
        sys.exit(1)
        
    print("Converting downloaded model to int8 CTranslate2 format (low CPU memory mode)...")
    python_exe = sys.executable
    converter_cmd = [
        python_exe, "-m", "ctranslate2.converters.transformers",
        "--model", local_model_dir,
        "--quantization", "int8",
        "--low_cpu_mem_usage",
        "--output_dir", output_dir
    ]
    
    print(f"Executing: {' '.join(converter_cmd)}")
    try:
        subprocess.check_call(converter_cmd)
        print("\nModel converted successfully!")
    except subprocess.CalledProcessError as e:
        print(f"\nError: Model conversion failed with exit code {e.returncode}")
        sys.exit(e.returncode)
        
    # Copy sentencepiece tokenizer model to output directory
    sp_source = os.path.join(local_model_dir, "sentencepiece.bpe.model")
    sp_target = os.path.join(output_dir, "sentencepiece.bpe.model")
    if os.path.exists(sp_source):
        shutil.copy(sp_source, sp_target)
        print(f"Copied sentencepiece model to {sp_target}")
        print("Offline NLLB-200 translation model setup successfully!")
    else:
        print(f"Error: sentencepiece.bpe.model not found in downloaded snapshot: {local_model_dir}")
        sys.exit(1)

if __name__ == "__main__":
    main()
