-- ============================================================
-- Phase 3: Reconciliation Totals View
-- ============================================================
-- Provides summary totals for user verification.

-- Drop and recreate to change structure
DROP MATERIALIZED VIEW IF EXISTS reconciliation_totals;

CREATE MATERIALIZED VIEW reconciliation_totals AS
SELECT
    -- Overall totals (from orders only, no joins that multiply rows)
    (SELECT COUNT(*) FROM orders) as total_orders,
    (SELECT COALESCE(SUM(total_cents), 0) FROM orders) as total_revenue_cents,
    (SELECT COUNT(*) FROM products) as total_products,
    (SELECT COUNT(*) FROM locations) as total_locations,
    -- Date range
    (SELECT MIN(created_at)::date FROM orders) as min_date,
    (SELECT MAX(created_at)::date FROM orders) as max_date,
    -- Breakdown by source
    (SELECT COUNT(*) FROM orders WHERE source = 'toast') as toast_orders,
    (SELECT COALESCE(SUM(total_cents), 0) FROM orders WHERE source = 'toast') as toast_revenue_cents,
    (SELECT COUNT(*) FROM orders WHERE source = 'doordash') as doordash_orders,
    (SELECT COALESCE(SUM(total_cents), 0) FROM orders WHERE source = 'doordash') as doordash_revenue_cents,
    (SELECT COUNT(*) FROM orders WHERE source = 'square') as square_orders,
    (SELECT COALESCE(SUM(total_cents), 0) FROM orders WHERE source = 'square') as square_revenue_cents,
    -- Data quality
    (SELECT COUNT(*) FROM products WHERE category IS NULL) as products_without_category,
    -- Errors: serious data integrity issues
    (
        (SELECT COUNT(*) FROM orders WHERE total_cents < 0) +
        (SELECT COUNT(*) FROM order_items WHERE quantity <= 0) +
        (SELECT COUNT(*) FROM order_items oi WHERE NOT EXISTS (SELECT 1 FROM products p WHERE p.id = oi.product_id)) +
        (SELECT COUNT(*) FROM orders o WHERE NOT EXISTS (SELECT 1 FROM order_items oi WHERE oi.order_id = o.id))
    ) as error_count,
    -- Warnings: potential issues worth reviewing
    (
        (SELECT COUNT(*) FROM orders WHERE total_cents = 0 AND voided = FALSE AND deleted = FALSE) +
        (SELECT COUNT(*) FROM products p WHERE NOT EXISTS (SELECT 1 FROM order_items oi WHERE oi.product_id = p.id)) +
        (SELECT COUNT(*) FROM orders WHERE voided = TRUE OR deleted = TRUE)
    ) as warning_count,
    -- Last updated
    NOW() as refreshed_at;

CREATE UNIQUE INDEX IF NOT EXISTS reconciliation_totals_idx
ON reconciliation_totals(refreshed_at);

-- Grant access
GRANT ALL ON reconciliation_totals TO service_role;
GRANT SELECT ON reconciliation_totals TO anon, authenticated;

-- Update refresh function to include reconciliation
CREATE OR REPLACE FUNCTION refresh_analytics_views()
RETURNS void
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY daily_sales;
    REFRESH MATERIALIZED VIEW CONCURRENTLY hourly_sales;
    REFRESH MATERIALIZED VIEW CONCURRENTLY product_performance;
    REFRESH MATERIALIZED VIEW CONCURRENTLY product_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY channel_breakdown;
    REFRESH MATERIALIZED VIEW CONCURRENTLY reconciliation_totals;
END;
$$;
