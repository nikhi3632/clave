-- ============================================================
-- Product Category Cache for LLM Classification
-- ============================================================

-- Cache table for LLM-inferred categories
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

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_product_category_cache_name
ON product_category_cache(product_name);

-- Index for finding items that need review
CREATE INDEX IF NOT EXISTS idx_product_category_cache_review
ON product_category_cache(confidence) WHERE confidence = 'llm';

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

-- Index for pending reviews
CREATE INDEX IF NOT EXISTS idx_category_review_pending
ON category_review_queue(status) WHERE status = 'pending';

-- ============================================================
-- RLS and Grants
-- ============================================================

ALTER TABLE product_category_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE category_review_queue ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Public read access" ON product_category_cache;
DROP POLICY IF EXISTS "Public read access" ON category_review_queue;

CREATE POLICY "Public read access" ON product_category_cache FOR SELECT USING (true);
CREATE POLICY "Public read access" ON category_review_queue FOR SELECT USING (true);

GRANT ALL ON product_category_cache TO service_role;
GRANT ALL ON category_review_queue TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON product_category_cache TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON category_review_queue TO anon, authenticated;

-- ============================================================
-- Trigger for updated_at
-- ============================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql
SET search_path = public;

DROP TRIGGER IF EXISTS update_product_category_cache_updated_at ON product_category_cache;
CREATE TRIGGER update_product_category_cache_updated_at
    BEFORE UPDATE ON product_category_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
