# ChimeraFlow Backend Dockerfile
# Stages: base (runtime dependencies) -> test (adds dev tools, runs the suite
# with mdbtools) -> runtime (default target, runs migrations then the API)

FROM python:3.13-slim AS base

WORKDIR /app

# mdbtools: Access reader used in production (ACCESS_READER=mdbtools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    mdbtools \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Test runner. Mount the synthetic data at /data (from the repository root):
#   docker build --target test -t chimeraflow-backend-test backend
#   docker run --rm -v "${PWD}/data:/data:ro" chimeraflow-backend-test
FROM base AS test
RUN pip install --no-cache-dir -r requirements-dev.txt
CMD ["python", "-m", "pytest", "tests", "-q"]

FROM base AS runtime

# Non-root user. /app stays root-owned and read-only for it: the runtime writes
# nothing under /app (only tests write files).
RUN useradd -r -u 10001 app

EXPOSE 8000

# Health check (stdlib only: no extra package or curl in the image)
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2)" || exit 1

# Apply migrations, then serve. A failed migration stops the container before
# it serves requests (see DECISIONS_LOG.md).
USER app

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn main:app --host 0.0.0.0 --port \"${BACKEND_PORT:-8000}\""]
