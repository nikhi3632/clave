.PHONY: help setup dev build start lint test clean
.DEFAULT_GOAL := help

help:
	@echo ""
	@echo "App (Next.js)"
	@echo "============="
	@echo ""
	@echo "  make setup      Install npm dependencies"
	@echo "  make dev        Start dev server (localhost:3000)"
	@echo "  make build      Production build"
	@echo "  make start      Start production server"
	@echo ""
	@echo "  make lint       Run ESLint"
	@echo "  make test       Run tests"
	@echo "  make clean      Remove generated files"
	@echo ""

setup:
	npm install

dev:
	npm run dev

build:
	npm run build

start:
	npm run start:custom

lint:
	npm run lint

test:
	npm test

clean:
	rm -rf dist
	rm -rf node_modules
	rm -rf .next
