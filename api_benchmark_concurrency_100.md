# API Load & Performance Benchmark Report

Generated on: 2026-06-16 23:49:56

## Test Parameters
- **Target URL**: `http://127.0.0.1:5000/api/search`
- **Concurrency (Parallel Threads)**: `100`
- **Total Configured Requests**: `1000`
- **Total Completed Requests**: `1000`

## Performance Metrics

| Metric | Value | Description |
| :--- | :--- | :--- |
| **Total Test Duration** | `4.947 seconds` | Time taken to complete all requests |
| **Throughput** | `202.13 req/sec` | Number of successful requests processed per second |
| **Success Rate** | `100.00%` | Percentage of successful requests (Status 2xx) |
| **Average Latency** | `344.59 ms` | Average response time of successful requests |
| **Min Latency** | `52.00 ms` | Fastest successful request response time |
| **Max Latency** | `846.82 ms` | Slowest successful request response time |

### Latency Percentiles (Successful Requests)
- **P50 (Median)**: `334.42 ms`
- **P90**: `500.64 ms`
- **P95**: `553.65 ms`
- **P99**: `678.96 ms`

---

## Request Status Distribution

| Status Code | Count | Percentage |
| :---: | :---: | :---: |
| `200` (OK (Success)) | 1000 | 100.0% |

---
*Note: This benchmark was executed locally using python's ThreadPoolExecutor to simulate concurrent API clients.*
