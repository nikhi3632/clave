-- ============================================================
-- All Indexes
-- ============================================================

-- ============================================================
-- Core Table Indexes
-- ============================================================

-- Orders indexes for time-based queries
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);
CREATE INDEX IF NOT EXISTS idx_orders_location_id ON orders(location_id);
CREATE INDEX IF NOT EXISTS idx_orders_channel ON orders(channel);
CREATE INDEX IF NOT EXISTS idx_orders_source ON orders(source);
CREATE INDEX IF NOT EXISTS idx_orders_location_created ON orders(location_id, created_at);

-- Orders indexes for expanded fields
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

-- ============================================================
-- Materialized View Unique Indexes
-- ============================================================

CREATE UNIQUE INDEX IF NOT EXISTS daily_sales_idx
ON daily_sales(location, date, channel, source);

CREATE UNIQUE INDEX IF NOT EXISTS hourly_sales_idx
ON hourly_sales(location, date, hour);

CREATE UNIQUE INDEX IF NOT EXISTS product_perf_idx
ON product_performance(product, location, channel);

CREATE UNIQUE INDEX IF NOT EXISTS product_summary_idx
ON product_summary(product);

CREATE UNIQUE INDEX IF NOT EXISTS channel_breakdown_idx
ON channel_breakdown(location, channel, source);

CREATE UNIQUE INDEX IF NOT EXISTS location_summary_idx
ON location_summary(location);

CREATE UNIQUE INDEX IF NOT EXISTS reconciliation_totals_idx
ON reconciliation_totals(refreshed_at);

-- ============================================================
-- ETL Cache Table Indexes
-- ============================================================

-- Product category cache
CREATE INDEX IF NOT EXISTS idx_product_category_cache_name
ON product_category_cache(product_name);

CREATE INDEX IF NOT EXISTS idx_product_category_cache_review
ON product_category_cache(confidence) WHERE confidence = 'llm';

-- Category review queue
CREATE INDEX IF NOT EXISTS idx_category_review_pending
ON category_review_queue(status) WHERE status = 'pending';

-- Product name cache
CREATE INDEX IF NOT EXISTS idx_product_name_cache_original
ON product_name_cache(original_name);

CREATE INDEX IF NOT EXISTS idx_product_name_cache_canonical
ON product_name_cache(canonical_name);

CREATE INDEX IF NOT EXISTS idx_product_name_cache_review
ON product_name_cache(confidence) WHERE confidence = 'llm';

-- Category mappings
CREATE INDEX IF NOT EXISTS idx_category_mappings_source
ON category_mappings(source_category);

CREATE INDEX IF NOT EXISTS idx_category_mappings_canonical
ON category_mappings(canonical_category);

-- Category merge queue
CREATE INDEX IF NOT EXISTS idx_category_merge_queue_pending
ON category_merge_queue(status) WHERE status = 'pending';
