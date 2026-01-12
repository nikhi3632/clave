-- ============================================================
-- Phase 1: Product Verification Columns
-- ============================================================
-- Adds avg_price, min/max price, and sources to product_performance
-- for data verification and sanity checking.

-- Drop and recreate product_performance with verification columns
DROP MATERIALIZED VIEW IF EXISTS product_performance CASCADE;

CREATE MATERIALIZED VIEW product_performance AS
SELECT
    p.canonical_name as product,
    p.category,
    l.name as location,
    o.channel,
    COUNT(DISTINCT o.id) as order_count,
    SUM(oi.quantity) as units_sold,
    SUM(oi.total_cents) as revenue_cents,
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

CREATE UNIQUE INDEX IF NOT EXISTS product_perf_idx
ON product_performance(product, location, channel);

-- Grant access
GRANT ALL ON product_performance TO service_role;
GRANT SELECT ON product_performance TO anon, authenticated;

-- ============================================================
-- Product Summary View (aggregated across locations/channels)
-- ============================================================
-- Useful for quick overview without drilling into location/channel

CREATE MATERIALIZED VIEW IF NOT EXISTS product_summary AS
SELECT
    p.canonical_name as product,
    p.category,
    COUNT(DISTINCT o.id) as total_orders,
    SUM(oi.quantity) as total_units,
    SUM(oi.total_cents) as total_revenue_cents,
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

CREATE UNIQUE INDEX IF NOT EXISTS product_summary_idx
ON product_summary(product);

-- Grant access
GRANT ALL ON product_summary TO service_role;
GRANT SELECT ON product_summary TO anon, authenticated;

-- ============================================================
-- Update refresh function to include new view
-- ============================================================

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
END;
$$;
