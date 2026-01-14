-- ============================================================
-- Database Functions
-- ============================================================

-- ============================================================
-- Trigger Function: Auto-update updated_at column
-- ============================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql
SET search_path = public;

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

-- ============================================================
-- Refresh Analytics Views
-- ============================================================

CREATE OR REPLACE FUNCTION refresh_analytics_views()
RETURNS void
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW daily_sales;
    REFRESH MATERIALIZED VIEW hourly_sales;
    REFRESH MATERIALIZED VIEW product_performance;
    REFRESH MATERIALIZED VIEW product_summary;
    REFRESH MATERIALIZED VIEW channel_breakdown;
    REFRESH MATERIALIZED VIEW channel_summary;
    REFRESH MATERIALIZED VIEW source_summary;
    REFRESH MATERIALIZED VIEW location_summary;
    REFRESH MATERIALIZED VIEW reconciliation_totals;
END;
$$;

GRANT EXECUTE ON FUNCTION refresh_analytics_views TO service_role;
