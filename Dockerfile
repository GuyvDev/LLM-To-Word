# ── Build stage ────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS base

WORKDIR /app

# System deps for lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2-dev libxslt1-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt         ./requirements.txt
COPY api/requirements.txt     ./api/requirements.txt

# Install all deps in one layer
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -r api/requirements.txt

# Copy source
COPY md2docx.py   ./md2docx.py
COPY api/         ./api/

# ── Runtime ────────────────────────────────────────────────────────────────────
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
