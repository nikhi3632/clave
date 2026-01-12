-- ============================================================
-- Schema Permissions (required after DROP SCHEMA CASCADE)
-- ============================================================

GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO anon, authenticated;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO anon, authenticated;

-- ============================================================
-- Core Tables for Restaurant Analytics
-- ============================================================

-- Locations (4 restaurants)
CREATE TABLE IF NOT EXISTS locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed locations
INSERT INTO locations (name) VALUES
    ('Downtown'),
    ('Airport'),
    ('Mall'),
    ('University')
ON CONFLICT (name) DO NOTHING;

-- Products (normalized from all sources)
CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name TEXT NOT NULL UNIQUE,
    category TEXT,
    original_names TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Orders (unified from all POS systems)
CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('toast', 'doordash', 'square')),
    location_id UUID NOT NULL REFERENCES locations(id),
    channel TEXT NOT NULL CHECK (channel IN ('dine_in', 'pickup', 'delivery')),
    subtotal_cents INTEGER NOT NULL CHECK (subtotal_cents >= 0),
    tax_cents INTEGER NOT NULL DEFAULT 0 CHECK (tax_cents >= 0),
    tip_cents INTEGER NOT NULL DEFAULT 0 CHECK (tip_cents >= 0),
    total_cents INTEGER GENERATED ALWAYS AS (subtotal_cents + tax_cents + tip_cents) STORED,
    created_at TIMESTAMPTZ NOT NULL,
    inserted_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source, external_id)
);

-- Order Items
CREATE TABLE IF NOT EXISTS order_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity >= 1),
    unit_price_cents INTEGER NOT NULL CHECK (unit_price_cents >= 0),
    total_cents INTEGER GENERATED ALWAYS AS (quantity * unit_price_cents) STORED,
    modifiers JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Row Level Security (RLS)
-- ============================================================

ALTER TABLE locations ENABLE ROW LEVEL SECURITY;
ALTER TABLE products ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_items ENABLE ROW LEVEL SECURITY;

-- Public read access for dashboard (idempotent)
DROP POLICY IF EXISTS "Public read access" ON locations;
DROP POLICY IF EXISTS "Public read access" ON products;
DROP POLICY IF EXISTS "Public read access" ON orders;
DROP POLICY IF EXISTS "Public read access" ON order_items;

CREATE POLICY "Public read access" ON locations FOR SELECT USING (true);
CREATE POLICY "Public read access" ON products FOR SELECT USING (true);
CREATE POLICY "Public read access" ON orders FOR SELECT USING (true);
CREATE POLICY "Public read access" ON order_items FOR SELECT USING (true);

-- Grant table access (after tables exist)
GRANT ALL ON locations TO service_role;
GRANT ALL ON products TO service_role;
GRANT ALL ON orders TO service_role;
GRANT ALL ON order_items TO service_role;

GRANT SELECT, INSERT, UPDATE, DELETE ON locations TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON products TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON orders TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON order_items TO anon, authenticated;
