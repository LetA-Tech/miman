FROM python:3.12-slim
# Conflict pin, not staleness: upstream's own test matrix caps at 3.12
# (.github/workflows/ci.yml). Bump when upstream's matrix does.

ARG IMAGE_SOURCE="https://github.com/LetA-Tech/miman"
ARG IMAGE_REVISION="unknown"
ARG IMAGE_VERSION="dev"

LABEL org.opencontainers.image.source="${IMAGE_SOURCE}" \
      org.opencontainers.image.revision="${IMAGE_REVISION}" \
      org.opencontainers.image.version="${IMAGE_VERSION}" \
      org.opencontainers.image.title="miman"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# psycopg (bare, no [c]/[binary] extra — server/requirements.txt) dlopens
# libpq at runtime; python:3.12-slim ships without it.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 10001 miman \
    && useradd --system --uid 10001 --gid miman --create-home --home-dir /home/miman miman

WORKDIR /app

# Local patched tree, never PyPI mem0ai (R1/A3 — image provenance).  Editable
# install so `mem0.__file__` resolves under /app instead of a site-packages
# copy indistinguishable from a PyPI install.
COPY pyproject.toml poetry.lock README.md LICENSE ./
COPY mem0 ./mem0
RUN python -m pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e .

# server/requirements.txt pins its own mem0ai>=0.1.48 line (upstream default
# install path) — filtered out so the floating PyPI install never shadows the
# local editable one above.
COPY server/requirements.txt ./server-requirements.txt
RUN grep -vE '^mem0ai([<>= ].*)?$' server-requirements.txt > server-runtime-requirements.txt \
    && pip install --no-cache-dir -r server-runtime-requirements.txt \
    && rm -f server-requirements.txt server-runtime-requirements.txt

COPY server ./server
COPY docker/entrypoint.sh /entrypoint.sh

RUN mkdir -p /app/history \
    && chmod +x /entrypoint.sh \
    && chown -R miman:miman /app /home/miman

USER miman
WORKDIR /app/server

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3).read()" || exit 1

ENTRYPOINT ["/entrypoint.sh"]
