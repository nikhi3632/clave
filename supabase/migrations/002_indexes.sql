-- ============================================================
-- Performance Indexes for Analytics Queries
-- ============================================================

-- Orders indexes for time-based queries
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);
CREATE INDEX IF NOT EXISTS idx_orders_location_id ON orders(location_id);
CREATE INDEX IF NOT EXISTS idx_orders_channel ON orders(channel);
CREATE INDEX IF NOT EXISTS idx_orders_source ON orders(source);
CREATE INDEX IF NOT EXISTS idx_orders_location_created ON orders(location_id, created_at);

-- Order items indexes for product analysis
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product_id ON order_items(product_id);

-- Products index for category queries
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
