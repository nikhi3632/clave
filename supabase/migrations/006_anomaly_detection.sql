-- ============================================================
-- Phase 2: ETL Anomaly Detection
-- ============================================================
-- Track data quality issues detected during ETL processing.

CREATE TABLE IF NOT EXISTS etl_anomalies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id TEXT NOT NULL,  -- ETL run identifier
    source TEXT NOT NULL,  -- toast, doordash, square
    severity TEXT NOT NULL DEFAULT 'warning'
        CHECK (severity IN ('info', 'warning', 'error')),
    anomaly_type TEXT NOT NULL,
    description TEXT NOT NULL,
    -- Context for debugging
    external_id TEXT,  -- Order/product ID from source
    product_name TEXT,
    location TEXT,
    -- Numeric context
    expected_value NUMERIC,
    actual_value NUMERIC,
    -- Raw data for investigation
    raw_data JSONB,
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for querying by run
CREATE INDEX IF NOT EXISTS idx_etl_anomalies_run
ON etl_anomalies(run_id, created_at DESC);

-- Index for querying by type/severity
CREATE INDEX IF NOT EXISTS idx_etl_anomalies_type
ON etl_anomalies(anomaly_type, severity);

-- Index for recent anomalies
CREATE INDEX IF NOT EXISTS idx_etl_anomalies_recent
ON etl_anomalies(created_at DESC);

-- ============================================================
-- Anomaly Summary View
-- ============================================================
-- Quick overview of anomalies by type

CREATE OR REPLACE VIEW anomaly_summary
WITH (security_invoker = true)
AS
SELECT
    anomaly_type,
    severity,
    COUNT(*) as count,
    MAX(created_at) as last_seen,
    COUNT(DISTINCT run_id) as affected_runs
FROM etl_anomalies
GROUP BY anomaly_type, severity
ORDER BY count DESC;

-- ============================================================
-- RLS and Grants
-- ============================================================

ALTER TABLE etl_anomalies ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Public read access" ON etl_anomalies;
CREATE POLICY "Public read access" ON etl_anomalies FOR SELECT USING (true);

GRANT ALL ON etl_anomalies TO service_role;
GRANT SELECT ON etl_anomalies TO anon, authenticated;
GRANT SELECT ON anomaly_summary TO anon, authenticated;
