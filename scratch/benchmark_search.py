"""
Benchmark script for the optimized NCO Search System.
Tests all key performance areas against the live Flask server at http://127.0.0.1:5000.

Usage:
    python scratch/benchmark_search.py
"""

import requests
import time
import json
import statistics

BASE_URL = "http://127.0.0.1:5000"

# ── Helpers ──────────────────────────────────────────────────────────────────

def timed_request(method, url, **kwargs):
    """Make a request and return (response, elapsed_ms)."""
    start = time.perf_counter()
    resp = method(url, **kwargs)
    elapsed = (time.perf_counter() - start) * 1000
    return resp, elapsed


def run_bench(label, fn, iterations=5):
    """Run a benchmark function multiple times and print stats."""
    times = []
    last_resp = None
    for i in range(iterations):
        resp, ms = fn()
        times.append(ms)
        last_resp = resp
    avg = statistics.mean(times)
    med = statistics.median(times)
    mn = min(times)
    mx = max(times)
    print(f"  {'Avg':>5}: {avg:>8.2f}ms | {'Med':>5}: {med:>8.2f}ms | "
          f"{'Min':>5}: {mn:>8.2f}ms | {'Max':>5}: {mx:>8.2f}ms  "
          f"({iterations} runs)")
    return times, last_resp


# ── Benchmarks ───────────────────────────────────────────────────────────────

def bench_search(query, label=None, top_k=5):
    """Benchmark a search query."""
    label = label or f"Search: '{query}'"
    print(f"\n🔎 {label}")

    def fn():
        return timed_request(
            requests.post,
            f"{BASE_URL}/api/search",
            json={"query": query, "top_k": top_k}
        )

    times, resp = run_bench(label, fn, iterations=5)
    data = resp.json()
    count = data.get("returned_count", len(data.get("results", [])))
    top_title = ""
    top_score = 0
    if data.get("results"):
        top_title = data["results"][0].get("occupation_title", "")
        top_score = data["results"][0].get("final_score", 0)
    print(f"  Results: {count} | Top: \"{top_title}\" (score: {top_score:.4f})")
    return times


def bench_empty_query_paginated():
    """Benchmark paginated empty query (should be fast and small)."""
    print(f"\n📄 Empty Query (Paginated, page=1, per_page=50)")

    def fn():
        return timed_request(
            requests.post,
            f"{BASE_URL}/api/search",
            json={"query": "", "page": 1, "per_page": 50}
        )

    times, resp = run_bench("Empty Paginated", fn, iterations=5)
    data = resp.json()
    returned = data.get("returned_count", 0)
    total = data.get("total_count", "?")
    payload_kb = len(resp.content) / 1024
    print(f"  Returned: {returned}/{total} | Payload: {payload_kb:.1f} KB")
    return times


def bench_translation_cache():
    """Benchmark translation caching — first call vs cached call."""
    print(f"\n🌐 Translation Cache Test (Hindi → English)")

    hindi_query = "किसान"  # farmer

    # First call (cache miss)
    resp1, ms1 = timed_request(
        requests.post,
        f"{BASE_URL}/api/search",
        json={"query": hindi_query, "user_language": "hi", "top_k": 3}
    )
    print(f"  1st call (cache miss): {ms1:>8.2f}ms")

    # Second call (cache hit)
    resp2, ms2 = timed_request(
        requests.post,
        f"{BASE_URL}/api/search",
        json={"query": hindi_query, "user_language": "hi", "top_k": 3}
    )
    print(f"  2nd call (cache hit):  {ms2:>8.2f}ms")

    if ms1 > 0:
        speedup = ms1 / ms2 if ms2 > 0 else float('inf')
        print(f"  Speedup: {speedup:.1f}x faster on cache hit")
    return [ms1, ms2]


def bench_analytics():
    """Benchmark all analytics endpoints (now SQL-based)."""
    print(f"\n📊 Analytics Endpoints (SQL Aggregation)")

    endpoints = [
        "/admin/api/analytics/divisions",
        "/admin/api/analytics/confidence",
        "/admin/api/analytics/top-occupations",
        "/admin/api/analytics/search-trend",
        "/admin/api/analytics/languages",
        "/admin/api/analytics/low-confidence",
    ]

    total_ms = 0
    for ep in endpoints:
        resp, ms = timed_request(requests.get, f"{BASE_URL}{ep}")
        status = "✅" if resp.status_code == 200 else "❌"
        print(f"  {status} {ep:<45} {ms:>8.2f}ms")
        total_ms += ms

    print(f"  {'Total':>47}: {total_ms:>8.2f}ms")
    return total_ms


def bench_nco_code_search():
    """Benchmark direct NCO code lookup."""
    print(f"\n🔢 NCO Code Direct Search (mode=nco)")

    def fn():
        return timed_request(
            requests.post,
            f"{BASE_URL}/api/search",
            json={"query": "2512.0201", "search_mode": "nco", "top_k": 5}
        )

    times, resp = run_bench("NCO Code Lookup", fn, iterations=5)
    data = resp.json()
    if data.get("results"):
        print(f"  Found: \"{data['results'][0].get('occupation_title', '')}\"")
    return times


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("  NCO Search System — Performance Benchmark")
    print("=" * 70)
    print(f"  Server: {BASE_URL}")
    print(f"  Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Warmup request
    print("\n⏳ Warmup request...")
    requests.post(f"{BASE_URL}/api/search", json={"query": "test", "top_k": 1})
    print("  Done.")

    all_results = {}

    # 1. TF-IDF Fast-path queries (exact/close title matches)
    print("\n" + "─" * 70)
    print("  SECTION 1: TF-IDF Fast-Path (exact title matches, skips SBERT)")
    print("─" * 70)
    all_results["fast_path_1"] = bench_search("Software Engineer", "Fast-path: 'Software Engineer'")
    all_results["fast_path_2"] = bench_search("Paddy Farmer", "Fast-path: 'Paddy Farmer'")
    all_results["fast_path_3"] = bench_search("Physician General", "Fast-path: 'Physician General'")

    # 2. SBERT standard path queries (vague/descriptive)
    print("\n" + "─" * 70)
    print("  SECTION 2: SBERT Standard Path (vague/descriptive queries)")
    print("─" * 70)
    all_results["sbert_1"] = bench_search("person who builds houses and structures", "SBERT: 'person who builds houses'")
    all_results["sbert_2"] = bench_search("someone working with crops in fields", "SBERT: 'crops in fields'")
    all_results["sbert_3"] = bench_search("I teach children mathematics", "SBERT: 'I teach children math'")

    # 3. Empty query pagination
    print("\n" + "─" * 70)
    print("  SECTION 3: Empty Query Pagination")
    print("─" * 70)
    all_results["pagination"] = bench_empty_query_paginated()

    # 4. NCO code direct lookup
    print("\n" + "─" * 70)
    print("  SECTION 4: NCO Code Direct Lookup")
    print("─" * 70)
    all_results["nco_code"] = bench_nco_code_search()

    # 5. Translation caching
    print("\n" + "─" * 70)
    print("  SECTION 5: Translation Cache")
    print("─" * 70)
    all_results["translation"] = bench_translation_cache()

    # 6. Analytics endpoints
    print("\n" + "─" * 70)
    print("  SECTION 6: Admin Analytics (SQL Aggregation)")
    print("─" * 70)
    all_results["analytics"] = bench_analytics()

    # Summary
    print("\n" + "=" * 70)
    print("  BENCHMARK SUMMARY")
    print("=" * 70)

    fast_avg = statistics.mean(
        [statistics.mean(all_results[k]) for k in ["fast_path_1", "fast_path_2", "fast_path_3"]]
    )
    sbert_avg = statistics.mean(
        [statistics.mean(all_results[k]) for k in ["sbert_1", "sbert_2", "sbert_3"]]
    )
    page_avg = statistics.mean(all_results["pagination"])
    nco_avg = statistics.mean(all_results["nco_code"])

    print(f"  TF-IDF Fast-path avg:    {fast_avg:>8.2f}ms")
    print(f"  SBERT Standard avg:      {sbert_avg:>8.2f}ms")
    print(f"  Paginated empty query:   {page_avg:>8.2f}ms")
    print(f"  NCO code lookup:         {nco_avg:>8.2f}ms")
    print(f"  Translation (1st/2nd):   {all_results['translation'][0]:.0f}ms / {all_results['translation'][1]:.0f}ms")
    print(f"  Analytics total:         {all_results['analytics']:.2f}ms")
    print("=" * 70)


if __name__ == "__main__":
    main()
