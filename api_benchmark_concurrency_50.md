# API Load & Performance Benchmark Report

Generated on: 2026-06-16 23:49:40

## Test Parameters
- **Target URL**: `http://127.0.0.1:5000/api/search`
- **Concurrency (Parallel Threads)**: `50`
- **Total Configured Requests**: `500`
- **Total Completed Requests**: `500`

## Performance Metrics

| Metric | Value | Description |
| :--- | :--- | :--- |
| **Total Test Duration** | `2.613 seconds` | Time taken to complete all requests |
| **Throughput** | `191.35 req/sec` | Number of successful requests processed per second |
| **Success Rate** | `100.00%` | Percentage of successful requests (Status 2xx) |
| **Average Latency** | `220.90 ms` | Average response time of successful requests |
| **Min Latency** | `42.73 ms` | Fastest successful request response time |
| **Max Latency** | `412.53 ms` | Slowest successful request response time |

### Latency Percentiles (Successful Requests)
- **P50 (Median)**: `219.62 ms`
- **P90**: `304.32 ms`
- **P95**: `328.71 ms`
- **P99**: `372.13 ms`

---

## Request Status Distribution

| Status Code | Count | Percentage |
| :---: | :---: | :---: |
| `200` (OK (Success)) | 500 | 100.0% |

---
*Note: This benchmark was executed locally using python's ThreadPoolExecutor to simulate concurrent API clients.*
