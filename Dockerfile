# Production Dockerfile for Remote Image Display API
FROM python:3.11-slim

# Prevent Python from writing .pyc and enable buffer flushing
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

WORKDIR /app

# Install system dependencies (for psycopg2, pillow, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Expose port (overridden by Railway $PORT at runtime)
EXPOSE 8000

# Run auto-seed on startup (idempotent: only creates initial admin/key if DB is empty) and launch uvicorn
CMD ["sh", "-c", "python seed.py && uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
