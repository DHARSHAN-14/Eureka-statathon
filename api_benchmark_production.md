# API Load & Performance Benchmark Report

Generated on: 2026-06-16 23:40:18

## Test Parameters
- **Target URL**: `http://127.0.0.1:5000/api/search`
- **Concurrency (Parallel Threads)**: `10`
- **Total Configured Requests**: `100`
- **Total Completed Requests**: `100`

## Performance Metrics

| Metric | Value | Description |
| :--- | :--- | :--- |
| **Total Test Duration** | `1.398 seconds` | Time taken to complete all requests |
| **Throughput** | `71.52 req/sec` | Number of successful requests processed per second |
| **Success Rate** | `100.00%` | Percentage of successful requests (Status 2xx) |
| **Average Latency** | `131.30 ms` | Average response time of successful requests |
| **Min Latency** | `67.19 ms` | Fastest successful request response time |
| **Max Latency** | `195.59 ms` | Slowest successful request response time |

### Latency Percentiles (Successful Requests)
- **P50 (Median)**: `128.62 ms`
- **P90**: `174.44 ms`
- **P95**: `179.85 ms`
- **P99**: `187.06 ms`

---

## Request Status Distribution

| Status Code | Count | Percentage |
| :---: | :---: | :---: |
| `200` (OK (Success)) | 100 | 100.0% |

---
*Note: This benchmark was executed locally using python's ThreadPoolExecutor to simulate concurrent API clients.*
