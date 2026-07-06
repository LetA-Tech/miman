#!/usr/bin/env bash
# Runs in WORKDIR /app/server (set by the root Dockerfile) so alembic.ini's
# relative script_location resolves and `import db`/`import models` work.
set -euo pipefail

alembic upgrade head

exec uvicorn main:app --host 0.0.0.0 --port 8000
