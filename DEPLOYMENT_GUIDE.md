# NCO Intelligence Engine - Production Deployment Guide

## Quick Start

### 1. Installation

```bash
# Clone/Navigate to project
cd /home/dharshan/Documents/Eureka-statathon-Kabhilan

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements_production.txt
```

### 2. Start API Server

```bash
# Development
uvicorn src.app.api:app --reload --host 0.0.0.0 --port 8000

# Production
gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 src.app.api:app
```

### 3. Test API

```bash
# Health check
curl http://localhost:8000/health

# Simple search
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "software engineer", "top_k": 5}'

# View API docs
# Open: http://localhost:8000/docs
```

---

## Deployment Checklist

### Pre-Deployment

- [ ] All data files prepared (CSV, embeddings, FAISS index)
- [ ] Models downloaded (SBERT, CrossEncoder)
- [ ] Environment variables configured
- [ ] SSL certificates obtained (for production)
- [ ] Database backups created

### Staging

- [ ] Load testing completed
- [ ] Security audit done
- [ ] Performance benchmarks recorded
- [ ] Error handling tested
- [ ] Logging verified

### Production

- [ ] Blue-green deployment setup
- [ ] Monitoring enabled
- [ ] Alerts configured
- [ ] Rollback plan documented
- [ ] Team trained

---

## Docker Deployment

### Build Docker Image

```dockerfile
# Dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements_production.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements_production.txt

# Copy application
COPY . .

# Create logs directory
RUN mkdir -p logs

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run application
CMD ["uvicorn", "src.app.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose

```yaml
version: '3.8'

services:
  nco-engine:
    build: .
    container_name: nco-intelligence-engine
    ports:
      - "8000:8000"
    environment:
      - LOG_LEVEL=INFO
      - ENABLE_CORS=true
      - FEATURE_ENABLE_RERANKER=true
    volumes:
      - ./data:/app/data
      - ./models:/app/models
      - ./logs:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  nginx:
    image: nginx:latest
    container_name: nco-reverse-proxy
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - nco-engine
    restart: unless-stopped
```

### Build and Run

```bash
# Build image
docker build -t nco-engine:1.0 .

# Run container
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/models:/app/models \
  -v $(pwd)/logs:/app/logs \
  --name nco-engine \
  nco-engine:1.0

# View logs
docker logs -f nco-engine

# Stop container
docker stop nco-engine
docker rm nco-engine
```

---

## Nginx Reverse Proxy Configuration

```nginx
# nginx.conf
upstream nco_backend {
    server nco-engine:8000;
}

server {
    listen 80;
    server_name _;
    client_max_body_size 10M;

    # Redirect to HTTPS
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # CORS headers
    add_header 'Access-Control-Allow-Origin' '*' always;
    add_header 'Access-Control-Allow-Methods' 'GET,POST,PUT,DELETE,OPTIONS' always;

    # Security headers
    add_header 'X-Content-Type-Options' 'nosniff' always;
    add_header 'X-Frame-Options' 'DENY' always;
    add_header 'X-XSS-Protection' '1; mode=block' always;

    # API routes
    location / {
        proxy_pass http://nco_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Documentation
    location /docs {
        proxy_pass http://nco_backend/docs;
    }

    location /redoc {
        proxy_pass http://nco_backend/redoc;
    }
}
```

---

## Environment Variables

```bash
# .env file
LOG_LEVEL=INFO
API_HOST=0.0.0.0
API_PORT=8000
ENABLE_CORS=true

# Search parameters
DEFAULT_SEARCH_MODE=hybrid_optimized
FEATURE_ENABLE_RERANKER=true
FEATURE_ENABLE_GRAPH_HIERARCHY=true

# Performance
ENABLE_QUERY_CACHING=true
CACHE_MAX_SIZE=1000

# Monitoring
ENABLE_QUERY_LOGGING=true
ENABLE_PERFORMANCE_METRICS=true
```

---

## Performance Tuning

### CPU Optimization

```bash
# Increase worker processes (production)
# For 4-core system: 4-8 workers
gunicorn -w 8 -k uvicorn.workers.UvicornWorker src.app.api:app

# Use multiple processes
export PYTHONOPTIMIZE=2  # Remove assert statements
```

### Memory Optimization

```bash
# Monitor memory usage
free -h

# Limit model caching
# In config.py:
CACHE_MAX_SIZE = 500  # Reduce from 1000
```

### Query Caching

```python
# In config.py
ENABLE_QUERY_CACHING = True
CACHE_TTL_SECONDS = 3600  # 1 hour
CACHE_MAX_SIZE = 1000

# Queries like "software engineer" cached automatically
```

---

## Monitoring & Alerting

### Prometheus Metrics

```python
# Add to requirements:
prometheus-client

# Example: Track search times
from prometheus_client import Histogram

search_time = Histogram(
    'nco_search_duration_seconds',
    'Search execution time',
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0]
)

with search_time.time():
    results = search_engine.search(query)
```

### Logging Review

```bash
# Watch logs in real-time
tail -f logs/search_engine.log

# Search specific patterns
grep "ERROR" logs/search_engine.log | tail -20

# Count by log level
grep "INFO" logs/search_engine.log | wc -l
grep "ERROR" logs/search_engine.log | wc -l

# Find slow queries
grep "time=" logs/search_engine.log | sort -t= -k3 -nr | head -10
```

### Health Checks

```bash
# Continuous health monitoring
watch -n 30 'curl -s http://localhost:8000/health | jq'

# Automated alerting
while true; do
  status=$(curl -s http://localhost:8000/health)
  if [[ $status != *"healthy"* ]]; then
    # Send alert
    echo "Service down at $(date)" | mail -s "Alert" admin@example.com
  fi
  sleep 60
done
```

---

## Scaling Strategies

### Horizontal Scaling (Multiple Instances)

```yaml
# docker-compose.yml with load balancing
services:
  nco-engine-1:
    image: nco-engine:1.0
    environment:
      - INSTANCE_ID=1

  nco-engine-2:
    image: nco-engine:1.0
    environment:
      - INSTANCE_ID=2

  nco-engine-3:
    image: nco-engine:1.0
    environment:
      - INSTANCE_ID=3

  nginx:
    # Load balances across 3 instances
```

### Caching with Redis

```python
# In config.py
ENABLE_QUERY_CACHING = True

# In search engine
import redis
redis_client = redis.Redis(host='localhost', port=6379, db=0)

cache_key = f"search:{query}:{mode}"
if cache_key in redis_client:
    return redis_client.get(cache_key)
```

### Database Indexing

```python
# Future: Cache results in PostgreSQL
from sqlalchemy import create_engine

engine = create_engine('postgresql://user:pass@localhost/nco_search')

# Cache search results
class SearchResult(Base):
    __tablename__ = 'search_results'
    query = Column(String)
    results = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
```

---

## Troubleshooting

### Issue: API Won't Start

```bash
# Check port in use
lsof -i :8000

# Kill process on port
kill -9 <PID>

# Start with different port
uvicorn src.app.api:app --port 8001
```

### Issue: Slow Queries

```bash
# Check model loading time
# Add to logger:
import time
start = time.time()
engine = AdvancedHybridSearch()
print(f"Initialization: {time.time() - start}s")

# Check FAISS index loading
# Measure embedding computation
# Profile hot functions
python -m cProfile -s cumulative src/app/api:app
```

### Issue: Memory Leak

```bash
# Monitor memory over time
watch -n 5 'ps aux | grep uvicorn'

# Use memory profiler
pip install memory-profiler
python -m memory_profiler src/app/api.py

# Limit model caching
CACHE_MAX_SIZE = 100
```

### Issue: High Latency

```bash
# Check query cache hit rate
grep "Cache hit" logs/search_engine.log | wc -l

# Enable query batch processing
curl -X POST http://localhost:8000/search/batch \
  -H "Content-Type: application/json" \
  -d '{"queries": ["software", "engineer", "teacher"]}'

# Use reranker selectively
# Only enable for important queries
```

---

## Backup & Recovery

### Data Backup

```bash
# Backup all data
tar -czf nco-backup-$(date +%Y%m%d).tar.gz \
  data/ models/ logs/

# Restore from backup
tar -xzf nco-backup-20260613.tar.gz
```

### Model Backup

```bash
# Backup models
cp models/nco_embeddings.npy models/nco_embeddings.npy.backup
cp models/nco_faiss.index models/nco_faiss.index.backup

# Quick restore
cp models/nco_embeddings.npy.backup models/nco_embeddings.npy
```

---

## Security

### API Security

```python
# In config.py
ENABLE_CORS = False  # Restrict CORS in production

# Add authentication
from fastapi.security import HTTPBearer
security = HTTPBearer()

@app.post("/search")
async def search(request: SearchRequest, credentials = Depends(security)):
    # Verify token
    ...
```

### Rate Limiting

```bash
# nginx rate limiting
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=100r/m;

location /search {
    limit_req zone=api_limit burst=20;
    proxy_pass http://nco_backend;
}
```

### HTTPS Only

```bash
# Force HTTPS in nginx
server {
    listen 80;
    return 301 https://$host$request_uri;
}
```

---

## Performance Benchmarks

### Baseline (HYBRID_OPTIMIZED)

```
Query: "Software Engineer"
Execution Time: 125ms
Memory: 340MB
Results: 10
Top Score: 0.920
```

### With Reranking

```
Query: "Software Engineer"
Execution Time: 320ms (+195ms)
Memory: 380MB
Results: 10
Top Score: 0.945 (+2.5%)
```

### Batch Processing

```
Queries: 20 occupations
Sequential: 2500ms
Batch: 1500ms (40% faster)
```

---

## Maintenance Tasks

### Daily

- [ ] Check application logs for errors
- [ ] Monitor system resources (CPU, memory, disk)
- [ ] Verify backups completed successfully

### Weekly

- [ ] Review performance metrics
- [ ] Clean old log files (keep last 30 days)
- [ ] Update dependencies if needed
- [ ] Test backup restoration

### Monthly

- [ ] Analyze search patterns and user behavior
- [ ] Optimize search parameters if needed
- [ ] Review security logs
- [ ] Update documentation

---

## Support & Escalation

### Common Issues

1. **API unresponsive** → Check logs, restart service
2. **Slow queries** → Check cache, check FAISS index
3. **High memory** → Reduce cache size, restart
4. **Reranker errors** → Verify model download, fallback

### Escalation Path

1. Application logs → `logs/search_engine.log`
2. System logs → `dmesg`, `journalctl`
3. Performance profile → `cProfile`, `memory_profiler`
4. Database query analysis → Query logs

---

## Resources

- API Docs: http://localhost:8000/docs
- Architecture: [ARCHITECTURE_MASTER_LEVEL.md](ARCHITECTURE_MASTER_LEVEL.md)
- Comparison: [COMPARISON_SUMMARY.md](COMPARISON_SUMMARY.md)
- Analysis: [SEARCH_ENGINE_ANALYSIS.md](SEARCH_ENGINE_ANALYSIS.md)
