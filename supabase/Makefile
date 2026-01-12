.PHONY: help migrate refresh reset
.DEFAULT_GOAL := help

# Load .env file from parent directory
ifneq (,$(wildcard ../.env))
    include ../.env
    export
endif

help:
	@echo ""
	@echo "Database (Supabase)"
	@echo "==================="
	@echo ""
	@echo "  make migrate   Apply SQL migrations"
	@echo "  make refresh   Refresh materialized views"
	@echo "  make reset     Drop and recreate (destructive!)"
	@echo ""

migrate:
	@echo "Applying migrations..."
	@if [ -z "$(DATABASE_URL)" ]; then \
		echo "Error: DATABASE_URL not set"; \
		echo "Add it to .env (get from Supabase dashboard > Settings > Database)"; \
		exit 1; \
	fi
	@for f in migrations/*.sql; do \
		echo "  $$f"; \
		PGOPTIONS='--client-min-messages=warning' psql "$(DATABASE_URL)" -f "$$f" -q; \
	done
	@echo "Done"

refresh:
	@echo "Refreshing materialized views..."
	@psql "$(DATABASE_URL)" -c "SELECT refresh_analytics_views();" -q
	@echo "Done"

reset:
	@echo "WARNING: This will drop ALL tables and data!"
	@read -p "Type 'yes' to confirm: " confirm && [ "$$confirm" = "yes" ] || exit 1
	@psql "$(DATABASE_URL)" -q -c "\
		DROP SCHEMA public CASCADE; \
		CREATE SCHEMA public; \
		GRANT ALL ON SCHEMA public TO postgres; \
		GRANT ALL ON SCHEMA public TO public; \
		GRANT ALL ON SCHEMA public TO service_role; \
		GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role; \
		GRANT CREATE ON SCHEMA public TO anon, authenticated, service_role;"
	@$(MAKE) migrate
	@echo "Database reset complete"
