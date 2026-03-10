# ── Stage: runtime ───────────────────────────────────────────────────────────
FROM python:3.12-slim

# Security: run as non-root user
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /app

# Install dependencies first to leverage Docker layer cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY app/ ./app/

# Drop to non-root
USER appuser

EXPOSE 8080

# Use the module path so Python can resolve imports correctly
CMD ["python", "-m", "app.main"]
