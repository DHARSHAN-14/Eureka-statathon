# API Load & Performance Benchmark Report

Generated on: 2026-06-16 23:40:27

## Test Parameters
- **Target URL**: `http://127.0.0.1:5000/api/search`
- **Concurrency (Parallel Threads)**: `25`
- **Total Configured Requests**: `500`
- **Total Completed Requests**: `500`

## Performance Metrics

| Metric | Value | Description |
| :--- | :--- | :--- |
| **Total Test Duration** | `3.718 seconds` | Time taken to complete all requests |
| **Throughput** | `134.49 req/sec` | Number of successful requests processed per second |
| **Success Rate** | `100.00%` | Percentage of successful requests (Status 2xx) |
| **Average Latency** | `178.84 ms` | Average response time of successful requests |
| **Min Latency** | `84.94 ms` | Fastest successful request response time |
| **Max Latency** | `307.31 ms` | Slowest successful request response time |

### Latency Percentiles (Successful Requests)
- **P50 (Median)**: `176.63 ms`
- **P90**: `234.52 ms`
- **P95**: `249.54 ms`
- **P99**: `273.49 ms`

---

## Request Status Distribution

| Status Code | Count | Percentage |
| :---: | :---: | :---: |
| `200` (OK (Success)) | 500 | 100.0% |

---
*Note: This benchmark was executed locally using python's ThreadPoolExecutor to simulate concurrent API clients.*
