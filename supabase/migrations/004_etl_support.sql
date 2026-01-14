-- ============================================================
-- ETL Support Tables
-- ============================================================
-- Cache tables for LLM-based classification and normalization.

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

DROP POLICY IF EXISTS "Public read access" ON product_category_cache;
DROP POLICY IF EXISTS "Public read access" ON category_review_queue;
DROP POLICY IF EXISTS "Public read access" ON product_name_cache;

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

DROP TRIGGER IF EXISTS update_product_category_cache_updated_at ON product_category_cache;
DROP TRIGGER IF EXISTS update_product_name_cache_updated_at ON product_name_cache;

CREATE TRIGGER update_product_category_cache_updated_at
    BEFORE UPDATE ON product_category_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_product_name_cache_updated_at
    BEFORE UPDATE ON product_name_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- Category Mappings
-- ============================================================
-- User-curated mappings from source categories to canonical forms.
-- Populated via `make review`, not hardcoded.
-- Example: "Beverages" -> "Drinks", "Coffee & Tea" -> "Drinks"

CREATE TABLE IF NOT EXISTS category_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_category TEXT NOT NULL UNIQUE,  -- Original category from POS
    canonical_category TEXT NOT NULL,       -- User-chosen canonical form
    created_by TEXT DEFAULT 'review',       -- 'review', 'manual', 'auto'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE category_mappings ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Public read access" ON category_mappings;
CREATE POLICY "Public read access" ON category_mappings FOR SELECT USING (true);
GRANT ALL ON category_mappings TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON category_mappings TO anon, authenticated;

-- ============================================================
-- Category Merge Queue
-- ============================================================
-- Holds clusters of similar categories for human review.
-- Separate from product review queue for clarity.

CREATE TABLE IF NOT EXISTS category_merge_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_variants TEXT[] NOT NULL,      -- e.g., ['Beverages', 'Drinks', 'Coffee']
    product_counts INTEGER[] NOT NULL,      -- e.g., [5, 12, 3] - products per variant
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'merged', 'skipped')),
    canonical_category TEXT,                -- Set when merged
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE category_merge_queue ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Public read access" ON category_merge_queue;
CREATE POLICY "Public read access" ON category_merge_queue FOR SELECT USING (true);
GRANT ALL ON category_merge_queue TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON category_merge_queue TO anon, authenticated;
