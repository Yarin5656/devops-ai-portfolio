# ─────────────────────────────────────────────────────────────
# Stage 1 — dependency builder
# ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build tools needed for some native extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --upgrade pip \
 && pip install --no-cache-dir --prefix=/install -r requirements.txt


# ─────────────────────────────────────────────────────────────
# Stage 2 — lean runtime image
# ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

LABEL maintainer="devops-ai-portfolio" \
      version="1.0.0" \
      description="Incident Response API — classifies incidents and returns runbook guidance"

# Non-root user for container security
RUN groupadd -r appgroup && useradd -r -g appgroup -d /app -s /sbin/nologin appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY app/ ./app/

# Drop to non-root
USER appuser

# Uvicorn listens on this port
EXPOSE 8000

# Health-check using the /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Production-grade startup:
#   - 2 workers (adjust via WORKERS env var)
#   - access log disabled (handled by load-balancer/sidecar in prod)
#   - controlled by env vars so Helm/k8s can override at deploy time
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WORKERS:-2} --log-level ${LOG_LEVEL:-info}"]
