-- ============================================================
-- Materialized Views for Fast Analytics Queries
-- ============================================================
-- NOTE: These views are intentionally accessible via the Data API
-- (anon/authenticated) as this is a read-only analytics dashboard.
-- The "materialized_view_in_api" linter warning is expected.
--
-- Indexes are created in 002_indexes.sql

-- ============================================================
-- Daily Sales (by location, date, channel, source)
-- ============================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS daily_sales AS
SELECT
    l.name as location,
    DATE(o.created_at) as date,
    o.channel,
    o.source,
    COUNT(*) as order_count,
    SUM(o.sales_cents) as sales_cents,
    SUM(o.tax_cents) as tax_cents,
    SUM(o.tip_cents) as tip_cents,
    SUM(o.total_cents) as total_cents,
    ROUND(AVG(o.sales_cents))::INTEGER as avg_order_cents
FROM orders o
JOIN locations l ON o.location_id = l.id
GROUP BY l.name, DATE(o.created_at), o.channel, o.source;

-- ============================================================
-- Hourly Sales (for time-of-day analysis)
-- ============================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS hourly_sales AS
SELECT
    l.name as location,
    DATE(o.created_at) as date,
    EXTRACT(HOUR FROM o.created_at)::INTEGER as hour,
    TRIM(TO_CHAR(o.created_at, 'Day')) as day_name,
    EXTRACT(DOW FROM o.created_at)::INTEGER as day_of_week,
    COUNT(*) as order_count,
    SUM(o.sales_cents) as sales_cents,
    SUM(o.tax_cents) as tax_cents,
    SUM(o.tip_cents) as tip_cents,
    SUM(o.total_cents) as total_cents
FROM orders o
JOIN locations l ON o.location_id = l.id
GROUP BY l.name, DATE(o.created_at), EXTRACT(HOUR FROM o.created_at),
         TO_CHAR(o.created_at, 'Day'), EXTRACT(DOW FROM o.created_at);

-- ============================================================
-- Product Performance (by location and channel)
-- ============================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS product_performance AS
SELECT
    p.canonical_name as product,
    p.category,
    l.name as location,
    o.channel,
    COUNT(DISTINCT o.id) as order_count,
    SUM(oi.quantity) as units_sold,
    SUM(oi.total_cents) as sales_cents,
    -- Verification columns
    ROUND(AVG(oi.unit_price_cents))::INTEGER as avg_price_cents,
    MIN(oi.unit_price_cents) as min_price_cents,
    MAX(oi.unit_price_cents) as max_price_cents,
    ARRAY_AGG(DISTINCT o.source) as sources
FROM order_items oi
JOIN orders o ON oi.order_id = o.id
JOIN products p ON oi.product_id = p.id
JOIN locations l ON o.location_id = l.id
GROUP BY p.canonical_name, p.category, l.name, o.channel;

-- ============================================================
-- Product Summary (aggregated across all locations)
-- ============================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS product_summary AS
SELECT
    p.canonical_name as product,
    p.category,
    COUNT(DISTINCT o.id) as total_orders,
    SUM(oi.quantity) as total_units,
    SUM(oi.total_cents) as total_sales_cents,
    ROUND(AVG(oi.unit_price_cents))::INTEGER as avg_price_cents,
    MIN(oi.unit_price_cents) as min_price_cents,
    MAX(oi.unit_price_cents) as max_price_cents,
    ARRAY_AGG(DISTINCT o.source) as sources,
    ARRAY_AGG(DISTINCT l.name) as locations,
    -- Price variance indicator (high variance = potential data issue)
    CASE
        WHEN MAX(oi.unit_price_cents) > MIN(oi.unit_price_cents) * 2
        THEN true ELSE false
    END as price_variance_flag
FROM order_items oi
JOIN orders o ON oi.order_id = o.id
JOIN products p ON oi.product_id = p.id
JOIN locations l ON o.location_id = l.id
GROUP BY p.canonical_name, p.category;

-- ============================================================
-- Channel Breakdown (by location, channel, source)
-- ============================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS channel_breakdown AS
SELECT
    l.name as location,
    o.channel,
    o.source,
    COUNT(*) as order_count,
    SUM(o.sales_cents) as sales_cents,
    SUM(o.tax_cents) as tax_cents,
    SUM(o.tip_cents) as tip_cents,
    SUM(o.total_cents) as total_cents,
    ROUND(AVG(o.sales_cents))::INTEGER as avg_order_cents
FROM orders o
JOIN locations l ON o.location_id = l.id
GROUP BY l.name, o.channel, o.source;

-- ============================================================
-- Location Summary (aggregated across all channels/sources)
-- ============================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS location_summary AS
SELECT
    l.name as location,
    COUNT(*) as order_count,
    SUM(o.sales_cents) as sales_cents,
    SUM(o.tax_cents) as tax_cents,
    SUM(o.tip_cents) as tip_cents,
    SUM(o.total_cents) as total_cents,
    ROUND(AVG(o.sales_cents))::INTEGER as avg_order_cents
FROM orders o
JOIN locations l ON o.location_id = l.id
GROUP BY l.name;

-- ============================================================
-- Reconciliation Totals (data quality/verification)
-- ============================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS reconciliation_totals AS
SELECT
    -- Overall totals (from orders only, no joins that multiply rows)
    (SELECT COUNT(*) FROM orders) as total_orders,
    (SELECT COALESCE(SUM(total_cents), 0) FROM orders) as total_sales_cents,
    (SELECT COUNT(*) FROM products) as total_products,
    (SELECT COUNT(*) FROM locations) as total_locations,
    -- Date range
    (SELECT MIN(created_at)::date FROM orders) as min_date,
    (SELECT MAX(created_at)::date FROM orders) as max_date,
    -- Breakdown by source
    (SELECT COUNT(*) FROM orders WHERE source = 'toast') as toast_orders,
    (SELECT COALESCE(SUM(total_cents), 0) FROM orders WHERE source = 'toast') as toast_sales_cents,
    (SELECT COUNT(*) FROM orders WHERE source = 'doordash') as doordash_orders,
    (SELECT COALESCE(SUM(total_cents), 0) FROM orders WHERE source = 'doordash') as doordash_sales_cents,
    (SELECT COUNT(*) FROM orders WHERE source = 'square') as square_orders,
    (SELECT COALESCE(SUM(total_cents), 0) FROM orders WHERE source = 'square') as square_sales_cents,
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

-- ============================================================
-- Grants
-- ============================================================

GRANT ALL ON daily_sales TO service_role;
GRANT ALL ON hourly_sales TO service_role;
GRANT ALL ON product_performance TO service_role;
GRANT ALL ON product_summary TO service_role;
GRANT ALL ON channel_breakdown TO service_role;
GRANT ALL ON location_summary TO service_role;
GRANT ALL ON reconciliation_totals TO service_role;

GRANT SELECT ON daily_sales TO anon, authenticated;
GRANT SELECT ON hourly_sales TO anon, authenticated;
GRANT SELECT ON product_performance TO anon, authenticated;
GRANT SELECT ON product_summary TO anon, authenticated;
GRANT SELECT ON channel_breakdown TO anon, authenticated;
GRANT SELECT ON location_summary TO anon, authenticated;
GRANT SELECT ON reconciliation_totals TO anon, authenticated;
