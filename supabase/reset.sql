-- ============================================================
-- Database Reset
-- ============================================================
-- Drops all tables and views to allow clean re-migration.
-- Run with: psql $DATABASE_URL -f supabase/reset.sql

-- Drop materialized views first
DROP MATERIALIZED VIEW IF EXISTS reconciliation_totals CASCADE;
DROP MATERIALIZED VIEW IF EXISTS channel_breakdown CASCADE;
DROP MATERIALIZED VIEW IF EXISTS product_performance CASCADE;
DROP MATERIALIZED VIEW IF EXISTS product_summary CASCADE;
DROP MATERIALIZED VIEW IF EXISTS hourly_sales CASCADE;
DROP MATERIALIZED VIEW IF EXISTS daily_sales CASCADE;

-- Drop regular views
DROP VIEW IF EXISTS anomaly_summary CASCADE;
DROP VIEW IF EXISTS price_anomalies CASCADE;
DROP VIEW IF EXISTS product_verification CASCADE;

-- Drop tables (order matters due to foreign keys)
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS locations CASCADE;
DROP TABLE IF EXISTS product_category_cache CASCADE;
DROP TABLE IF EXISTS category_review_queue CASCADE;
DROP TABLE IF EXISTS etl_anomalies CASCADE;

-- Drop functions
DROP FUNCTION IF EXISTS refresh_analytics_views();
DROP FUNCTION IF EXISTS execute_readonly_query(TEXT);

-- Done
SELECT 'Database reset complete' AS status;
