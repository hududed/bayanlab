.PHONY: help install dev up down logs test clean

help:  ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies with uv
	uv pip install -e .

dev:  ## Install development dependencies
	uv pip install -e ".[dev]"

up:  ## Start all services with docker-compose
	cd infra/docker && docker-compose up -d

down:  ## Stop all services
	cd infra/docker && docker-compose down

logs:  ## Show logs from all services
	cd infra/docker && docker-compose logs -f

test:  ## Run tests
	pytest backend/tests/ -v --cov=backend

clean:  ## Clean up generated files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .coverage htmlcov

pipeline:  ## Run the full pipeline manually
	uv run python run_pipeline.py --pipeline all

api:  ## Run the API service locally
	uv run uvicorn backend.services.api_service.main:app --reload

db-shell:  ## Connect to the database
	docker exec -it docker-db-1 psql -U bayan -d bayan_backbone
