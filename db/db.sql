-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.category_mappings (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  source_category text NOT NULL UNIQUE,
  canonical_category text NOT NULL,
  created_by text DEFAULT 'review'::text,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT category_mappings_pkey PRIMARY KEY (id)
);
CREATE TABLE public.category_merge_queue (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  category_variants ARRAY NOT NULL,
  product_counts ARRAY NOT NULL,
  status text NOT NULL DEFAULT 'pending'::text CHECK (status = ANY (ARRAY['pending'::text, 'merged'::text, 'skipped'::text])),
  canonical_category text,
  reviewed_at timestamp with time zone,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT category_merge_queue_pkey PRIMARY KEY (id)
);
CREATE TABLE public.category_review_queue (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  product_name text NOT NULL UNIQUE,
  source_category text,
  llm_category text NOT NULL,
  confidence_score real NOT NULL,
  reason text,
  status text NOT NULL DEFAULT 'pending'::text CHECK (status = ANY (ARRAY['pending'::text, 'approved'::text, 'rejected'::text, 'custom'::text])),
  final_category text,
  reviewed_at timestamp with time zone,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT category_review_queue_pkey PRIMARY KEY (id)
);
CREATE TABLE public.locations (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  name text NOT NULL UNIQUE,
  street text,
  city text,
  state text,
  zip_code text,
  country text DEFAULT 'US'::text,
  location_type text,
  timezone text DEFAULT 'America/New_York'::text,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT locations_pkey PRIMARY KEY (id)
);
CREATE TABLE public.order_items (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  order_id uuid NOT NULL,
  product_id uuid NOT NULL,
  quantity integer NOT NULL DEFAULT 1 CHECK (quantity >= 1),
  unit_price_cents integer NOT NULL CHECK (unit_price_cents >= 0),
  total_cents integer DEFAULT (quantity * unit_price_cents),
  modifiers jsonb DEFAULT '[]'::jsonb,
  original_name text,
  special_instructions text,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT order_items_pkey PRIMARY KEY (id),
  CONSTRAINT order_items_order_id_fkey FOREIGN KEY (order_id) REFERENCES public.orders(id),
  CONSTRAINT order_items_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id)
);
CREATE TABLE public.orders (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  external_id text NOT NULL,
  source text NOT NULL CHECK (source = ANY (ARRAY['toast'::text, 'doordash'::text, 'square'::text])),
  location_id uuid NOT NULL,
  channel text NOT NULL CHECK (channel = ANY (ARRAY['dine_in'::text, 'pickup'::text, 'delivery'::text])),
  sales_cents integer NOT NULL CHECK (sales_cents >= 0),
  tax_cents integer NOT NULL DEFAULT 0 CHECK (tax_cents >= 0),
  tip_cents integer NOT NULL DEFAULT 0 CHECK (tip_cents >= 0),
  total_cents integer DEFAULT ((sales_cents + tax_cents) + tip_cents),
  delivery_fee_cents integer DEFAULT 0,
  service_fee_cents integer DEFAULT 0,
  commission_cents integer DEFAULT 0,
  merchant_payout_cents integer DEFAULT 0,
  processing_fee_cents integer DEFAULT 0,
  order_status text,
  pickup_time timestamp with time zone,
  delivery_time timestamp with time zone,
  closed_at timestamp with time zone,
  is_catering boolean DEFAULT false,
  contains_alcohol boolean DEFAULT false,
  voided boolean DEFAULT false,
  deleted boolean DEFAULT false,
  refund_status text,
  payment_type text,
  card_type text,
  revenue_center text,
  server_name text,
  check_number text,
  order_source text,
  business_date date,
  delivery_street text,
  delivery_city text,
  delivery_state text,
  delivery_zip text,
  created_at timestamp with time zone NOT NULL,
  inserted_at timestamp with time zone DEFAULT now(),
  CONSTRAINT orders_pkey PRIMARY KEY (id),
  CONSTRAINT orders_location_id_fkey FOREIGN KEY (location_id) REFERENCES public.locations(id)
);
CREATE TABLE public.product_category_cache (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  product_name text NOT NULL UNIQUE,
  category text NOT NULL,
  confidence text NOT NULL DEFAULT 'llm'::text CHECK (confidence = ANY (ARRAY['source'::text, 'llm'::text, 'llm_auto'::text, 'reviewed'::text, 'manual'::text])),
  score real DEFAULT 1.0,
  reason text DEFAULT ''::text,
  source_category text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT product_category_cache_pkey PRIMARY KEY (id)
);
CREATE TABLE public.product_name_cache (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  original_name text NOT NULL UNIQUE,
  canonical_name text NOT NULL,
  confidence text NOT NULL DEFAULT 'llm'::text CHECK (confidence = ANY (ARRAY['exact'::text, 'llm'::text, 'llm_auto'::text, 'reviewed'::text, 'manual'::text])),
  score real DEFAULT 1.0,
  reason text DEFAULT ''::text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT product_name_cache_pkey PRIMARY KEY (id)
);
CREATE TABLE public.products (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  canonical_name text NOT NULL UNIQUE,
  category text,
  original_names ARRAY DEFAULT '{}'::text[],
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT products_pkey PRIMARY KEY (id)
);
