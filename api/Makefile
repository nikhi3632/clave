.PHONY: help setup dev prod lint lint-fix format test clean
.DEFAULT_GOAL := help

help:
	@echo ""
	@echo "API (FastAPI)"
	@echo "============="
	@echo ""
	@echo "  make setup      Create venv and install dependencies"
	@echo "  make dev        Start dev server (localhost:8000)"
	@echo "  make prod       Start production server"
	@echo ""
	@echo "  make lint       Run ruff linter"
	@echo "  make lint-fix   Auto-fix lint issues"
	@echo "  make format     Format code with ruff"
	@echo "  make test       Run tests"
	@echo "  make clean      Remove generated files"
	@echo ""

setup:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

dev:
	.venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000

prod:
	.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

lint:
	.venv/bin/ruff check .

lint-fix:
	.venv/bin/ruff check --fix .

format:
	.venv/bin/ruff format .

test:
	.venv/bin/pytest -v

clean:
	rm -rf __pycache__
	rm -rf .pytest_cache
	rm -rf routers/__pycache__
	rm -rf services/__pycache__
	rm -rf models/__pycache__
