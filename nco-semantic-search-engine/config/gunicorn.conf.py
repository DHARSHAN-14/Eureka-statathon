"""Gunicorn config for low-memory Indian / AWS EC2 servers."""
import os

bind = os.getenv("GUNICORN_BIND", "0.0.0.0:5000")
workers = int(os.getenv("GUNICORN_WORKERS", "1"))
threads = int(os.getenv("GUNICORN_THREADS", "4"))
preload_app = True
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
keepalive = 5
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "500"))
max_requests_jitter = 50
worker_class = "gthread"
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
