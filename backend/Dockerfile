# Multi-purpose production Dockerfile for FastAPI Backend and Celery Worker
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install system dependencies & curl for container health check
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY backend/ /app/

# Create non-root user for security compliance
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/logs && \
    chown -R appuser:appuser /app

USER appuser

# Expose backend port
EXPOSE 8000

# Default health check for FastAPI
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Default command runs FastAPI via Uvicorn (override with celery for worker container)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
