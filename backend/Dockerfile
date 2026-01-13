# Multi-stage build for optimized M1 8GB deployment

# Stage 1: Builder for dependencies
FROM python:3.9-slim AS builder

WORKDIR /app

# System dependencies for Scientific Python
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install dependencies with cache optimization
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime image
FROM python:3.9-slim AS runtime

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser \
    && mkdir -p /app/workspace/datasets \
    && chown -R appuser:appuser /app

# Copy application code
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Create data directory
RUN mkdir -p /app/workspace/datasets

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run with Gunicorn for production with M1 8GB optimizations
CMD ["gunicorn", "app.main:app", "-w", "2", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "--preload"]