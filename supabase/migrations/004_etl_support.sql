-- ============================================================
-- ETL Support Tables
-- ============================================================
-- Cache tables for LLM-based classification and normalization.
-- Indexes are created in 002_indexes.sql.

-- ============================================================
-- Product Category Cache
-- ============================================================

CREATE TABLE IF NOT EXISTS product_category_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    confidence TEXT NOT NULL DEFAULT 'llm'
        CHECK (confidence IN ('source', 'llm', 'llm_auto', 'reviewed', 'manual')),
    score REAL DEFAULT 1.0,  -- 0.0-1.0 confidence score
    reason TEXT DEFAULT '',  -- LLM explanation
    source_category TEXT,    -- Original category from POS (for audit)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Category Review Queue
-- ============================================================

CREATE TABLE IF NOT EXISTS category_review_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_name TEXT NOT NULL,
    source_category TEXT,
    llm_category TEXT NOT NULL,
    confidence_score REAL NOT NULL,
    reason TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected', 'custom')),
    final_category TEXT,  -- Set when reviewed
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(product_name)
);

-- ============================================================
-- Product Name Cache
-- ============================================================

CREATE TABLE IF NOT EXISTS product_name_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_name TEXT NOT NULL UNIQUE,
    canonical_name TEXT NOT NULL,
    confidence TEXT NOT NULL DEFAULT 'llm'
        CHECK (confidence IN ('exact', 'llm', 'llm_auto', 'reviewed', 'manual')),
    score REAL DEFAULT 1.0,  -- 0.0-1.0 confidence score
    reason TEXT DEFAULT '',  -- LLM explanation for the mapping
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Row Level Security
-- ============================================================

ALTER TABLE product_category_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE category_review_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE product_name_cache ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read access" ON product_category_cache FOR SELECT USING (true);
CREATE POLICY "Public read access" ON category_review_queue FOR SELECT USING (true);
CREATE POLICY "Public read access" ON product_name_cache FOR SELECT USING (true);

-- ============================================================
-- Grants
-- ============================================================

GRANT ALL ON product_category_cache TO service_role;
GRANT ALL ON category_review_queue TO service_role;
GRANT ALL ON product_name_cache TO service_role;

GRANT SELECT, INSERT, UPDATE, DELETE ON product_category_cache TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON category_review_queue TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON product_name_cache TO anon, authenticated;

-- ============================================================
-- Triggers
-- ============================================================

CREATE TRIGGER update_product_category_cache_updated_at
    BEFORE UPDATE ON product_category_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_product_name_cache_updated_at
    BEFORE UPDATE ON product_name_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
