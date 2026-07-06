.PHONY: format sort lint miman-test miman-docker-build miman-deploy-check miman-release-all miman-compose-config

# Variables
ISORT_OPTIONS = --profile black
PROJECT_NAME := mem0ai

# --- miman (LetA) release-artifact targets — additive, never touch the targets above ---
MIMAN_IMAGE_NAME ?= miman
MIMAN_REGISTRY ?= registry.digitalocean.com
MIMAN_REGISTRY_NAMESPACE ?= leta-container-registry
MIMAN_IMAGE_REPO ?= $(MIMAN_REGISTRY)/$(MIMAN_REGISTRY_NAMESPACE)/$(MIMAN_IMAGE_NAME)
VERSION ?=
MIMAN_IMAGE_REVISION ?= $(shell git rev-parse HEAD 2>/dev/null || echo unknown)

# Default target
all: format sort lint

install:
	hatch env create

install_all:
	pip install ruff==0.6.9 groq together boto3 litellm ollama chromadb weaviate weaviate-client sentence_transformers vertexai \
	            google-generativeai elasticsearch opensearch-py vecs "pinecone<7.0.0" pinecone-text faiss-cpu langchain-community \
							upstash-vector azure-search-documents langchain-memgraph langchain-neo4j langchain-aws rank-bm25 pymochow pymongo psycopg kuzu databricks-sdk valkey

# Format code with ruff
format:
	hatch run format

# Sort imports with isort
sort:
	hatch run isort mem0/

# Lint code with ruff
lint:
	hatch run lint

docs:
	cd docs && mintlify dev

build:
	hatch build

publish:
	hatch publish

clean:
	rm -rf dist

test:
	hatch run test

test-py-3.10:
	hatch run dev_py_3_10:test

test-py-3.11:
	hatch run dev_py_3_11:test

test-py-3.12:
	hatch run dev_py_3_12:test

# --- miman (LetA) targets (spec 03-M §11 M2) ---
miman-test:
	@if command -v hatch >/dev/null 2>&1; then \
		hatch run pytest tests/server/test_leta_qdrant_config.py -q; \
	else \
		python3 -m pytest tests/server/test_leta_qdrant_config.py -q; \
	fi

miman-docker-build:
	@test -n "$(VERSION)" || (echo "VERSION is required. Usage: make miman-docker-build VERSION=0.0.0-audit" >&2; exit 1)
	docker build \
		--build-arg IMAGE_SOURCE="https://github.com/LetA-Tech/miman" \
		--build-arg IMAGE_REVISION="$(MIMAN_IMAGE_REVISION)" \
		--build-arg IMAGE_VERSION="$(VERSION)" \
		-t "$(MIMAN_IMAGE_NAME):$(VERSION)" \
		-t "$(MIMAN_IMAGE_REPO):$(VERSION)" \
		-f Dockerfile .

miman-deploy-check:
	@bash scripts/deploy-check.sh

miman-release-all:
	@VERSION="$(VERSION)" bash scripts/release-all.sh

miman-compose-config:
	docker compose --env-file deploy/.env.example -f deploy/docker-compose.yml config
