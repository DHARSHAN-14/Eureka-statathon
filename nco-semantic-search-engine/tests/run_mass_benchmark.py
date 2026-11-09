import os
import sys
import re
import json
import time
import random
from concurrent.futures import ThreadPoolExecutor

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv()

from database import db_store
import utils.searchapp as search_module

# Set a fixed random seed for reproducibility
random.seed(42)

def introduce_typos(word, num_typos=2):
    """Introduce 1-3 letter spelling errors (substitution, deletion, insertion, swap)."""
    if len(word) <= 3:
        return word
    word_chars = list(word)
    for _ in range(min(num_typos, len(word_chars) - 1)):
        op = random.choice(["sub", "del", "ins", "swap"])
        idx = random.randint(0, len(word_chars) - 1)
        if op == "sub":
            word_chars[idx] = random.choice("abcdefghijklmnopqrstuvwxyz")
        elif op == "del" and len(word_chars) > 3:
            del word_chars[idx]
        elif op == "ins":
            word_chars.insert(idx, random.choice("abcdefghijklmnopqrstuvwxyz"))
        elif op == "swap" and idx < len(word_chars) - 1:
            word_chars[idx], word_chars[idx+1] = word_chars[idx+1], word_chars[idx]
    return "".join(word_chars)

def generate_queries(row):
    """Generate 3 distinct vague, misspelled query formats for an occupation."""
    title = row.get("occupation_title") or row.get("Occupational Title")
    nco = row.get("nco_2015") or row.get("NCO 2015")
    row_id = row.get("id") or row.get("_row_id")
    
    # Strip special chars
    title_clean = re.sub(r"[^a-zA-Z\s]", "", title).strip()
    words = [w for w in title_clean.split() if len(w) > 3]
    if not words:
        words = title_clean.split()
        
    queries = []
    fillers = [
        "i am a",
        "i work as",
        "my job is",
        "i do"
    ]
    
    # Query 1: Vague sentence with full title misspelled
    corrupted_title = " ".join([introduce_typos(w, random.randint(1, 2)) for w in title_clean.split()])
    queries.append(f"{random.choice(fillers)} {corrupted_title}")
    
    # Query 2: Misspelled single keyword
    if words:
        kw = random.choice(words)
        queries.append(f"i do {introduce_typos(kw, random.randint(2, 3))}")
    else:
        queries.append(f"i work as {introduce_typos(title_clean, 2)}")
        
    # Query 3: Misspelled keyword pair or fallback
    if len(words) >= 2:
        kw_pair = random.sample(words, 2)
        corr_pair = " ".join([introduce_typos(w, random.randint(1, 2)) for w in kw_pair])
        queries.append(f"help with {corr_pair}")
    else:
        queries.append(f"i am {introduce_typos(title_clean, 3)}")
        
    return [
        {"query": q, "target_nco": nco, "target_title": title, "row_id": row_id} 
        for q in queries
    ]

def evaluate_query(task):
    """Run spellcheck + search and check if target occupation is retrieved in top 5."""
    query = task["query"]
    target_nco = task["target_nco"]
    target_title = task["target_title"]
    row_id = task["row_id"]
    
    # 1. Word-level spellcheck
    suggestions = db_store.get_spelling_suggestions(query, limit=1)
    corrected = suggestions[0] if suggestions else query
    
    # 2. Search
    start_t = time.perf_counter()
    results = search_module.search(corrected, top_k=5)
    latency = (time.perf_counter() - start_t) * 1000
    
    # 3. Check rank of target NCO code
    rank = -1
    for idx, r in enumerate(results, start=1):
        if r.get("nco_code") == target_nco or r.get("row_id") == row_id:
            rank = idx
            break
            
    passed = (rank != -1) # Passes if target is retrieved in top 5
    
    return {
        "query": query,
        "corrected_query": corrected,
        "target_title": target_title,
        "target_nco": target_nco,
        "passed": passed,
        "rank": rank,
        "latency_ms": latency,
        "top_results": [{"title": r["occupation_title"], "nco": r["nco_code"], "score": r["final_score"]} for r in results[:3]]
    }

def main():
    print("Initializing Database & Loading Occupations...")
    db_store.init_db()
    _, rows = db_store.load_csv_rows()
    
    print(f"Loaded {len(rows)} occupations.")
    
    # Generate all test cases
    test_tasks = []
    for row in rows:
        test_tasks.extend(generate_queries(row))
        
    total_queries = len(test_tasks)
    print(f"Generated {total_queries} vagued/misspelled test cases.")
    
    # Execute searches in parallel using ThreadPoolExecutor
    print("Running searches in parallel (this will take 2-4 minutes)...")
    results = []
    start_time = time.time()
    
    from concurrent.futures import as_completed
    # Using 8 threads to speed up PyTorch embedding runs
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(evaluate_query, task): task for task in test_tasks}
        for idx, future in enumerate(as_completed(futures), start=1):
            results.append(future.result())
            if idx % 10 == 0 or idx == total_queries:
                print(f"  Processed {idx}/{total_queries} queries...", flush=True)
        
    total_time = time.time() - start_time
    
    # Calculate statistics
    passed_count = sum(1 for r in results if r["passed"])
    pass_rate = (passed_count / total_queries) * 100
    avg_latency = sum(r["latency_ms"] for r in results) / total_queries
    
    print("\n" + "=" * 80)
    print("BENCHMARK COMPLETE REPORT")
    print("=" * 80)
    print(f"Total Test Queries Run:  {total_queries}")
    print(f"Passed (Top 5 Retrieval): {passed_count}")
    print(f"Pass Rate (%):           {pass_rate:.2f}%")
    print(f"Average Search Latency:   {avg_latency:.1f} ms")
    print(f"Total Execution Time:    {total_time:.1f} seconds")
    print("=" * 80)
    
    # Group failures to understand what types of queries fail
    failures = [r for r in results if not r["passed"]]
    
    # Write full detailed report to JSON
    report_path = os.path.join(PROJECT_ROOT, "tests", "results", "mass_benchmark_results.json")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_queries": total_queries,
            "passed": passed_count,
            "pass_rate": pass_rate,
            "average_latency_ms": avg_latency,
            "total_time_seconds": total_time,
            "failures_count": len(failures),
            "results": results
        }, f, indent=2, ensure_ascii=False)
    print(f"Saved full benchmark log to: {report_path}")
    
    # Print a sample of failures to show where it fails
    if failures:
        print("\nSample of Failed Queries (First 15):")
        print("-" * 80)
        for f in failures[:15]:
            print(f"Query:        '{f['query']}'")
            print(f"Corrected:    '{f['corrected_query']}'")
            print(f"Target Title: '{f['target_title']}' ({f['target_nco']})")
            print("Top Retrieved:")
            for idx, r in enumerate(f["top_results"], start=1):
                print(f"   {idx}. {r['title']} (NCO: {r['nco']}, score: {r['score']:.3f})")
            print("-" * 80)

if __name__ == "__main__":
    main()
