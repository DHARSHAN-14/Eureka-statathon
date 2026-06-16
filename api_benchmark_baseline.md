# API Load & Performance Benchmark Report

Generated on: 2026-06-16 23:40:11

## Test Parameters
- **Target URL**: `http://127.0.0.1:5000/api/search`
- **Concurrency (Parallel Threads)**: `2`
- **Total Configured Requests**: `10`
- **Total Completed Requests**: `10`

## Performance Metrics

| Metric | Value | Description |
| :--- | :--- | :--- |
| **Total Test Duration** | `0.667 seconds` | Time taken to complete all requests |
| **Throughput** | `14.99 req/sec` | Number of successful requests processed per second |
| **Success Rate** | `100.00%` | Percentage of successful requests (Status 2xx) |
| **Average Latency** | `127.98 ms` | Average response time of successful requests |
| **Min Latency** | `87.83 ms` | Fastest successful request response time |
| **Max Latency** | `166.62 ms` | Slowest successful request response time |

### Latency Percentiles (Successful Requests)
- **P50 (Median)**: `130.28 ms`
- **P90**: `151.13 ms`
- **P95**: `158.88 ms`
- **P99**: `165.07 ms`

---

## Request Status Distribution

| Status Code | Count | Percentage |
| :---: | :---: | :---: |
| `200` (OK (Success)) | 10 | 100.0% |

---
*Note: This benchmark was executed locally using python's ThreadPoolExecutor to simulate concurrent API clients.*
