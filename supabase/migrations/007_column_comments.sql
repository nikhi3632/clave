-- ============================================================
-- Column Comments for LLM Context
-- ============================================================
-- These comments are queried dynamically to build LLM prompts.
-- Format: Brief description. Values: x, y, z. Synonyms: "user term" -> value. Notes: special handling.

-- orders table
COMMENT ON COLUMN orders.source IS 'POS system that created the order. Synonyms: "pos" -> check all sources.';
COMMENT ON COLUMN orders.channel IS 'How the order was placed. Synonyms: "takeout"/"to-go" -> pickup, "in-store"/"eat-in"/"dine in" -> dine_in.';
COMMENT ON COLUMN orders.payment_type IS 'Normalized payment method. UNKNOWN = DoorDash orders (payment not exposed to merchants). Synonyms: "credit card"/"debit" -> CARD, "apple pay"/"google pay" -> WALLET.';
COMMENT ON COLUMN orders.voided IS 'Order was voided. EXCLUDE from revenue: WHERE voided = FALSE.';
COMMENT ON COLUMN orders.deleted IS 'Order was deleted. EXCLUDE from revenue: WHERE deleted = FALSE.';
COMMENT ON COLUMN orders.refund_status IS 'Refund state. Values: NONE, PARTIAL, FULL.';
COMMENT ON COLUMN orders.is_catering IS 'Large/catering order. Filter: WHERE is_catering = TRUE.';
COMMENT ON COLUMN orders.contains_alcohol IS 'Order includes alcohol. Filter: WHERE contains_alcohol = TRUE.';
COMMENT ON COLUMN orders.total_cents IS 'All monetary values are in CENTS. Divide by 100.0 for dollars.';
COMMENT ON COLUMN orders.delivery_fee_cents IS 'DoorDash delivery fee charged to customer.';
COMMENT ON COLUMN orders.service_fee_cents IS 'Platform service fee.';
COMMENT ON COLUMN orders.commission_cents IS 'Platform commission taken from merchant.';
COMMENT ON COLUMN orders.merchant_payout_cents IS 'Actual amount paid to restaurant after fees.';
COMMENT ON COLUMN orders.processing_fee_cents IS 'Payment processing fee (mainly Toast).';
COMMENT ON COLUMN orders.server_name IS 'Employee who took the order (Toast only).';
COMMENT ON COLUMN orders.order_source IS 'Origin of order. Values: POS, ONLINE, THIRD_PARTY.';

-- products table
COMMENT ON COLUMN products.category IS 'Product category. Synonyms: "beverages"/"drinks" -> Drinks, "main courses"/"mains"/"entree" -> Entrees, "apps" -> Appetizers.';
COMMENT ON COLUMN products.canonical_name IS 'Normalized product name used for matching across POS sources.';

-- locations table
COMMENT ON COLUMN locations.location_type IS 'Type of venue. Can query by type instead of name.';
COMMENT ON COLUMN locations.name IS 'Location display name. Query with ILIKE for partial matches.';

-- order_items table
COMMENT ON COLUMN order_items.original_name IS 'Item name before normalization. Useful for debugging product matching.';
COMMENT ON COLUMN order_items.special_instructions IS 'Customer notes like "no mayo", "extra cheese".';

-- Materialized views
COMMENT ON MATERIALIZED VIEW daily_sales IS 'Pre-aggregated daily metrics by location/channel/source. USE THIS for daily trends.';
COMMENT ON MATERIALIZED VIEW hourly_sales IS 'Pre-aggregated hourly patterns. USE THIS for time-of-day analysis.';
COMMENT ON MATERIALIZED VIEW product_performance IS 'Pre-aggregated product metrics. USE THIS for product analysis.';
COMMENT ON MATERIALIZED VIEW channel_breakdown IS 'Pre-aggregated channel comparison. USE THIS for channel analysis.';
