.PHONY: help setup clean
.DEFAULT_GOAL := help

help:
	@echo ""
	@echo "Restaurant Analytics Dashboard"
	@echo "=============================="
	@echo ""
	@echo "Quick Start:"
	@echo "  make setup   Install all dependencies"
	@echo ""
	@echo "Components (run from each directory):"
	@echo "  cd app && make dev        Frontend (localhost:3000)"
	@echo "  cd api && make dev        API (localhost:8000)"
	@echo "  cd etl && make run        ETL pipeline"
	@echo "  cd supabase && make migrate   Database migrations"
	@echo ""
	@echo "See Makefiles in: app/, api/, etl/, supabase/"
	@echo ""

setup:
	@echo "Setting up all components..."
	cd app && $(MAKE) setup
	cd api && $(MAKE) setup
	cd etl && $(MAKE) setup
	@echo ""
	@echo "Setup complete! Next steps:"
	@echo "  1. Copy .env.example to .env and fill in values"
	@echo "  2. Run: cd supabase && make migrate"
	@echo "  3. Run: cd etl && make run"
	@echo "  4. Run: cd app && make dev"
	@echo ""

clean:
	cd app && $(MAKE) clean
	cd api && $(MAKE) clean
	cd etl && $(MAKE) clean
	@echo "Cleaned"
