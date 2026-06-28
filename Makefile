.PHONY: install setup dev compose-dev test lint format migrate seed db-up db-down

# Package management
install:
	pip install -e .

install-uv:
	uv pip install -e .

install-all:
	pip install -e ".[all]"

install-all-uv:
	uv pip install -e ".[all]"

# Setup wizard
setup:
	python src/tokenfinops/setup_wizard.py

# Running the app locally
dev:
	uvicorn tokenfinops.main:app --host 0.0.0.0 --port 8000 --reload --app-dir src

# Running backing services via Docker Compose
db-up:
	docker-compose up -d postgres redis

db-down:
	docker-compose down

# Run full stack (database + application in containers)
compose-up:
	docker-compose up --build

compose-down:
	docker-compose down -v

# Database migrations
migrate:
	alembic upgrade head

# Code quality
lint:
	ruff check src tests
	mypy src

format:
	ruff format src tests

# Testing
test:
	pytest tests
