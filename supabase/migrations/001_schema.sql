-- ============================================================
-- Core Schema: Tables, Constraints, RLS, and Grants
-- ============================================================

-- Schema Permissions
GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO anon, authenticated;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO anon, authenticated;

-- ============================================================
-- Core Tables
-- ============================================================

CREATE TABLE IF NOT EXISTS locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    street TEXT,
    city TEXT,
    state TEXT,
    zip_code TEXT,
    country TEXT DEFAULT 'US',
    location_type TEXT,
    timezone TEXT DEFAULT 'America/New_York',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name TEXT NOT NULL UNIQUE,
    category TEXT,
    original_names TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('toast', 'doordash', 'square')),
    location_id UUID NOT NULL REFERENCES locations(id),
    channel TEXT NOT NULL CHECK (channel IN ('dine_in', 'pickup', 'delivery')),
    sales_cents INTEGER NOT NULL CHECK (sales_cents >= 0),
    tax_cents INTEGER NOT NULL DEFAULT 0 CHECK (tax_cents >= 0),
    tip_cents INTEGER NOT NULL DEFAULT 0 CHECK (tip_cents >= 0),
    total_cents INTEGER GENERATED ALWAYS AS (sales_cents + tax_cents + tip_cents) STORED,
    delivery_fee_cents INTEGER DEFAULT 0,
    service_fee_cents INTEGER DEFAULT 0,
    commission_cents INTEGER DEFAULT 0,
    merchant_payout_cents INTEGER DEFAULT 0,
    processing_fee_cents INTEGER DEFAULT 0,
    order_status TEXT,
    pickup_time TIMESTAMPTZ,
    delivery_time TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    is_catering BOOLEAN DEFAULT FALSE,
    contains_alcohol BOOLEAN DEFAULT FALSE,
    voided BOOLEAN DEFAULT FALSE,
    deleted BOOLEAN DEFAULT FALSE,
    refund_status TEXT,
    payment_type TEXT,
    card_type TEXT,
    revenue_center TEXT,
    server_name TEXT,
    check_number TEXT,
    order_source TEXT,
    business_date DATE,
    delivery_street TEXT,
    delivery_city TEXT,
    delivery_state TEXT,
    delivery_zip TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    inserted_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source, external_id)
);

CREATE TABLE IF NOT EXISTS order_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity >= 1),
    unit_price_cents INTEGER NOT NULL CHECK (unit_price_cents >= 0),
    total_cents INTEGER GENERATED ALWAYS AS (quantity * unit_price_cents) STORED,
    modifiers JSONB DEFAULT '[]',
    original_name TEXT,
    special_instructions TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Row Level Security
-- ============================================================

ALTER TABLE locations ENABLE ROW LEVEL SECURITY;
ALTER TABLE products ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_items ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read access" ON locations FOR SELECT USING (true);
CREATE POLICY "Public read access" ON products FOR SELECT USING (true);
CREATE POLICY "Public read access" ON orders FOR SELECT USING (true);
CREATE POLICY "Public read access" ON order_items FOR SELECT USING (true);

-- ============================================================
-- Grants
-- ============================================================

GRANT ALL ON locations TO service_role;
GRANT ALL ON products TO service_role;
GRANT ALL ON orders TO service_role;
GRANT ALL ON order_items TO service_role;

GRANT SELECT, INSERT, UPDATE, DELETE ON locations TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON products TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON orders TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON order_items TO anon, authenticated;
