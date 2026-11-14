# ChimeraFlow Backend Dockerfile
# Stages:
#   base     runtime dependencies (system packages + pip requirements), no code
#   doppler  Doppler CLI, installed from the signed official apt repository
#   test     base + dev tools + code and tests, runs the suite with mdbtools
#   redis    redis:7-alpine + Doppler CLI (production compose only: the password
#            comes from Doppler, so DOPPLER_TOKEN is the only variable passed)
#   runtime  (default target) base + Doppler CLI + code without tests + synthetic
#            data baked at /data; runs migrations then the API
#
# The runtime stage reads the synthetic data from a named build context `data`
# (the repository `data/` directory, outside the backend/ build context):
#   docker build --build-context data=./data -t chimeraflow-backend backend
# docker compose passes it through `additional_contexts` (see docker-compose*.yml).
# The test stage does not need it.

FROM python:3.13-slim AS base

WORKDIR /app

# mdbtools: Access reader used in production (ACCESS_READER=mdbtools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    mdbtools \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Doppler CLI: pinned version from the official apt repository. apt verifies the
# package signature; the repository key is checked against the pinned fingerprint
# before it is trusted. Only the static binary is copied to the other stages, so
# curl and gnupg stay out of them.
FROM python:3.13-slim AS doppler
ARG DOPPLER_VERSION=3.77.1
ARG DOPPLER_APT_FPR=BD8F51EC1320748CED4E6E3BDE2A7741A397C129
RUN set -eu \
    && apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
    && curl -fsSL https://packages.doppler.com/public/cli/gpg.DE2A7741A397C129.key -o /tmp/doppler.asc \
    && actual="$(gpg --show-keys --with-colons /tmp/doppler.asc | awk -F: '/^fpr:/ {print $10; exit}')" \
    && if [ "$actual" != "$DOPPLER_APT_FPR" ]; then \
         echo "Doppler apt key fingerprint mismatch: got $actual" >&2; exit 1; \
       fi \
    && pubs="$(gpg --show-keys --with-colons /tmp/doppler.asc | grep -c '^pub:')" \
    && if [ "$pubs" != "1" ]; then \
         echo "Doppler key file must hold exactly one public key, found $pubs" >&2; exit 1; \
       fi \
    && gpg --dearmor < /tmp/doppler.asc > /usr/share/keyrings/doppler.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/doppler.gpg] https://packages.doppler.com/public/cli/deb/debian any-version main" \
       > /etc/apt/sources.list.d/doppler-cli.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends "doppler=${DOPPLER_VERSION}" \
    && doppler --version \
    && rm -rf /var/lib/apt/lists/*

# Test runner. Mount the synthetic data at /data (from the repository root):
#   docker build --target test -t chimeraflow-backend-test backend
#   docker run --rm -v "${PWD}/data:/data:ro" chimeraflow-backend-test
FROM base AS test
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY . .
CMD ["python", "-m", "pytest", "tests", "-q"]

# Application code without tests and dev files, so the runtime image does not
# carry them (the .dockerignore applies to every stage, the test stage needs tests).
FROM base AS source
COPY . .
RUN rm -rf tests requirements-dev.txt pytest.ini ruff.toml spike_access.py README.md Dockerfile docker-entrypoint.sh

# Redis for the production compose: the Doppler CLI injects REDIS_PASSWORD.
# Same static binary as the API image, so the version is pinned once above.
FROM redis:7-alpine AS redis
COPY --from=doppler /usr/bin/doppler /usr/local/bin/doppler

FROM base AS runtime

COPY --from=doppler /usr/bin/doppler /usr/local/bin/doppler
COPY --from=source /app/ /app/
# Synthetic data baked in the image (read-only for the app user, no host path on the VPS)
COPY --from=data . /data
COPY --chmod=755 docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

# Non-root user. /app stays root-owned and read-only for it: the runtime writes
# nothing under /app (only tests write files). HOME points to a writable
# directory because the Doppler CLI keeps its (empty) config there.
RUN useradd -r -u 10001 app && mkdir /home/app && chown app /home/app
ENV HOME=/home/app \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

# Health check (stdlib only: no extra package or curl in the image)
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2)" || exit 1

# Apply migrations, then serve. A failed migration stops the container before
# it serves requests (see DECISIONS_LOG.md). The entrypoint runs through the
# Doppler CLI when DOPPLER_TOKEN is set (production), directly otherwise.
USER app

ENTRYPOINT ["docker-entrypoint.sh"]
