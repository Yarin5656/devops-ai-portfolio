"""
Flask application with Prometheus metrics instrumentation.
Exposes /, /health, and /metrics endpoints.
"""

import time
import logging

from flask import Flask, jsonify, Response
from prometheus_client import (
    Counter,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
    REGISTRY,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------
app = Flask(__name__)

# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "http_status"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

HEALTH_CHECK_COUNT = Counter(
    "health_check_requests_total",
    "Total number of /health endpoint requests",
)


# ---------------------------------------------------------------------------
# Helper: track every request
# ---------------------------------------------------------------------------
def track_request(endpoint: str, method: str, status: int, duration: float) -> None:
    REQUEST_COUNT.labels(method=method, endpoint=endpoint, http_status=str(status)).inc()
    REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    start = time.time()
    payload = {
        "service": "devops-monitoring-demo",
        "status": "running",
        "version": "1.0.0",
        "endpoints": ["/", "/health", "/metrics"],
    }
    duration = time.time() - start
    track_request("/", "GET", 200, duration)
    logger.info("GET / 200")
    return jsonify(payload), 200


@app.route("/health")
def health():
    start = time.time()
    HEALTH_CHECK_COUNT.inc()
    payload = {"status": "healthy", "checks": {"app": "ok"}}
    duration = time.time() - start
    track_request("/health", "GET", 200, duration)
    logger.info("GET /health 200")
    return jsonify(payload), 200


@app.route("/metrics")
def metrics():
    """Expose Prometheus metrics."""
    data = generate_latest(REGISTRY)
    return Response(data, status=200, mimetype=CONTENT_TYPE_LATEST)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("Starting devops-monitoring-demo on port 5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
