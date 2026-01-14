-- ============================================================
-- Rich Schema Comments for Dynamic LLM Prompt Generation
-- ============================================================
-- These structured comments enable the LLM to understand the schema
-- without hardcoding view/table/column names in the prompt.
--
-- Format:
-- - Views: PURPOSE:, DIMENSIONS:, METRICS:, USE FOR:
-- - Columns: Description. SYNONYMS: term1, term2. NOTE: special info.
-- - Dimension tables: DIMENSION:, DISPLAY_COLUMN:, FILTER_PATTERN:
-- - Utility views: INTERNAL: description

-- ============================================================
-- Schema-Level Conventions
-- ============================================================

COMMENT ON SCHEMA public IS
'NAMING CONVENTIONS:
- All monetary values end in _cents (stored as integers)
- sales_cents = net sales (excludes tax and tips)
- total_cents = total collected (sales + tax + tips)
- Analytics views use denormalized names: location, product, date
- Base tables use FK references: location_id, product_id, created_at
CURRENCY: USD, stored in cents, divide by 100.0 for dollars, round to 2 decimals';

-- ============================================================
-- Dimension Tables
-- ============================================================

COMMENT ON TABLE locations IS
'DIMENSION: location
DISPLAY_COLUMN: name
FILTER_PATTERN: JOIN locations l ON {alias}.location_id = l.id WHERE l.name = :filter_value
VALUES_QUERY: SELECT DISTINCT name FROM locations ORDER BY name';

COMMENT ON TABLE products IS
'DIMENSION: product, category
DISPLAY_COLUMNS: canonical_name (for product), category (for category)
FILTER_PATTERN_product: JOIN products p ON {alias}.product_id = p.id WHERE p.canonical_name = :filter_value
FILTER_PATTERN_category: JOIN products p ON {alias}.product_id = p.id WHERE p.category = :filter_value
VALUES_QUERY_product: SELECT DISTINCT canonical_name FROM products ORDER BY canonical_name
VALUES_QUERY_category: SELECT DISTINCT category FROM products WHERE category IS NOT NULL ORDER BY category';

-- ============================================================
-- Fact Tables
-- ============================================================

COMMENT ON TABLE orders IS
'Primary fact table for orders. Contains one row per order.
FILTER_PATTERN_source: WHERE source = :filter_value
FILTER_PATTERN_channel: WHERE channel = :filter_value
FILTER_PATTERN_date: WHERE DATE(created_at) = :filter_value::date
NOTE: For revenue metrics, use subtotal_cents (equivalent to revenue_cents in views)';

COMMENT ON TABLE order_items IS
'Line items within orders. Join to orders via order_id, to products via product_id.
NOTE: total_cents here is item-level (quantity * unit_price), not order-level';

-- ============================================================
-- Analytics Views - These are exposed to the LLM
-- ============================================================

COMMENT ON MATERIALIZED VIEW daily_sales IS
'Analytics view for daily sales trends.
PURPOSE: Time-series analysis by day, location, channel, and source
DIMENSIONS: date, location, channel, source
METRICS: sales_cents, tax_cents, tip_cents, total_cents, order_count, avg_order_cents
USE FOR: daily sales trends, day-over-day comparisons, sales by date';

COMMENT ON MATERIALIZED VIEW hourly_sales IS
'Analytics view for hourly patterns.
PURPOSE: Time-of-day analysis and peak hour identification
DIMENSIONS: date, location, hour, day_name, day_of_week
METRICS: sales_cents, tax_cents, tip_cents, total_cents, order_count
USE FOR: hourly patterns, peak hours, busiest times, time-of-day analysis';

COMMENT ON MATERIALIZED VIEW product_performance IS
'Analytics view for product metrics by location and channel.
PURPOSE: Product performance analysis with location/channel breakdown
DIMENSIONS: product, category, location, channel
METRICS: sales_cents, units_sold, order_count, avg_price_cents
USE FOR: product sales, top products, product comparison by location';

COMMENT ON MATERIALIZED VIEW product_summary IS
'Analytics view for product metrics aggregated across all locations.
PURPOSE: Overall product performance without location breakdown
DIMENSIONS: product, category
METRICS: total_sales_cents, total_units, total_orders, avg_price_cents
USE FOR: top selling products overall, product rankings, category performance';

COMMENT ON MATERIALIZED VIEW channel_breakdown IS
'Analytics view for channel and source comparison.
PURPOSE: Compare performance across order channels and POS sources
DIMENSIONS: location, channel, source
METRICS: sales_cents, tax_cents, tip_cents, total_cents, order_count, avg_order_cents
USE FOR: channel comparison, dine-in vs delivery vs pickup, source comparison';

COMMENT ON MATERIALIZED VIEW location_summary IS
'Analytics view for location performance.
PURPOSE: Compare metrics across locations (aggregated across all channels/sources)
DIMENSIONS: location
METRICS: sales_cents, tax_cents, tip_cents, total_cents, order_count, avg_order_cents
USE FOR: location comparison, location rankings, sales by location';

-- ============================================================
-- Internal Views - NOT exposed to LLM
-- ============================================================

COMMENT ON MATERIALIZED VIEW reconciliation_totals IS
'INTERNAL: Data quality reconciliation view for ETL verification.
NOT FOR ANALYTICS QUERIES - use daily_sales or location_summary instead.
Contains aggregate counts and data quality metrics for debugging.';

-- ============================================================
-- Column Comments with Synonyms
-- ============================================================

-- Analytics view columns (these are what the LLM will query)
COMMENT ON COLUMN daily_sales.sales_cents IS
'Net sales in cents (food/drink sales, excludes tax and tips).
SYNONYMS: sales, revenue, net sales, net revenue, food sales
EQUIVALENT: orders.sales_cents';

COMMENT ON COLUMN daily_sales.total_cents IS
'Total collected in cents (includes tax and tips).
SYNONYMS: total collected, proceeds
FORMULA: sales_cents + tax_cents + tip_cents';

COMMENT ON COLUMN daily_sales.tax_cents IS
'Tax collected in cents.
SYNONYMS: tax, sales tax, taxes';

COMMENT ON COLUMN daily_sales.tip_cents IS
'Tips collected in cents.
SYNONYMS: tips, gratuity, gratuities';

COMMENT ON COLUMN daily_sales.order_count IS
'Number of orders.
SYNONYMS: orders, order count, number of orders, transactions';

COMMENT ON COLUMN daily_sales.avg_order_cents IS
'Average order value in cents (based on subtotal).
SYNONYMS: average order, avg order, AOV, average ticket';

COMMENT ON COLUMN daily_sales.date IS
'Order date (DATE type).
SYNONYMS: day, date';

COMMENT ON COLUMN daily_sales.location IS
'Location name (denormalized from locations.name).
SYNONYMS: store, restaurant, branch, site';

COMMENT ON COLUMN daily_sales.channel IS
'Order channel: dine_in, pickup, or delivery.
SYNONYMS: order type, service type
MAPPING: takeout/to-go = pickup, in-store/eat-in = dine_in';

COMMENT ON COLUMN daily_sales.source IS
'POS system: toast, doordash, or square.
SYNONYMS: pos, point of sale, system';

-- Location summary columns
COMMENT ON COLUMN location_summary.sales_cents IS
'Net sales in cents (excludes tax and tips).
SYNONYMS: sales, revenue, net sales';

COMMENT ON COLUMN location_summary.total_cents IS
'Total collected in cents (includes tax and tips).
SYNONYMS: total collected, proceeds';

COMMENT ON COLUMN location_summary.location IS
'Location name.
SYNONYMS: store, restaurant, branch';

-- Product performance columns
COMMENT ON COLUMN product_performance.sales_cents IS
'Net sales from this product in cents.
SYNONYMS: sales, revenue, product sales, product revenue';

COMMENT ON COLUMN product_performance.units_sold IS
'Total quantity sold.
SYNONYMS: quantity, units, items sold, volume';

COMMENT ON COLUMN product_performance.product IS
'Product name (normalized canonical_name).
SYNONYMS: item, menu item, product name';

COMMENT ON COLUMN product_performance.category IS
'Product category.
SYNONYMS: type, product type, category
MAPPING: beverages/drinks = Drinks, main courses/mains/entree = Entrees, apps = Appetizers';

-- Product summary columns
COMMENT ON COLUMN product_summary.total_sales_cents IS
'Total sales from this product across all locations.
SYNONYMS: sales, revenue, product sales';

COMMENT ON COLUMN product_summary.total_units IS
'Total quantity sold across all locations.
SYNONYMS: quantity, units, items sold';

-- Channel breakdown columns
COMMENT ON COLUMN channel_breakdown.sales_cents IS
'Net sales in cents for this channel.
SYNONYMS: sales, revenue, channel sales';

COMMENT ON COLUMN channel_breakdown.total_cents IS
'Total collected in cents for this channel.
SYNONYMS: total collected, proceeds';

-- Hourly sales columns
COMMENT ON COLUMN hourly_sales.hour IS
'Hour of day (0-23).
SYNONYMS: time, hour of day';

COMMENT ON COLUMN hourly_sales.day_name IS
'Day of week name (Monday, Tuesday, etc.).
SYNONYMS: day, weekday';

COMMENT ON COLUMN hourly_sales.sales_cents IS
'Net sales for this hour.
SYNONYMS: sales, revenue, hourly sales';

-- ============================================================
-- Base table column comments (for drill-down SQL generation)
-- ============================================================

COMMENT ON COLUMN orders.sales_cents IS
'Order sales in cents (net sales, excludes tax and tips).
SYNONYMS: sales, revenue, net
NOTE: Use this in summarySQL - equivalent to sales_cents in views';

COMMENT ON COLUMN orders.total_cents IS
'Order total in cents (sales + tax + tips). Generated column.
SYNONYMS: total collected, proceeds';

COMMENT ON COLUMN orders.tax_cents IS
'Tax amount in cents.';

COMMENT ON COLUMN orders.tip_cents IS
'Tip amount in cents.';

COMMENT ON COLUMN orders.source IS
'POS system: toast, doordash, or square.';

COMMENT ON COLUMN orders.channel IS
'Order channel: dine_in, pickup, or delivery.';

COMMENT ON COLUMN orders.created_at IS
'Order timestamp. Use DATE(created_at) for date filtering.';

COMMENT ON COLUMN orders.location_id IS
'Foreign key to locations table. Join: locations l ON orders.location_id = l.id';

COMMENT ON COLUMN order_items.product_id IS
'Foreign key to products table. Join: products p ON order_items.product_id = p.id';

COMMENT ON COLUMN order_items.order_id IS
'Foreign key to orders table. Join: orders o ON order_items.order_id = o.id';

COMMENT ON COLUMN order_items.quantity IS
'Number of units ordered.';

COMMENT ON COLUMN order_items.total_cents IS
'Line item total (quantity * unit_price_cents). Item-level, not order-level.';

COMMENT ON COLUMN products.canonical_name IS
'Normalized product name for matching across POS sources.
SYNONYMS: product, item, product name';

COMMENT ON COLUMN products.category IS
'Product category.
SYNONYMS: type, product type
MAPPING: beverages/drinks = Drinks, mains/entree = Entrees';

COMMENT ON COLUMN locations.name IS
'Location display name.
SYNONYMS: location, store, restaurant';
