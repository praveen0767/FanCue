# Dockerfile for FanCue backend (FastAPI)
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    "pydantic>=2.7.0" \
    "pyyaml>=6.0.0" \
    "fastembed>=0.9.0" \
    "qdrant-client>=1.13.0" \
    "uvicorn[standard]>=0.30.0" \
    "fastapi>=0.110.0" \
    "httpx>=0.27.0" \
    "python-dotenv>=1.0.0" \
    "jsonschema>=4.20.0"

COPY backend/ ./backend/
COPY ingestion/ ./ingestion/
COPY contracts/ ./contracts/
COPY data/ ./data/

EXPOSE 8000

# Render (and most PaaS providers) inject a PORT env variable at runtime.
# Shell-form CMD allows ${PORT:-8000} expansion; array-form cannot do this.
CMD uvicorn backend.app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
