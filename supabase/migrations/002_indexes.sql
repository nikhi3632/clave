-- ============================================================
-- Performance Indexes for Analytics Queries
-- ============================================================

-- Orders indexes for time-based queries
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);
CREATE INDEX IF NOT EXISTS idx_orders_location_id ON orders(location_id);
CREATE INDEX IF NOT EXISTS idx_orders_channel ON orders(channel);
CREATE INDEX IF NOT EXISTS idx_orders_source ON orders(source);
CREATE INDEX IF NOT EXISTS idx_orders_location_created ON orders(location_id, created_at);

-- New order indexes for expanded fields
CREATE INDEX IF NOT EXISTS idx_orders_order_status ON orders(order_status);
CREATE INDEX IF NOT EXISTS idx_orders_is_catering ON orders(is_catering) WHERE is_catering = TRUE;
CREATE INDEX IF NOT EXISTS idx_orders_contains_alcohol ON orders(contains_alcohol) WHERE contains_alcohol = TRUE;
CREATE INDEX IF NOT EXISTS idx_orders_payment_type ON orders(payment_type);
CREATE INDEX IF NOT EXISTS idx_orders_revenue_center ON orders(revenue_center);
CREATE INDEX IF NOT EXISTS idx_orders_voided ON orders(voided) WHERE voided = TRUE;
CREATE INDEX IF NOT EXISTS idx_orders_business_date ON orders(business_date);
CREATE INDEX IF NOT EXISTS idx_orders_order_source ON orders(order_source);
CREATE INDEX IF NOT EXISTS idx_orders_refund_status ON orders(refund_status);

-- Order items indexes for product analysis
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product_id ON order_items(product_id);

-- Products index for category queries
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);

-- Location indexes for address-based queries
CREATE INDEX IF NOT EXISTS idx_locations_city ON locations(city);
CREATE INDEX IF NOT EXISTS idx_locations_location_type ON locations(location_type);
