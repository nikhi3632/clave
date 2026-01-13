-- ============================================================
-- Product Name Cache for LLM-based Normalization
-- ============================================================
-- Maps original product names to canonical names
-- e.g., "Lg Coke" -> "Coca-Cola", "Griled Chiken" -> "Grilled Chicken"

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

-- Index for fast lookups by original name
CREATE INDEX IF NOT EXISTS idx_product_name_cache_original
ON product_name_cache(original_name);

-- Index for finding all variants of a canonical name
CREATE INDEX IF NOT EXISTS idx_product_name_cache_canonical
ON product_name_cache(canonical_name);

-- Index for items that need review
CREATE INDEX IF NOT EXISTS idx_product_name_cache_review
ON product_name_cache(confidence) WHERE confidence = 'llm';

-- ============================================================
-- RLS and Grants
-- ============================================================

ALTER TABLE product_name_cache ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Public read access" ON product_name_cache;
CREATE POLICY "Public read access" ON product_name_cache FOR SELECT USING (true);

GRANT ALL ON product_name_cache TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON product_name_cache TO anon, authenticated;

-- ============================================================
-- Trigger for updated_at
-- ============================================================

DROP TRIGGER IF EXISTS update_product_name_cache_updated_at ON product_name_cache;
CREATE TRIGGER update_product_name_cache_updated_at
    BEFORE UPDATE ON product_name_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
