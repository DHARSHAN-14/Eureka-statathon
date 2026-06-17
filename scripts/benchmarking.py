# =============================================================================
# NCO JOB TITLE EMBEDDING MODEL BENCHMARK
# =============================================================================
# Run this on Kaggle (GPU T4) for best results (~1 hour for all 6 models)
# Upload: data/raw/benchmark_dataset_multilingual.csv  to Kaggle dataset
#
# Metrics: Top-1/3/5 Accuracy, MRR, Encode Speed, Query Latency, Memory
# Breakdowns: by language, query_type, difficulty
# Output: benchmark_results_summary.csv, benchmark_results_detailed.csv,
#         benchmark_report.md
# =============================================================================

# -- CELL 1: Install / verify dependencies -------------------------------------
import subprocess, sys

def pip_install(pkg):
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", pkg])

try:
    import sentence_transformers
except ImportError:
    pip_install("sentence-transformers")

try:
    import psutil
except ImportError:
    pip_install("psutil")

# -- CELL 2: Imports ------------------------------------------------------------
import os
import gc
import time
import tracemalloc
import warnings
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import psutil
import torch
from sentence_transformers import SentenceTransformer

warnings.filterwarnings("ignore")

print("PyTorch version   : " + str(torch.__version__))
print("CUDA available    : " + str(torch.cuda.is_available()))
if torch.cuda.is_available():
    print("GPU               : " + str(torch.cuda.get_device_name(0)))
    print("GPU VRAM          : %.1f GB" % (torch.cuda.get_device_properties(0).total_memory / 1e9))
print("RAM available     : %.1f GB" % (psutil.virtual_memory().available / 1e9))

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print("\nRunning on        : " + DEVICE.upper())

# -- CELL 3: Configuration -----------------------------------------------------

# === Dataset path -- update if your Kaggle dataset slug differs ===
DATASET_PATH = "/kaggle/input/datasets/mohamedak/nco-benchmark/benchmark_dataset_multilingual.csv"
if not os.path.exists(DATASET_PATH):
    # Second Kaggle path variant (older slug format)
    DATASET_PATH = "/kaggle/input/nco-benchmark/benchmark_dataset_multilingual.csv"
if not os.path.exists(DATASET_PATH):
    # Local fallback (works when running as a .py script, not a notebook)
    _base = os.path.dirname(os.path.abspath(globals().get('__file__', os.getcwd())))
    DATASET_PATH = os.path.join(_base, "data", "raw", "benchmark_dataset_multilingual.csv")

OUTPUT_DIR = Path("/kaggle/working") if os.path.exists("/kaggle") else Path("data/benchmark_output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TOP_K_VALUES = [1, 3, 5]

# Optimal batch sizes per model for T4 (16GB VRAM)
# Reduce if you hit OOM errors
MODELS = [
    {
        "name": "all-MiniLM-L6-v2",
        "hf_id": "all-MiniLM-L6-v2",
        "dim": 384,
        "batch_size": 512,
        "notes": "Fastest, lowest memory",
    },
    {
        "name": "BAAI/bge-small-en-v1.5",
        "hf_id": "BAAI/bge-small-en-v1.5",
        "dim": 384,
        "batch_size": 512,
        "notes": "Fast, strong accuracy",
    },
    {
        "name": "thenlper/gte-base",
        "hf_id": "thenlper/gte-base",
        "dim": 768,
        "batch_size": 256,
        "notes": "Medium size, good accuracy",
    },
    {
        "name": "intfloat/multilingual-e5-base",
        "hf_id": "intfloat/multilingual-e5-base",
        "dim": 768,
        "batch_size": 256,
        "notes": "Best for multilingual queries",
        "query_prefix": "query: ",      # e5 models need prefix
        "corpus_prefix": "passage: ",
    },
    {
        "name": "BAAI/bge-large-en-v1.5",
        "hf_id": "BAAI/bge-large-en-v1.5",
        "dim": 1024,
        "batch_size": 128,
        "notes": "High accuracy, larger model",
    },
    {
        "name": "hkunlp/instructor-xl",
        "hf_id": "hkunlp/instructor-xl",
        "dim": 768,
        "batch_size": 64,
        "notes": "Highest accuracy, instruction-tuned",
        "instruction_query": "Represent the job search query for finding the NCO job title: ",
        "instruction_corpus": "Represent the NCO job title for semantic search: ",
    },
]

print("\nDataset path : " + str(DATASET_PATH))
print("Output dir   : " + str(OUTPUT_DIR))
print("Models to run: " + str(len(MODELS)))
print("Top-K values : " + str(TOP_K_VALUES))

# -- CELL 4: Load Dataset ------------------------------------------------------

print("\n" + "="*60)
print("LOADING DATASET")
print("="*60)

df = pd.read_csv(DATASET_PATH, encoding="utf-8-sig")
df.columns = df.columns.str.strip()

print("Total queries     : " + format(len(df), ","))
print("Columns           : " + str(list(df.columns)))
print("\nLanguages         : " + str(sorted(df['language'].unique())))
print("Query types       : " + str(sorted(df['query_type'].unique())))
print("Difficulties      : " + str(sorted(df['difficulty'].unique())))

# Build corpus: unique (nco_code, title) pairs
corpus_df = df[["expected_nco_code", "expected_title"]].drop_duplicates().reset_index(drop=True)
corpus_df = corpus_df.sort_values("expected_nco_code").reset_index(drop=True)

CORPUS_TEXTS = corpus_df["expected_title"].tolist()
CORPUS_CODES = corpus_df["expected_nco_code"].tolist()

# Build fast lookup: code -> index in corpus
CODE_TO_IDX = {code: idx for idx, code in enumerate(CORPUS_CODES)}

# Queries
QUERIES      = df["query"].tolist()
QUERY_CODES  = df["expected_nco_code"].tolist()

print("\nCorpus size       : " + format(len(CORPUS_TEXTS), ",") + " unique NCO titles")
print("Query count       : " + format(len(QUERIES), ","))

# -- CELL 5: Helper Functions --------------------------------------------------

def get_gpu_memory_mb():
    """Returns currently allocated GPU memory in MB, or 0 if no GPU."""
    if torch.cuda.is_available():
        return torch.cuda.memory_allocated() / 1e6
    return 0.0

def get_peak_ram_mb():
    """Returns current process RSS RAM in MB."""
    return psutil.Process(os.getpid()).memory_info().rss / 1e6

def flush_gpu():
    """Clear GPU cache between models."""
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
    gc.collect()

def encode_texts(model, texts, batch_size, prefix=None, instruction=None, show_progress=True):
    """
    Encode a list of texts with optional prefix (e5) or instruction (instructor).
    Returns normalized numpy embeddings.
    """
    if instruction is not None:
        # instructor models use (instruction, text) tuples
        inputs = [[instruction, t] for t in texts]
    elif prefix is not None:
        inputs = [prefix + t for t in texts]
    else:
        inputs = texts

    embeddings = model.encode(
        inputs,
        batch_size=batch_size,
        show_progress_bar=show_progress,
        convert_to_numpy=True,
        normalize_embeddings=True,
        device=DEVICE,
    )
    return embeddings  # shape: (N, dim), already L2-normalized

def cosine_similarity_matrix(query_embs, corpus_embs, chunk_size=2000):
    """
    Compute cosine similarity between query_embs and corpus_embs in chunks.
    Since embeddings are L2-normalized, cosine sim = dot product.
    Returns top-5 (indices, scores) per query to save memory.
    """
    max_k = max(TOP_K_VALUES)
    n_queries = len(query_embs)

    top_indices = np.zeros((n_queries, max_k), dtype=np.int32)
    top_scores  = np.zeros((n_queries, max_k), dtype=np.float32)

    corpus_t = torch.tensor(corpus_embs, dtype=torch.float32)
    if torch.cuda.is_available():
        corpus_t = corpus_t.cuda()

    for start in range(0, n_queries, chunk_size):
        end   = min(start + chunk_size, n_queries)
        chunk = torch.tensor(query_embs[start:end], dtype=torch.float32)
        if torch.cuda.is_available():
            chunk = chunk.cuda()

        sims = torch.mm(chunk, corpus_t.T)  # (chunk_size, corpus_size)
        topk = torch.topk(sims, k=max_k, dim=1)

        top_indices[start:end] = topk.indices.cpu().numpy()
        top_scores[start:end]  = topk.values.cpu().numpy()

        del chunk, sims, topk

    del corpus_t
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return top_indices, top_scores

def compute_metrics(top_indices, query_codes, df):
    """
    Compute all metrics from top-K search results.
    Returns (summary_dict, per_query_records).
    """
    n = len(query_codes)
    per_query = []
    reciprocal_ranks = []

    # Per-slice accumulators: {slice_key: {k: [hit/miss, ...]}}
    slice_keys = ["language", "query_type", "difficulty"]
    slice_hits = {sk: defaultdict(lambda: defaultdict(list)) for sk in slice_keys}
    slice_rr   = {sk: defaultdict(list) for sk in slice_keys}

    for i in range(n):
        correct_code = query_codes[i]
        correct_idx  = CODE_TO_IDX.get(correct_code, -1)

        # Find rank of correct answer (1-indexed), -1 if not in top-K
        predicted_indices = top_indices[i]  # array of corpus indices
        rank = -1
        for r, idx in enumerate(predicted_indices):
            if idx == correct_idx:
                rank = r + 1
                break

        rr = 1.0 / rank if rank > 0 else 0.0
        reciprocal_ranks.append(rr)

        row = df.iloc[i]
        rec = {
            "query_id":       row["query_id"],
            "language":       row["language"],
            "query_type":     row["query_type"],
            "difficulty":     row["difficulty"],
            "correct_code":   correct_code,
            "rank":           rank,
            "reciprocal_rank": rr,
        }
        for k in TOP_K_VALUES:
            hit = 1 if (0 < rank <= k) else 0
            rec["hit@" + str(k)] = hit

        per_query.append(rec)

        # Accumulate slice metrics
        for sk in slice_keys:
            sv = row[sk]
            for k in TOP_K_VALUES:
                slice_hits[sk][sv][k].append(rec["hit@" + str(k)])
            slice_rr[sk][sv].append(rr)

    # Aggregate
    summary = {}
    for k in TOP_K_VALUES:
        hits = [r["hit@" + str(k)] for r in per_query]
        summary["top" + str(k) + "_accuracy"] = round(np.mean(hits) * 100, 2)

    summary["mrr"] = round(np.mean(reciprocal_ranks), 4)

    # Slice breakdowns
    for sk in slice_keys:
        for sv, kdict in slice_hits[sk].items():
            for k in TOP_K_VALUES:
                key = str(sk) + "_" + str(sv) + "_top" + str(k)
                summary[key] = round(np.mean(kdict[k]) * 100, 2)
        for sv, rrs in slice_rr[sk].items():
            summary[str(sk) + "_" + str(sv) + "_mrr"] = round(np.mean(rrs), 4)

    return summary, per_query

# -- CELL 6: Main Benchmark Loop -----------------------------------------------

print("\n" + "="*60)
print("STARTING BENCHMARK")
print("="*60)

all_summaries   = []   # one dict per model
all_per_query   = []   # one dict per (model, query)

for m_cfg in MODELS:
    model_name = m_cfg["name"]
    hf_id      = m_cfg["hf_id"]
    batch_size = m_cfg["batch_size"]

    print("\n" + "-"*60)
    print("Model: " + str(model_name))
    print("-"*60)

    flush_gpu()
    ram_before = get_peak_ram_mb()
    gpu_before = get_gpu_memory_mb()

    # -- Load model ------------------------------------------------
    t0 = time.time()
    model = SentenceTransformer(hf_id, device=DEVICE)
    load_time = time.time() - t0
    print("  [ok] Model loaded in %.1fs" % load_time)

    # -- Encode corpus ---------------------------------------------
    print("  Encoding " + format(len(CORPUS_TEXTS), ",") + " corpus titles...")
    corpus_prefix      = m_cfg.get("corpus_prefix")
    corpus_instruction = m_cfg.get("instruction_corpus")

    t1 = time.time()
    corpus_embs = encode_texts(
        model, CORPUS_TEXTS, batch_size,
        prefix=corpus_prefix, instruction=corpus_instruction
    )
    corpus_encode_time = time.time() - t1
    corpus_speed = len(CORPUS_TEXTS) / corpus_encode_time
    print("  [ok] Corpus encoded in %.1fs  (%.0f docs/sec)" % (corpus_encode_time, corpus_speed))

    # -- Encode queries --------------------------------------------
    print("  Encoding " + format(len(QUERIES), ",") + " queries...")
    query_prefix      = m_cfg.get("query_prefix")
    query_instruction = m_cfg.get("instruction_query")

    t2 = time.time()
    query_embs = encode_texts(
        model, QUERIES, batch_size,
        prefix=query_prefix, instruction=query_instruction
    )
    query_encode_time = time.time() - t2
    query_speed       = len(QUERIES) / query_encode_time
    avg_latency_ms    = (query_encode_time / len(QUERIES)) * 1000
    print("  [ok] Queries encoded in %.1fs  (%.0f q/sec, %.2f ms/query)" % (query_encode_time, query_speed, avg_latency_ms))

    # Peak memory after encoding
    ram_after = get_peak_ram_mb()
    gpu_after = get_gpu_memory_mb()
    peak_ram_mb = ram_after - ram_before
    peak_gpu_mb = gpu_after - gpu_before

    # -- Similarity search -----------------------------------------
    print("  Computing cosine similarity (top-" + str(max(TOP_K_VALUES)) + ")...")
    t3 = time.time()
    top_indices, top_scores = cosine_similarity_matrix(query_embs, corpus_embs)
    search_time = time.time() - t3
    print("  [ok] Search done in %.1fs" % search_time)

    # -- Score -----------------------------------------------------
    print(f"  Computing metrics...")
    metrics, per_query_rows = compute_metrics(top_indices, QUERY_CODES, df)

    # -- Build summary row -----------------------------------------
    total_time = load_time + corpus_encode_time + query_encode_time + search_time
    summary = {
        "model":                 model_name,
        "embedding_dim":         corpus_embs.shape[1],
        "total_time_sec":        round(total_time, 1),
        "load_time_sec":         round(load_time, 1),
        "corpus_encode_sec":     round(corpus_encode_time, 1),
        "corpus_speed_docs_sec": round(corpus_speed, 0),
        "query_encode_sec":      round(query_encode_time, 1),
        "query_speed_q_sec":     round(query_speed, 0),
        "avg_latency_ms":        round(avg_latency_ms, 3),
        "search_time_sec":       round(search_time, 1),
        "peak_ram_delta_mb":     round(peak_ram_mb, 1),
        "peak_gpu_delta_mb":     round(peak_gpu_mb, 1),
        "device":                DEVICE,
        **metrics,
    }

    all_summaries.append(summary)
    for row in per_query_rows:
        row["model"] = model_name
    all_per_query.extend(per_query_rows)

    # Print quick results
    print("\n  -- RESULTS ------------------------------------------")
    print("  Top-1 Accuracy : " + str(metrics['top1_accuracy']) + "%")
    print("  Top-3 Accuracy : " + str(metrics['top3_accuracy']) + "%")
    print("  Top-5 Accuracy : " + str(metrics['top5_accuracy']) + "%")
    print("  MRR            : " + str(metrics['mrr']))
    print("  Total Time     : %.1fs" % total_time)
    print("  Peak RAM delta : %.0f MB" % peak_ram_mb)
    if torch.cuda.is_available():
        print("  Peak GPU delta : %.0f MB" % peak_gpu_mb)
    print("  -----------------------------------------------------")

    # Save checkpoint after each model (don't lose progress)
    chk_path = OUTPUT_DIR / ("checkpoint_" + model_name.replace('/', '_') + ".csv")
    pd.DataFrame([summary]).to_csv(chk_path, index=False)
    print("  [ok] Checkpoint saved: " + chk_path.name)

    # Cleanup
    del model, corpus_embs, query_embs, top_indices, top_scores
    flush_gpu()

# -- CELL 7: Save Results ------------------------------------------------------

print("\n" + "="*60)
print("SAVING RESULTS")
print("="*60)

summary_df  = pd.DataFrame(all_summaries)
detailed_df = pd.DataFrame(all_per_query)

summary_path  = OUTPUT_DIR / "benchmark_results_summary.csv"
detailed_path = OUTPUT_DIR / "benchmark_results_detailed.csv"

summary_df.to_csv(summary_path, index=False)
detailed_df.to_csv(detailed_path, index=False)

print("[ok] Summary  -> " + str(summary_path))
print("[ok] Detailed -> " + str(detailed_path))

# -- CELL 8: Generate Markdown Report -----------------------------------------

def generate_report(summary_df):
    lines = []
    now   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines.append("# Embedding Model Benchmark Report")
    lines.append("*Generated: " + str(now) + " | Device: " + DEVICE.upper() + "*\n")

    # -- Overall Rankings --
    lines.append("## 📊 Overall Rankings\n")
    ranked = summary_df.sort_values("top1_accuracy", ascending=False)

    # Core metrics table
    cols = ["model", "top1_accuracy", "top3_accuracy", "top5_accuracy", "mrr",
            "avg_latency_ms", "corpus_speed_docs_sec", "peak_ram_delta_mb", "total_time_sec"]
    col_labels = ["Model", "Top-1 %", "Top-3 %", "Top-5 %", "MRR",
                  "Latency (ms)", "Speed (doc/s)", "RAM δ (MB)", "Time (s)"]

    header = "| " + " | ".join(col_labels) + " |"
    sep    = "| " + " | ".join(["---"] * len(col_labels)) + " |"
    lines.append(header)
    lines.append(sep)
    for _, row in ranked.iterrows():
        vals = [str(row.get(c, "N/A")) for c in cols]
        lines.append("| " + " | ".join(vals) + " |")

    lines.append("")

    # -- Best model per criterion --
    lines.append("## 🏆 Best Model per Criterion\n")
    criteria = {
        "Highest Top-1 Accuracy":  summary_df.loc[summary_df["top1_accuracy"].idxmax(), "model"],
        "Highest MRR":             summary_df.loc[summary_df["mrr"].idxmax(), "model"],
        "Fastest Encoding":        summary_df.loc[summary_df["query_speed_q_sec"].idxmax(), "model"],
        "Lowest Latency":          summary_df.loc[summary_df["avg_latency_ms"].idxmin(), "model"],
        "Lowest RAM Usage":        summary_df.loc[summary_df["peak_ram_delta_mb"].idxmin(), "model"],
    }
    for criterion, model in criteria.items():
        lines.append("- **" + str(criterion) + "**: `" + str(model) + "`")
    lines.append("")

    # -- Accuracy by Language --
    lines.append("## 🌍 Top-1 Accuracy by Language\n")
    languages = sorted(set(col.split("_")[1] for col in summary_df.columns
                           if col.startswith("language_") and col.endswith("_top1")))
    if languages:
        lang_header = "| Model | " + " | ".join(languages) + " |"
        lang_sep    = "| --- | " + " | ".join(["---"] * len(languages)) + " |"
        lines.append(lang_header)
        lines.append(lang_sep)
        for _, row in ranked.iterrows():
            vals = [str(row.get("language_" + str(l) + "_top1", "N/A")) + "%" for l in languages]
            lines.append("| " + str(row['model']) + " | " + " | ".join(vals) + " |")
        lines.append("")

    # -- Accuracy by Query Type --
    lines.append("## 🔍 Top-1 Accuracy by Query Type\n")
    qtypes = sorted(set(
        "_".join(col.split("_")[1:-1])
        for col in summary_df.columns
        if col.startswith("query_type_") and col.endswith("_top1")
    ))
    if qtypes:
        qt_header = "| Model | " + " | ".join(qtypes) + " |"
        qt_sep    = "| --- | " + " | ".join(["---"] * len(qtypes)) + " |"
        lines.append(qt_header)
        lines.append(qt_sep)
        for _, row in ranked.iterrows():
            vals = [str(row.get("query_type_" + str(q) + "_top1", "N/A")) + "%" for q in qtypes]
            lines.append("| " + str(row['model']) + " | " + " | ".join(vals) + " |")
        lines.append("")

    # -- Accuracy by Difficulty --
    lines.append("## 🎯 Top-1 Accuracy by Difficulty\n")
    diffs = ["easy", "medium", "hard"]
    diff_header = "| Model | Easy | Medium | Hard |"
    diff_sep    = "| --- | --- | --- | --- |"
    lines.append(diff_header)
    lines.append(diff_sep)
    for _, row in ranked.iterrows():
        vals = [str(row.get("difficulty_" + str(d) + "_top1", "N/A")) + "%" for d in diffs]
        lines.append("| " + str(row['model']) + " | " + " | ".join(vals) + " |")
    lines.append("")

    # -- Recommendation --
    lines.append("## ✅ Recommendation\n")
    best_overall  = summary_df.loc[summary_df["top1_accuracy"].idxmax(), "model"]
    best_balanced = summary_df.loc[
        (summary_df["top1_accuracy"] / summary_df["avg_latency_ms"]).idxmax(), "model"
    ]
    multilingual_col = "language_Hindi_top1" if "language_Hindi_top1" in summary_df.columns else None
    best_multilang = (
        summary_df.loc[summary_df[multilingual_col].idxmax(), "model"]
        if multilingual_col else "N/A"
    )
    lines.append("| Use Case | Recommended Model |")
    lines.append("| --- | --- |")
    lines.append("| Best accuracy overall | `" + str(best_overall) + "` |")
    lines.append("| Best accuracy/speed balance | `" + str(best_balanced) + "` |")
    lines.append("| Best multilingual support | `" + str(best_multilang) + "` |")
    lines.append("\n> Update `MODEL_NAME` in `scripts/legacy_pipeline/02_generateEmbedding.py` to the recommended model.")

    return "\n".join(lines)


report_md   = generate_report(summary_df)
report_path = OUTPUT_DIR / "benchmark_report.md"
report_path.write_text(report_md, encoding="utf-8")
print("[ok] Report   -> " + str(report_path))

# -- CELL 9: Print Final Summary Table -----------------------------------------

print("\n" + "="*60)
print("BENCHMARK COMPLETE -- FINAL SUMMARY")
print("="*60)

display_cols = ["model", "top1_accuracy", "top3_accuracy", "top5_accuracy",
                "mrr", "avg_latency_ms", "total_time_sec"]

ranked = summary_df.sort_values("top1_accuracy", ascending=False)[display_cols]
print(ranked.to_string(index=False))

print("\nFull results saved to: " + str(OUTPUT_DIR))
print("Files:")
print("  " + summary_path.name)
print("  " + detailed_path.name)
print("  " + report_path.name)
