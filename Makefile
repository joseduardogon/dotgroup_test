.DEFAULT_GOAL := help
.PHONY: help install migrate run test lint format typecheck check docker-build docker-run

help: ## Show this help
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

install: ## Install dependencies and git hooks
	poetry install
	poetry run pre-commit install

migrate: ## Apply database migrations
	poetry run alembic upgrade head

run: migrate ## Run the API with auto-reload on http://localhost:8000
	poetry run uvicorn library_api.main:create_app --factory --reload

test: ## Run the test suite with coverage
	poetry run pytest

lint: ## Static analysis (ruff)
	poetry run ruff check .
	poetry run ruff format --check .

format: ## Auto-format and apply safe fixes
	poetry run ruff check --fix .
	poetry run ruff format .

typecheck: ## Strict type checking (mypy)
	poetry run mypy

check: lint typecheck test ## Everything CI runs

docker-build: ## Build the container image
	docker build -t dotgroup-test:latest .

docker-run: ## Run the container on http://localhost:8000
	docker compose up --build
