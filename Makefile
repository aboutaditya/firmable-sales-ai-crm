SHELL := /bin/sh

# Load local defaults when present. Command-line assignments still take precedence.
-include .env

PYTHON ?= python3
PIP ?= $(PYTHON) -m pip
NPM ?= npm
BACKEND_HOST ?= 127.0.0.1
BACKEND_PORT ?= 8000
FRONTEND_PORT ?= 3000
DATASET ?= data/processed/demo-companies.parquet
RAW_SOURCE ?= $(if $(RAW_DATASET_URL),$(RAW_DATASET_URL),data/demo/observations.jsonl)
DATASET_VERSION ?= demo-v1
MIN_SCORE ?= 0
MAX_RECORDS ?= 1000
BATCH_SIZE ?= 1000
CHECKPOINT ?= $(DATASET).checkpoint.json
DATASET_RUNS_DIR ?= data/processed/dataset_runs
DATASET_NAME ?= companies
AUTH_REQUIRED=false
NEXT_PUBLIC_LOCAL_DEMO=true
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1

ETL_MAX_RECORDS := $(if $(MAX_RECORDS),--max-records $(MAX_RECORDS),)

export OPENROUTER_API_KEY OPENROUTER_BASE_URL OPENROUTER_MODEL \
	OPENROUTER_HTTP_REFERER OPENROUTER_APP_TITLE \
	OPENROUTER_INPUT_COST_PER_1K OPENROUTER_OUTPUT_COST_PER_1K

.PHONY: help init init-backend init-frontend install-backend install-frontend \
        etl migrate sync test test-python test-frontend build-frontend \
        eval-openrouter eval-openrouter-v2 eval-report eval-compare start-backend start-frontend start dev compile clean-cache

help:
	@printf '%s\n' \
		'Available targets:' \
		'  make init             Install backend/frontend dependencies' \
		'  make init-backend     Install Python dependencies and package' \
		'  make init-frontend    Install frontend dependencies' \
		'  make etl              Build the local Parquet dataset from the demo source' \
		'  make migrate          Apply Alembic migrations using DATABASE_URL' \
		'  make sync             Sync qualified companies using DATABASE_URL' \
		'  make eval-openrouter  Run labelled account-scoring cases through OpenRouter' \
		'  make eval-openrouter-v2 Run the v2 account-scoring prompt through OpenRouter' \
		'  make eval-report      Calculate evaluation metrics from saved predictions' \
		'  make eval-compare     Compare v2 metrics with the v1 baseline' \
		'  make start-backend    Start FastAPI on $(BACKEND_HOST):$(BACKEND_PORT)' \
		'  make start-frontend   Start Next.js on $(FRONTEND_PORT)' \
		'  make start             Start backend and frontend together' \
		'  make test             Run Python tests and frontend build' \
		'  make build-frontend   Create a production frontend build'

init: init-backend init-frontend

init-backend:
	$(PIP) install -r requirements-dev.txt
	$(PIP) install -e .
	@echo 'Backend dependencies installed. Local Parquet mode does not require a .env file.'

init-frontend:
	cd frontend && $(NPM) install
	@if [ ! -f frontend/.env.local ]; then cp frontend/.env.example frontend/.env.local; echo 'Created frontend/.env.local; add Supabase values for login.'; fi

install-backend: init-backend
install-frontend: init-frontend

etl:
	$(PYTHON) -m sales_intelligence etl $(RAW_SOURCE) \
		--output $(DATASET) --dataset-version $(DATASET_VERSION) \
		--checkpoint $(CHECKPOINT) --checkpoint-interval 100 \
		--dataset-runs-dir $(DATASET_RUNS_DIR) --dataset-name $(DATASET_NAME) $(ETL_MAX_RECORDS)

migrate:
	@test -n "$(DATABASE_URL)" || (echo 'DATABASE_URL is required. Example: make migrate DATABASE_URL=postgresql://...'; exit 1)
	DATABASE_URL="$(DATABASE_URL)" alembic upgrade head

sync:
	$(PYTHON) -m sales_intelligence sync $(DATASET) \
		--min-score $(MIN_SCORE) --dataset-version $(DATASET_VERSION) --batch-size $(BATCH_SIZE)

eval-openrouter:
	$(PYTHON) evals/run_openrouter_eval.py \
		--cases evals/datasets/account_scoring.jsonl \
		--prompt prompts/account_scoring/v1.txt \
		--prompt-version account-scoring-v1 \
		--resume \
		--output evals/results/openrouter-predictions.jsonl

eval-openrouter-v2:
	$(PYTHON) evals/run_openrouter_eval.py \
		--cases evals/datasets/account_scoring.jsonl \
		--prompt prompts/account_scoring/v2.txt \
		--prompt-version account-scoring-v2 \
		--resume \
		--output evals/results/openrouter-predictions-v2.jsonl

eval-report:
	$(PYTHON) evals/harness.py \
		--cases evals/datasets/account_scoring.jsonl \
		--predictions evals/results/openrouter-predictions.jsonl \
		--prompt-version account-scoring-v1 \
		--output evals/results/openrouter-account-scoring-v1.json

eval-compare:
	$(PYTHON) evals/harness.py \
		--cases evals/datasets/account_scoring.jsonl \
		--predictions evals/results/openrouter-predictions-v2.jsonl \
		--prompt-version account-scoring-v2 \
		--previous-predictions evals/results/openrouter-predictions.jsonl \
		--previous-prompt-version account-scoring-v1 \
		--output evals/results/openrouter-account-scoring-v2.json

start-backend:
	ANALYTICAL_DATASET=$(DATASET) uvicorn sales_intelligence.backend.main:app \
		--host $(BACKEND_HOST) --port $(BACKEND_PORT) --reload

start-frontend:
	cd frontend && $(NPM) run dev -- --hostname 127.0.0.1 --port $(FRONTEND_PORT)

start:
	@trap 'kill 0' INT TERM EXIT; \
		$(MAKE) start-backend & \
		$(MAKE) start-frontend & \
		wait

dev: start

test: test-python build-frontend

test-python:
	$(PYTHON) -m unittest discover -s tests -v
	$(PYTHON) -m compileall -q sales_intelligence scripts

test-frontend:
	cd frontend && $(NPM) run build

build-frontend: test-frontend

compile:
	$(PYTHON) -m compileall -q sales_intelligence scripts

clean-cache:
	find . -type d \( -name __pycache__ -o -name .pytest_cache \) -prune -exec rm -rf {} +
