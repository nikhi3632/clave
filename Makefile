.PHONY: help up down build logs clean setup migrate reset review review-stats lint lint-fix typecheck
.DEFAULT_GOAL := help

help:
	@echo ""
	@echo "Restaurant Analytics Dashboard"
	@echo "=============================="
	@echo ""
	@echo "Commands:"
	@echo "  make up           Start all services"
	@echo "  make down         Stop all services"
	@echo "  make setup        Run migrations + ETL (first-time setup)"
	@echo "  make migrate      Run migrations only (no ETL)"
	@echo "  make reset        Drop all tables and re-run setup"
	@echo "  make review       Interactive category review CLI"
	@echo "  make review-stats Show category classification stats"
	@echo "  make build        Rebuild containers"
	@echo "  make logs         View container logs"
	@echo "  make clean        Remove all Docker resources"
	@echo "  make lint         Run all linters"
	@echo "  make lint-fix     Run linters with auto-fix"
	@echo "  make typecheck    Run TypeScript type checking"
	@echo ""

up:
	docker compose up --build

setup:
	docker compose run --rm seed

migrate:
	docker compose run --rm seed sh -c 'for f in /supabase/migrations/*.sql; do echo "Applying $$f..."; psql "$$DATABASE_URL" -f "$$f" -q; done'

reset:
	docker compose build seed
	docker compose run --rm seed sh -c 'psql "$$DATABASE_URL" -f /supabase/reset.sql -q'
	docker compose run --rm seed

review:
	docker compose run --rm -it seed python -m review

review-stats:
	docker compose run --rm seed python -m review --stats

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

clean:
	docker compose down --rmi all --volumes --remove-orphans
	@echo "Docker resources cleaned up"

lint:
	@echo "Linting app (ESLint)..."
	@docker run --rm -v $(PWD)/app:/app -w /app node:20-slim sh -c "npm ci --silent && npm run lint"
	@echo "Linting api + etl (ruff)..."
	@docker run --rm -v $(PWD):/src -w /src ghcr.io/astral-sh/ruff:latest check api/ etl/
	@echo "All lint checks passed"

lint-fix:
	@echo "Fixing app (ESLint)..."
	@docker run --rm -v $(PWD)/app:/app -w /app node:20-slim sh -c "npm ci --silent && npm run lint -- --fix"
	@echo "Fixing api + etl (ruff)..."
	@docker run --rm -v $(PWD):/src -w /src ghcr.io/astral-sh/ruff:latest check api/ etl/ --fix
	@echo "Auto-fix complete"

typecheck:
	@echo "Type checking app (TypeScript)..."
	@docker run --rm -v $(PWD)/app:/app -w /app node:20-slim sh -c "npm ci --silent && npm run typecheck"
	@echo "Type check passed"
