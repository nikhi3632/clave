.PHONY: help setup run review review-stats lint lint-fix format test clean
.DEFAULT_GOAL := help

help:
	@echo ""
	@echo "ETL Pipeline"
	@echo "============"
	@echo ""
	@echo "  make setup         Create venv and install dependencies"
	@echo "  make run           Run full ETL pipeline"
	@echo "  make review        Interactive category review CLI"
	@echo "  make review-stats  Show category review statistics"
	@echo ""
	@echo "  make lint          Run ruff linter"
	@echo "  make lint-fix      Auto-fix lint issues"
	@echo "  make format        Format code with ruff"
	@echo "  make test          Run tests"
	@echo "  make clean         Remove generated files"
	@echo ""

setup:
	python3 -m venv .venv
	.venv/bin/pip install -e ".[dev]"

run:
	.venv/bin/python -m main

review:
	.venv/bin/python -m review

review-stats:
	.venv/bin/python -m review --stats

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
	rm -rf *.egg-info
	rm -rf .ruff_cache
