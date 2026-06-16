import os
import sys
import time
import json
import random
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

# Set of realistic search queries to simulate actual user requests
SAMPLE_QUERIES = [
    'software developer',
    'medical doctor',
    'mechanical engineer',
    'primary school teacher',
    'office clerk',
    'data analyst',
    'civil engineer',
    'financial adviser',
    'graphic designer',
    'registered nurse',
    'database administrator',
    'marketing manager',
    'sales executive',
    'chef de cuisine',
    'electrician'
]

def run_single_request(url, query, top_k, search_mode, timeout):
    """Sends a single POST request to the API and measures latency."""
    data = {
        'query': query,
        'top_k': top_k,
        'search_mode': search_mode
    }
    
    start_time = time.perf_counter()
    status_code = -1
    error_msg = None
    
    try:
        response = requests.post(url, json=data, timeout=timeout)
        status_code = response.status_code
        # Read the body to ensure we download the entire response payload
        _ = response.text
    except requests.exceptions.Timeout:
        status_code = 408
        error_msg = "Timeout"
    except requests.exceptions.ConnectionError:
        status_code = 503
        error_msg = "Connection Refused"
    except Exception as e:
        status_code = 500
        error_msg = str(e)
        
    end_time = time.perf_counter()
    latency_ms = (end_time - start_time) * 1000
    
    return {
        'latency_ms': latency_ms,
        'status_code': status_code,
        'query': query,
        'error': error_msg
    }

def calculate_percentile(sorted_list, percentile):
    """Calculates percentile from a sorted list of numbers."""
    if not sorted_list:
        return 0.0
    index = (len(sorted_list) - 1) * (percentile / 100.0)
    lower = int(index)
    upper = lower + 1
    if upper < len(sorted_list):
        return sorted_list[lower] + (sorted_list[upper] - sorted_list[lower]) * (index - lower)
    return sorted_list[lower]

def generate_markdown_report(results, total_duration, concurrency, total_requests, url, filename="api_benchmark_report.md"):
    """Generates a detailed markdown report of the benchmark run."""
    successful_latencies = sorted([r['latency_ms'] for r in results if 200 <= r['status_code'] < 300])
    all_latencies = sorted([r['latency_ms'] for r in results])
    
    total_runs = len(results)
    success_runs = len(successful_latencies)
    failed_runs = total_runs - success_runs
    
    status_codes = {}
    for r in results:
        status_codes[r['status_code']] = status_codes.get(r['status_code'], 0) + 1
        
    error_types = {}
    for r in results:
        if r['error']:
            error_types[r['error']] = error_types.get(r['error'], 0) + 1

    # Latency Stats
    avg_latency = sum(successful_latencies) / success_runs if success_runs else 0.0
    min_latency = successful_latencies[0] if success_runs else 0.0
    max_latency = successful_latencies[-1] if success_runs else 0.0
    p50 = calculate_percentile(successful_latencies, 50)
    p90 = calculate_percentile(successful_latencies, 90)
    p95 = calculate_percentile(successful_latencies, 95)
    p99 = calculate_percentile(successful_latencies, 99)
    
    # Throughput
    throughput = success_runs / total_duration if total_duration > 0 else 0.0
    
    report_content = f"""# API Load & Performance Benchmark Report

Generated on: {time.strftime('%Y-%m-%d %H:%M:%S')}

## Test Parameters
- **Target URL**: `{url}`
- **Concurrency (Parallel Threads)**: `{concurrency}`
- **Total Configured Requests**: `{total_requests}`
- **Total Completed Requests**: `{total_runs}`

## Performance Metrics

| Metric | Value | Description |
| :--- | :--- | :--- |
| **Total Test Duration** | `{total_duration:.3f} seconds` | Time taken to complete all requests |
| **Throughput** | `{throughput:.2f} req/sec` | Number of successful requests processed per second |
| **Success Rate** | `{(success_runs / total_runs * 100):.2f}%` | Percentage of successful requests (Status 2xx) |
| **Average Latency** | `{avg_latency:.2f} ms` | Average response time of successful requests |
| **Min Latency** | `{min_latency:.2f} ms` | Fastest successful request response time |
| **Max Latency** | `{max_latency:.2f} ms` | Slowest successful request response time |

### Latency Percentiles (Successful Requests)
- **P50 (Median)**: `{p50:.2f} ms`
- **P90**: `{p90:.2f} ms`
- **P95**: `{p95:.2f} ms`
- **P99**: `{p99:.2f} ms`

---

## Request Status Distribution

| Status Code | Count | Percentage |
| :---: | :---: | :---: |
"""
    for code, count in sorted(status_codes.items()):
        status_text = "OK (Success)" if 200 <= code < 300 else "Error"
        report_content += f"| `{code}` ({status_text}) | {count} | {(count/total_runs*100):.1f}% |\n"
        
    if error_types:
        report_content += "\n## Error Analysis\n\n| Error Details | Count | Percentage |\n| :--- | :---: | :---: |\n"
        for err, count in sorted(error_types.items()):
            report_content += f"| `{err}` | {count} | {(count/total_runs*100):.1f}% |\n"

    report_content += """
---
*Note: This benchmark was executed locally using python's ThreadPoolExecutor to simulate concurrent API clients.*
"""

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(report_content)
    return filename

def main():
    parser = argparse.ArgumentParser(description="API Latency, Throughput and Concurrency Benchmarking Tool")
    parser.add_argument('--url', type=str, default='http://localhost:5000/api/search', help='API endpoint URL')
    parser.add_argument('--requests', type=int, default=100, help='Total number of requests to execute')
    parser.add_argument('--concurrency', type=int, default=10, help='Number of concurrent threads')
    parser.add_argument('--top-k', type=int, default=5, help='top_k parameter value in search')
    parser.add_argument('--mode', type=str, default='general', choices=['general', 'nco'], help='Search mode')
    parser.add_argument('--timeout', type=float, default=10.0, help='Request timeout in seconds')
    parser.add_argument('--output-report', type=str, default='api_benchmark_report.md', help='Output Markdown report path')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("      API LOAD & PERFORMANCE BENCHMARKING TOOL")
    print("=" * 60)
    print(f"Target URL:     {args.url}")
    print(f"Total Requests: {args.requests}")
    print(f"Concurrency:    {args.concurrency} worker threads")
    print(f"Parameters:     top_k={args.top_k}, search_mode={args.mode}")
    print(f"Timeout:        {args.timeout}s")
    print("=" * 60)
    print("\nWarm-up: Checking connectivity to the target URL...")
    
    # Check if target is reachable first
    try:
        warmup_resp = requests.post(args.url, json={
            'query': 'warmup',
            'top_k': 1,
            'search_mode': args.mode
        }, timeout=3.0)
        print(f"[OK] Target is online. Status Code: {warmup_resp.status_code}")
    except Exception as e:
        print(f"[WARNING] Could not connect to target URL: {e}")
        print("Ensure your API server is running before executing the benchmark.")
        print("Continuing benchmark run anyway...\n")
        
    print(f"Starting load test with {args.concurrency} parallel connections...")
    
    results = []
    start_test_time = time.perf_counter()
    
    # Thread pool execution
    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = []
        for i in range(args.requests):
            query = random.choice(SAMPLE_QUERIES)
            futures.append(
                executor.submit(
                    run_single_request,
                    args.url,
                    query,
                    args.top_k,
                    args.mode,
                    args.timeout
                )
            )
            
        # Monitor progress
        completed = 0
        for future in as_completed(futures):
            res = future.result()
            results.append(res)
            completed += 1
            if completed % max(1, args.requests // 10) == 0 or completed == args.requests:
                percentage = (completed / args.requests) * 100
                print(f"Progress: {completed}/{args.requests} requests completed ({percentage:.0f}%)")
                
    end_test_time = time.perf_counter()
    total_duration = end_test_time - start_test_time
    
    # Calculations
    successful_latencies = sorted([r['latency_ms'] for r in results if 200 <= r['status_code'] < 300])
    all_latencies = sorted([r['latency_ms'] for r in results])
    
    total_runs = len(results)
    success_runs = len(successful_latencies)
    failed_runs = total_runs - success_runs
    
    status_codes = {}
    for r in results:
        status_codes[r['status_code']] = status_codes.get(r['status_code'], 0) + 1
        
    avg_latency = sum(successful_latencies) / success_runs if success_runs else 0.0
    min_latency = successful_latencies[0] if success_runs else 0.0
    max_latency = successful_latencies[-1] if success_runs else 0.0
    p50 = calculate_percentile(successful_latencies, 50)
    p90 = calculate_percentile(successful_latencies, 90)
    p95 = calculate_percentile(successful_latencies, 95)
    p99 = calculate_percentile(successful_latencies, 99)
    throughput = success_runs / total_duration if total_duration > 0 else 0.0
    
    # Console output
    print("\n" + "=" * 60)
    print("                     BENCHMARK RESULTS")
    print("=" * 60)
    print(f"Total Test Duration:       {total_duration:.3f} seconds")
    print(f"Successful Requests:       {success_runs} / {total_runs} ({(success_runs/total_runs*100):.2f}%)")
    print(f"Failed / Errored Requests: {failed_runs} / {total_runs} ({(failed_runs/total_runs*100):.2f}%)")
    print(f"Throughput (TPS / RPS):    {throughput:.2f} successful req/sec")
    print("-" * 60)
    print("Latency Stats (Successful Requests only):")
    print(f"  Average Latency:         {avg_latency:.2f} ms")
    print(f"  Min / Max Latency:       {min_latency:.2f} ms / {max_latency:.2f} ms")
    print(f"  P50 (Median) Latency:    {p50:.2f} ms")
    print(f"  P90 Latency:             {p90:.2f} ms")
    print(f"  P95 Latency:             {p95:.2f} ms")
    print(f"  P99 Latency:             {p99:.2f} ms")
    print("-" * 60)
    print("Status Code Distribution:")
    for code, count in sorted(status_codes.items()):
        print(f"  Status {code}:             {count} requests ({(count/total_runs*100):.1f}%)")
    print("=" * 60)
    
    # Generate Markdown Report
    report_file = generate_markdown_report(results, total_duration, args.concurrency, args.requests, args.url, args.output_report)
    print(f"\n[OK] Detailed Markdown report generated: {os.path.abspath(report_file)}")
    print("=" * 60)

if __name__ == '__main__':
    main()
