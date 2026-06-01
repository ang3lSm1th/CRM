import os


bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "eventlet")
workers = int(os.getenv("WEB_CONCURRENCY", "1"))
threads = int(os.getenv("GUNICORN_THREADS", "1"))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))
accesslog = "-"
errorlog = "-"
capture_output = True
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
worker_tmp_dir = "/dev/shm" if os.path.isdir("/dev/shm") else None
