"""
Gunicorn configuration for CPG Conversational AI.
Single worker + 4 threads — avoids multi-process conflicts with DuckDB/SQLite.
"""
import threading

bind    = "0.0.0.0:5000"
workers = 1
threads = 4
worker_class = "gthread"
timeout  = 120
keepalive = 5

accesslog = "-"   # stdout
errorlog  = "-"   # stderr
loglevel  = "info"


def post_fork(server, worker):
    """Start the insights background thread inside the gunicorn worker process."""
    from frontend.app_with_auth import _insights_generation_loop
    t = threading.Thread(target=_insights_generation_loop, daemon=True, name="insights-bg")
    t.start()
    server.log.info("[gunicorn] insights background thread started in worker %s", worker.pid)
