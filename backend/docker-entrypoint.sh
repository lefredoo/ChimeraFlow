#!/bin/sh
# Container entrypoint: apply migrations, then serve the API.
#
# Two explicit modes, chosen by the presence of DOPPLER_TOKEN (never a silent fallback):
#   doppler  DOPPLER_TOKEN is set (production): the Doppler CLI fetches every other
#            variable at start. If Doppler is unreachable or the token is invalid the
#            container stops, it does not start with a partial configuration.
#   env      DOPPLER_TOKEN is not set (local compose, tests): variables come from the
#            container environment as given.
set -eu

# Single-quoted on purpose: ${BACKEND_PORT} is expanded by the inner shell, after
# Doppler has injected it.
SERVE='alembic upgrade head && exec uvicorn main:app --host 0.0.0.0 --port "${BACKEND_PORT:-8000}"'

if [ -n "${DOPPLER_TOKEN:-}" ]; then
    echo "entrypoint: mode=doppler (configuration fetched by the Doppler CLI)"
    # --no-fallback: no encrypted secrets copy written to disk in a stateless container
    exec doppler run --no-check-version --no-fallback -- sh -c "$SERVE"
fi

echo "entrypoint: mode=env (DOPPLER_TOKEN not set, configuration read from the container environment)"
exec sh -c "$SERVE"
