-- ============================================================
-- Materialized Views for Fast Analytics Queries
-- ============================================================
-- NOTE: These views are intentionally accessible via the Data API
-- (anon/authenticated) as this is a read-only analytics dashboard.
-- The "materialized_view_in_api" linter warning is expected.

-- Daily sales by location and channel
CREATE MATERIALIZED VIEW IF NOT EXISTS daily_sales AS
SELECT
    l.name as location,
    DATE(o.created_at) as date,
    o.channel,
    o.source,
    COUNT(*) as order_count,
    SUM(o.total_cents) as revenue_cents,
    ROUND(AVG(o.total_cents))::INTEGER as avg_order_cents
FROM orders o
JOIN locations l ON o.location_id = l.id
GROUP BY l.name, DATE(o.created_at), o.channel, o.source;

CREATE UNIQUE INDEX IF NOT EXISTS daily_sales_idx
ON daily_sales(location, date, channel, source);

-- Hourly sales pattern
CREATE MATERIALIZED VIEW IF NOT EXISTS hourly_sales AS
SELECT
    l.name as location,
    DATE(o.created_at) as date,
    EXTRACT(HOUR FROM o.created_at)::INTEGER as hour,
    TRIM(TO_CHAR(o.created_at, 'Day')) as day_name,
    EXTRACT(DOW FROM o.created_at)::INTEGER as day_of_week,
    COUNT(*) as order_count,
    SUM(o.total_cents) as revenue_cents
FROM orders o
JOIN locations l ON o.location_id = l.id
GROUP BY l.name, DATE(o.created_at), EXTRACT(HOUR FROM o.created_at),
         TO_CHAR(o.created_at, 'Day'), EXTRACT(DOW FROM o.created_at);

CREATE UNIQUE INDEX IF NOT EXISTS hourly_sales_idx
ON hourly_sales(location, date, hour);

-- Product performance
CREATE MATERIALIZED VIEW IF NOT EXISTS product_performance AS
SELECT
    p.canonical_name as product,
    p.category,
    l.name as location,
    o.channel,
    COUNT(DISTINCT o.id) as order_count,
    SUM(oi.quantity) as units_sold,
    SUM(oi.total_cents) as revenue_cents
FROM order_items oi
JOIN orders o ON oi.order_id = o.id
JOIN products p ON oi.product_id = p.id
JOIN locations l ON o.location_id = l.id
GROUP BY p.canonical_name, p.category, l.name, o.channel;

CREATE UNIQUE INDEX IF NOT EXISTS product_perf_idx
ON product_performance(product, location, channel);

-- Channel breakdown
CREATE MATERIALIZED VIEW IF NOT EXISTS channel_breakdown AS
SELECT
    l.name as location,
    o.channel,
    o.source,
    COUNT(*) as order_count,
    SUM(o.total_cents) as revenue_cents,
    ROUND(AVG(o.total_cents))::INTEGER as avg_order_cents,
    SUM(o.tip_cents) as total_tips_cents
FROM orders o
JOIN locations l ON o.location_id = l.id
GROUP BY l.name, o.channel, o.source;

CREATE UNIQUE INDEX IF NOT EXISTS channel_breakdown_idx
ON channel_breakdown(location, channel, source);

-- ============================================================
-- Refresh Function
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
    REFRESH MATERIALIZED VIEW CONCURRENTLY channel_breakdown;
END;
$$;

-- ============================================================
-- Safe SQL Execution (for AI-generated queries)
-- ============================================================

CREATE OR REPLACE FUNCTION execute_readonly_query(query_text TEXT)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
SET statement_timeout = '10s'
AS $$
DECLARE
    result JSONB;
    upper_query TEXT;
BEGIN
    upper_query := UPPER(TRIM(query_text));

    -- Must be SELECT
    IF NOT (upper_query LIKE 'SELECT%') THEN
        RAISE EXCEPTION 'Only SELECT queries are allowed';
    END IF;

    -- Block dangerous keywords (word boundaries to avoid false positives like "deleted")
    IF upper_query ~ '\m(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|GRANT|EXEC)\M' THEN
        RAISE EXCEPTION 'Query contains forbidden keywords';
    END IF;

    -- Execute and return as JSONB array
    EXECUTE 'SELECT COALESCE(jsonb_agg(row_to_json(t)), ''[]''::jsonb) FROM (' || query_text || ') t'
    INTO result;

    RETURN result;
END;
$$;

-- Grant execute to anon role for API access
GRANT EXECUTE ON FUNCTION execute_readonly_query TO anon;
GRANT EXECUTE ON FUNCTION execute_readonly_query TO authenticated;
GRANT EXECUTE ON FUNCTION refresh_analytics_views TO service_role;

-- Grant view access
GRANT ALL ON daily_sales TO service_role;
GRANT ALL ON hourly_sales TO service_role;
GRANT ALL ON product_performance TO service_role;
GRANT ALL ON channel_breakdown TO service_role;

GRANT SELECT ON daily_sales TO anon, authenticated;
GRANT SELECT ON hourly_sales TO anon, authenticated;
GRANT SELECT ON product_performance TO anon, authenticated;
GRANT SELECT ON channel_breakdown TO anon, authenticated;
