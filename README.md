# Clave Restaurant Analytics Dashboard

A natural language analytics dashboard that consolidates messy restaurant data from multiple POS sources (Toast, DoorDash, Square) into a unified schema, normalizes product names and categories using LLM-powered classification, and generates dynamic visualizations from plain English queries.

> 🚀 **[Live Demo](https://clave-opal.vercel.app/)** · **[API Docs](https://clave-production-8c73.up.railway.app/docs)**

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Architecture Overview](#architecture-overview)
3. [Data Cleaning & Normalization](#data-cleaning--normalization)
4. [Database Schema Design](#database-schema-design)
5. [AI Integration](#ai-integration)
6. [Dashboard Features](#dashboard-features)
7. [Solutions to Edge Cases](#solutions-to-edge-cases)
8. [Technical Decisions & Tradeoffs](#technical-decisions--tradeoffs)
9. [What I'd Improve With More Time](#what-id-improve-with-more-time)
10. [Project Structure](#project-structure)

---

## Quick Start

### Prerequisites

- [Docker & Docker Compose](https://docs.docker.com/get-docker/)
- Make (pre-installed on macOS/Linux, [install on Windows](https://gnuwin32.sourceforge.net/packages/make.htm))
- A Supabase project ([supabase.com](https://supabase.com))
- Anthropic API key ([console.anthropic.com](https://console.anthropic.com))

### 1. Clone & Configure

```bash
git clone https://github.com/nikhi3632/clave.git
cd clave
cp .env.example .env
```

### 2. Set Up Supabase

1. Create a project at [supabase.com](https://supabase.com)
2. Get credentials from **Settings > API**:
   - Project URL → `SUPABASE_URL`
   - `anon` key → `SUPABASE_ANON_KEY`
   - `service_role` key → `SUPABASE_SERVICE_KEY`
3. Get connection string from **Settings > Database** → `DATABASE_URL`

### 3. Configure .env

```bash
# .env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key
DATABASE_URL=postgresql://postgres:password@db.your-project.supabase.co:5432/postgres
ANTHROPIC_API_KEY=sk-ant-...
```

### 4. Run

```bash
make setup    # Run database migrations
docker compose run --rm seed python -m etl   # Run ETL pipeline
make up       # Start the application
```

### 5. Access

- **Dashboard**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs

### Available Commands

| Command | Description |
|---------|-------------|
| `make up` | Start all services (API + Frontend) |
| `make down` | Stop all services |
| `make reset` | Drop all tables, re-run migrations |
| `make review` | Interactive CLI: review LLM suggestions, browse/edit products |
| `make review-stats` | Show classification statistics |
| `make build` | Rebuild Docker containers |
| `make logs` | View container logs |
| `make lint` | Run ESLint (app) + Ruff (api/etl) |
| `make typecheck` | TypeScript type checking |

---

## Architecture Overview

```mermaid
flowchart TB
    subgraph Frontend["🖥️ Frontend (Next.js 15)"]
        QI[QueryInput + Examples]
        Charts[Charts: Bar/Line/Pie/Table/Metric]
        Drill[DrillDown Modal]
        DQ[DataQuality Modal]
    end

    subgraph API["⚡ API (FastAPI)"]
        Query["POST /api/query<br/>• NL → SQL<br/>• Chart selection<br/>• Retry on error"]
        DrillAPI["GET /api/drill-down<br/>• Filter by dimension<br/>• Custom summarySQL"]
        LLM["LLM Service (Claude)<br/>• Schema introspection<br/>• Date range awareness<br/>• Structured JSON response"]
        DB["Database Service<br/>• SQL validation (RPC)<br/>• Dangerous pattern blocking<br/>• Connection retry"]
    end

    subgraph Supabase["🗄️ Supabase (PostgreSQL)"]
        Core["Core Tables<br/>locations │ products │ orders │ order_items"]
        Views["Materialized Views<br/>daily_sales │ hourly_sales │ product_performance<br/>channel_summary │ source_summary │ location_summary"]
        ETLTables["ETL Support Tables<br/>product_name_cache │ product_category_cache<br/>category_review_queue │ category_mappings"]
    end

    subgraph ETL["🔄 ETL Pipeline (Python)"]
        Extract["Extract<br/>Toast, DoorDash, Square"]
        Transform["Transform<br/>LLM Classifiers"]
        Load["Load → Audit → Refresh Views"]
        Cache["Caching Layer<br/>Never re-calls LLM for cached items"]
        Review["Review System (CLI)<br/>Human-in-the-loop approval"]
    end

    QI --> Query
    Charts --> Drill
    Query --> LLM --> DB
    DrillAPI --> DB
    DB --> Supabase
    ETL --> Supabase
    Extract --> Transform --> Load
    Transform --> Cache
```

### Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| Frontend | Next.js 15, TypeScript, Tailwind | Dashboard UI |
| Charts | Recharts | Bar, Line, Pie, Table, Metric views |
| API | FastAPI (Python 3.13) | Query processing, LLM integration |
| Database | Supabase (PostgreSQL) | Storage, materialized views |
| AI | Claude (Anthropic) | NL→SQL, product classification |
| ETL | Python + RapidFuzz | Extraction, normalization, loading |
| Infra | Docker Compose, GitHub Actions | Development, CI/CD |

---

## Data Cleaning & Normalization

### The Challenge

Six JSON files from three POS systems with real-world messiness:

| Issue | Examples |
|-------|----------|
| **Typos** | "Griled Chiken", "expresso", "coffe", "Appitizers" |
| **Inconsistent naming** | "Hash Browns" vs "Hashbrowns" |
| **Emoji categories** | "🍔 Burgers" vs "Burgers" vs "BURGERS" |
| **Baked-in variations** | "Churros 12pcs" vs "Churros" |
| **Format differences** | "Lg Coke" vs "Large Coca-Cola" vs "Soft Drink" |
| **Semantic ambiguity** | "Margarita" (cocktail) vs "Margherita Pizza" |

### Solution: 4-Layer Normalization Pipeline

```mermaid
flowchart TB
    Input["📥 Input: 'Lg Coke' from Toast POS"]

    subgraph L1["Layer 1: LLM Cache Check"]
        Cache{"In product_name_cache?"}
        CacheHit["✓ Use cached canonical name"]
        CacheMiss["Continue to Layer 2"]
    end

    subgraph L2["Layer 2: Fuzzy Matching"]
        Fuzzy["1. Exact match (lowercase)<br/>2. Phonetic match (ph→f, ck→k)<br/>3. RapidFuzz scoring<br/>4. Threshold ≥ 70%"]
    end

    subgraph L3["Layer 3: LLM Batch Normalization"]
        LLM["Claude (batches of 30):<br/>• Fix typos (Griled → Grilled)<br/>• Expand abbreviations (Lg → Large)<br/>• Remove quantities (12pcs → base)<br/>• Split if fuzzy wrongly grouped"]
    end

    subgraph L4["Layer 4: Category Classification"]
        Cat["Priority: User mappings → Exact match → LLM"]
        Conf{"Confidence?"}
        High["≥90%: Auto-approve"]
        Med["70-90%: Flag for review"]
        Low["<70%: Require human decision"]
    end

    Output["📤 Output: canonical_name='Coca-Cola'<br/>category='Beverages'<br/>original_names=['Lg Coke', 'Large Coca-Cola']"]

    Input --> Cache
    Cache -->|Yes| CacheHit --> Output
    Cache -->|No| CacheMiss --> Fuzzy
    Fuzzy --> LLM
    LLM --> Cat --> Conf
    Conf -->|High| High --> Output
    Conf -->|Medium| Med --> Output
    Conf -->|Low| Low --> Output
```

**Why LLM Cache First?** Prevents fuzzy matcher from wrongly grouping semantically different items (e.g., "Margarita" cocktail ≠ "Margherita Pizza").

### Category Cleaning

```python
def clean_category(category: str) -> str:
    # 1. Remove emojis: "🍔 Burgers" → "Burgers"
    cleaned = remove_unicode_emojis(category)

    # 2. Handle combined: "Sides & Appetizers" → normalize each part
    if " & " in category or " and " in category:
        parts = split_and_normalize_each(category)
        return " & ".join(parts)

    # 3. Fix typos via phonetic/fuzzy matching
    match = category_matcher.match(category)

    # 4. Title case: "BURGERS" → "Burgers"
    return match.matched.title()
```

### Human-in-the-Loop Review

When LLM confidence is below threshold or disagrees with source:

```bash
$ make review

============================================================
PENDING REVIEW: 2 items
============================================================
1. Lobster Roll
   Source: Seafood
   LLM:    Sandwiches (80% confidence)
   Reason: Despite source saying Seafood, a lobster roll
           is served on a roll/bun making it a sandwich

2. Shrimp Scampi
   Source: Seafood
   LLM:    Entrees (80% confidence)
   Reason: This is typically served as a main course dish

Review pending items? [y/n]: y

──────────────────────────────────────────────────────────
Product: Lobster Roll
Source said: Seafood
LLM says: Sandwiches (80%)
──────────────────────────────────────────────────────────

Options:
  [a] Approve LLM category
  [r] Revert to source category
  [1-14] Set to known category:
      1. Appetizers
      2. Beverages
      ...
  [c] Enter custom category
  [s] Skip
  [q] Quit

Choice: a
  ✓ Approved: Sandwiches

Browse all products to edit categories? [y/n]: y

============================================================
ALL PRODUCTS BY CATEGORY (77 total)
============================================================
Appetizers (10):
  1. Bruschetta
  2. Buffalo Wings
  ...

Product #: 45
──────────────────────────────────────────────────────────
Product: Prime Rib
Current: Entrees
──────────────────────────────────────────────────────────
[1-14] Choose category or [c] custom:

Choice: 12
  ✓ Changed to: Steaks
```

**Key feature**: Reviewed decisions are **never overwritten** by subsequent ETL runs. The `category_review_queue` tracks status (pending/approved/rejected/custom) and the loader respects completed reviews.

### Caching Strategy

| Cache Table | Key | Value | Purpose |
|-------------|-----|-------|---------|
| `product_name_cache` | original_name | canonical_name, confidence | Avoid re-normalizing known products |
| `product_category_cache` | product_name | category, confidence, source_category | Avoid re-classifying known products |
| `category_mappings` | source_category | canonical_category | User-curated overrides |
| `category_review_queue` | product_name | status, final_category | Track human decisions |

**Result**: Re-running ETL only calls LLM for genuinely new products. Existing products use cached results.

### Post-ETL Audit

After loading, the audit system finds similar categories for potential merging:

```python
# In audit.py
def find_similar_categories():
    """Find categories that might be duplicates."""
    # Uses multiple similarity methods:
    # - Fuzzy ratio >= 70
    # - Substring containment
    # - Partial ratio
    # - Token sort ratio

    # Creates entries in category_merge_queue for human review
```

---

## Database Schema Design

> 📄 **Full schema**: [`db/db.sql`](db/db.sql) — Complete table definitions with constraints and CHECK clauses

### Core Tables

![Database Schema](db/schema.png)

| Table | Purpose |
|-------|---------|
| `locations` | Restaurant locations (Downtown, Airport, etc.) - dynamically discovered from source files |
| `orders` | Order headers with financials, timestamps, source system, channel (dine-in/pickup/delivery) |
| `order_items` | Line items linking orders to products, with quantity, price, modifiers |
| `products` | Canonical product names with category and `original_names[]` for variant tracking |
| `product_name_cache` | LLM normalization cache: "Lg Coke" → "Coca-Cola" (avoids re-calling LLM) |
| `product_category_cache` | LLM classification cache: "Coca-Cola" → "Beverages" with confidence score |
| `category_review_queue` | Human review workflow for uncertain LLM classifications (pending/approved/rejected) |
| `category_merge_queue` | Similar category suggestions from post-ETL audit ("Apps" ≈ "Appetizers") |
| `category_mappings` | User-curated overrides: always map "Soft Drinks" → "Beverages" |

### Design Decisions

#### 1. Money as Integers (Cents)
```sql
sales_cents INTEGER NOT NULL,      -- $12.50 = 1250
tax_cents INTEGER NOT NULL,
tip_cents INTEGER NOT NULL,
total_cents INTEGER GENERATED ALWAYS AS (sales_cents + tax_cents + tip_cents) STORED
```
**Why**: Avoids floating-point precision issues. Industry standard for financial data.

#### 2. Composite Unique Constraint
```sql
UNIQUE(source, external_id)  -- Prevents duplicate imports
```
**Why**: Same order ID can exist in different POS systems. Upsert handles re-runs.

#### 3. Dynamic Location Discovery
```sql
-- No hardcoded location enum!
-- Locations extracted from source files automatically
locations.name (UNIQUE)  -- "Downtown", "Airport", etc.
```
**Why**: New locations don't require code changes. Just run ETL.

#### 4. Product Variant Tracking
```sql
products.original_names TEXT[] DEFAULT '{}'
-- ["Lg Coke", "Large Coca-Cola", "Soft Drink"] → canonical: "Coca-Cola"
```
**Why**: Preserves data lineage. Know which source names mapped to which canonical.

#### 5. JSONB for Dynamic Source Breakdown
```sql
-- In reconciliation_totals view
source_breakdown JSONB  -- {"toast": {...}, "doordash": {...}, "square": {...}}
```
**Why**: Adding Uber Eats requires only ETL extractor, no schema/view changes.

### Materialized Views

| View | Dimensions | Metrics | Use Case |
|------|------------|---------|----------|
| `daily_sales` | date, location, channel, source | order_count, sales, tax, tips, total, avg_order | Daily trends |
| `hourly_sales` | date, hour, day_name, day_of_week, location | order_count, sales, tax, tips, total | Peak hour analysis |
| `product_performance` | product, category, location, channel | units_sold, sales, avg/min/max price, sources[] | Product analysis |
| `product_summary` | product, category | total across all locations, price_variance_flag | Product overview |
| `channel_breakdown` | location, channel, source | order_count, sales, tax, tips, total, avg | Channel comparison by location |
| `channel_summary` | channel | order_count, sales, tax, tips, total, avg | AOV by channel, sales by channel |
| `source_summary` | source | order_count, sales, tax, tips, total, avg | AOV by POS, sales by source |
| `location_summary` | location | aggregated across all channels | Location comparison |
| `reconciliation_totals` | (single row) | totals, source_breakdown (JSONB), quality metrics | Data quality |

### Data Quality Monitoring

The `reconciliation_totals` view tracks:

```sql
-- Errors (serious issues)
error_count = (
    orders with negative totals +
    items with quantity <= 0 +
    orphaned items (no product) +
    empty orders (no items)
)

-- Warnings (worth reviewing)
warning_count = (
    zero-value non-voided orders +
    unused products (no orders) +
    voided/deleted orders
)

-- Quality indicators
products_without_category  -- Uncategorized count
price_variance_flag        -- Per product: true if max > min * 2
```

### ETL Support Tables

```sql
-- LLM result caching
product_name_cache (original_name → canonical_name, confidence)
product_category_cache (product_name → category, confidence, source_category)

-- Human review workflow
category_review_queue (product_name, source_category, llm_category,
                       confidence_score, reason, status, final_category)
category_merge_queue (category_variants[], product_counts[], status)
category_mappings (source_category → canonical_category, created_by)
```

---

## AI Integration

### Query Processing Flow

```mermaid
flowchart TB
    Input["🗣️ User: 'Show me sales by location'"]

    subgraph Schema["📊 Schema Introspection"]
        S1["Tables: orders, order_items, products, locations"]
        S2["Views: daily_sales, hourly_sales, product_performance, etc."]
        S3["Dimensions: locations, sources, channels, categories"]
        S4["Date range: January 1-4, 2025"]
    end

    subgraph LLM["🤖 LLM System Prompt"]
        L1["You are an analytics SQL assistant"]
        L2["Available views with columns and data types..."]
        L3["Available dimensions with actual values..."]
        L4["Date range: {min_date} to {max_date}"]
        L5["Return JSON: sql, chartConfig, summary, drillDown"]
    end

    subgraph Validation["🔒 SQL Validation"]
        V1["execute_readonly_query() PostgreSQL function"]
        V2["Blocks: DROP, DELETE, INSERT, UPDATE, ALTER, TRUNCATE"]
        V3["Blocks: Comments (--), multiple statements (;)"]
        V4["10-second statement timeout"]
    end

    subgraph Retry["🔄 Automatic Retry"]
        R1["If SQL fails (syntax error, invalid column):"]
        R2["• Capture error message"]
        R3["• Re-call LLM with error context"]
        R4["• Max 2 attempts"]
    end

    Output["✅ Response: { data: [...], chartType: 'bar', summary: '...' }"]

    Input --> Schema
    Schema --> LLM
    LLM --> Validation
    Validation -->|Success| Output
    Validation -->|Failure| Retry
    Retry --> LLM
```

### Chart Type Selection

| Query Pattern | Chart Type | Example |
|---------------|------------|---------|
| "by location", "compare X vs Y" | Bar | Sales by location |
| "over time", "trend", "daily", "hourly" | Line | Daily revenue trend |
| "breakdown", "distribution", "share" | Pie | Channel breakdown |
| "top N", "list", "all products" | Table | Top 10 products |
| "total", "how much", single value | Metric | Total revenue |
| Informational, no data | Info | Data range info |

### Drill-Down Support

Charts support click-through exploration:

```typescript
// Click "Downtown" bar → DrillDownModal opens with:
{
  filters: { location: "Downtown" },
  summarySQL: "SELECT SUM(total_cents) as value FROM orders o
               JOIN locations l ON o.location_id = l.id
               WHERE l.name = :filter_value",
  summaryLabel: "Total Sales"
}

// Modal shows:
// - All orders for Downtown
// - Items in each order
// - Summary: "Total Sales: $2,450.00 (45 orders, 127 items)"
```

---

## Dashboard Features

### Multi-Widget Dashboard

- Each query adds a new widget to the dashboard (newest at top)
- Widgets accumulate - build up a dashboard with multiple visualizations
- Remove individual widgets with the X button
- Each widget shows its original query for context

### Query Input

- Natural language text input
- Quick-query example buttons with icons:
  - "Total sales" / "Total proceeds" (Dollar icon)
  - "Sales by location" (Location icon)
  - "AOV by channel" / "AOV by POS System" (Bar chart icon)
  - "Hourly sales trend" (Clock icon)
  - "Channel breakdown" (Pie icon)
  - "All products with sales" (Table icon)
- Loading state with spinner

### Chart Types

| Type | Component | Features |
|------|-----------|----------|
| Bar | `BarChartView` | Horizontal/vertical, value labels, drill-down on click |
| Line | `LineChartView` | Smooth curves, data points, time-series optimized |
| Pie | `PieChartView` | Custom colors, percentage labels, legend |
| Table | `TableView` | Sortable columns, formatted values, row click |
| Metric | `MetricView` | Large KPI number, subtitle, trend indicator |
| Info | `InfoCard` | Text-only informational display |

### Data Quality Modal

Accessible via info icon, shows:

- **Financial Summary**: Sales, tax, tips, total collected
- **Counts**: Orders, products, categories
- **Source Breakdown**: Dynamic per-source stats (from JSONB)
  - Each source shows: order count, sales, tax, tips, total
- **Quality Indicators**:
  - Errors (red): Data integrity issues
  - Warnings (orange): Potential issues
  - Uncategorized (yellow): Products without category
- **Date Range**: Min/max dates, location count

### Theme Support

- Dark/light mode toggle
- System preference detection
- Consistent styling across all components

---

## Solutions to Edge Cases

### The Margarita Problem

**Challenge**: Fuzzy matching grouped "Margarita" (cocktail) with "Margherita Pizza" because they're phonetically similar.

**Solution**: Two-part fix:
1. Check LLM cache FIRST, before fuzzy matching. The LLM understands semantic context (cocktail vs pizza).
2. Product Split Detection: If LLM maps fuzzy-grouped items to DIFFERENT canonical names, split them apart retroactively.

### Source Hint with Override

**Challenge**: POS source categories are sometimes wrong. Lobster Roll tagged as "Seafood" but it's actually a sandwich.

**Solution**: Pass source category as a "hint" to LLM, but let LLM override with reasoning:
```json
{
  "category": "Sandwiches",
  "confidence": 0.8,
  "reason": "Despite source saying Seafood, a lobster roll is served on a roll/bun"
}
```

### Confidence-Based Routing

**Challenge**: LLM isn't always right. Can't blindly trust classifications.

**Solution**: Three-tier routing based on confidence score:
| Confidence | Action |
|------------|--------|
| ≥ 90% | Auto-approve, save to cache |
| 70-90% | Save but flag for human review |
| < 70% | Don't apply, require human decision |

### Review Preservation Across ETL Runs

**Challenge**: Human reviews would get overwritten by subsequent ETL runs.

**Solution**: Track review status (`pending`/`approved`/`rejected`/`custom`) in `category_review_queue`. Loader checks status before applying—completed reviews are NEVER overwritten by future ETL runs.

### Dynamic Location Discovery

**Challenge**: Hardcoded location enums require code changes for new restaurants.

**Solution**: Extract location names from source files automatically. New location? Just run ETL. Zero code changes needed.

### Category Merge Queue

**Challenge**: Similar categories proliferate: "Appetizers", "Appetizers & Sides", "Apps", "Starters".

**Solution**: Post-ETL audit phase uses fuzzy matching to find similar categories, creates merge suggestions in `category_merge_queue`. Human picks canonical name, all variants get remapped.

### Custom Phonetic Normalization

**Challenge**: Standard Soundex/Metaphone not optimized for food/restaurant names.

**Solution**: Custom phonetic key function tuned for restaurant products:
```python
# phonetic_key() transformations:
# ph → f, ck → k, ee → i, ough → o, etc.
# "Philly Cheesesteak" and "Filly Cheesteak" → same key
```

### Product Variant Tracking

**Challenge**: Lose visibility into what source names became what canonical name.

**Solution**: Store `original_names[]` array on products:
```text
canonical_name: "Coca-Cola"
original_names: ["Lg Coke", "Large Coca-Cola", "Soft Drink", "Cola"]
```

### Graceful ETL Shutdown

**Challenge**: Ctrl+C during ETL could leave data in inconsistent state.

**Solution**: SIGINT/SIGTERM handling saves progress before exit. Second signal forces immediate exit. No orphaned transactions or partial loads.

### LLM Self-Correction

**Challenge**: LLM sometimes generates invalid SQL (wrong column name, syntax error).

**Solution**: Catch database error, re-call LLM with context:
```text
"Previous SQL failed with error: column 'revenue' does not exist.
Available columns: sales_cents, tax_cents, total_cents.
Please fix the query."
```
Max 2 attempts. LLM self-corrects based on the error.

---

> **Philosophy**: These solutions share a common thread—make the system **self-healing** and **human-supervised** rather than rigidly automated. The LLM provides intelligence, caching provides efficiency, and humans provide oversight for edge cases.

---

## Technical Decisions & Tradeoffs

### 1. LLM Cache Before Fuzzy Matching

**Decision**: Check LLM cache FIRST, before fuzzy matching (see [The Margarita Problem](#the-margarita-problem)).

**Tradeoff**: First ETL run is slower (must call LLM for all products), but subsequent runs are fast AND semantically correct. Worth it.

### 2. Materialized Views vs Real-time Queries

**Decision**: Pre-aggregated materialized views for analytics.

**Why**:
- Analytics queries scan large data volumes
- Pre-aggregation reduces query time 10-100x
- Data changes infrequently (after ETL runs)

**Tradeoff**: Data is eventually consistent (seconds delay after ETL).

### 3. Python ETL + FastAPI vs Node.js

**Decision**: Python for ETL and API.

**Why**:
- Superior data processing libraries
- RapidFuzz for fuzzy matching
- Anthropic SDK well-supported
- FastAPI provides async + OpenAPI docs

**Tradeoff**: Two languages in stack, but clear separation of concerns.

### 4. Human Review Queue

**Decision**: Flag uncertain LLM classifications for human review (see [Confidence-Based Routing](#confidence-based-routing) and [Review Preservation](#review-preservation-across-etl-runs)).

**Tradeoff**: Requires manual `make review` step, but ensures accuracy and builds institutional knowledge. Reviews are preserved forever.

### 5. JSONB for Source Breakdown

**Decision**: Dynamic JSONB aggregation instead of hardcoded source columns (same philosophy as [Dynamic Location Discovery](#dynamic-location-discovery)).

**Why**: Adding new POS source (Uber Eats) requires only:
1. Add ETL extractor
2. Add to CHECK constraint
3. **No view or frontend changes**

**Tradeoff**: Slightly more complex SQL, but highly extensible.

### 6. Server-Side SQL Validation

**Decision**: PostgreSQL function `execute_readonly_query()` validates and executes SQL. Combined with [LLM Self-Correction](#llm-self-correction) for automatic retry.

**Why**:
- Defense in depth (API + database validation)
- Statement timeout prevents runaway queries
- Blocks dangerous patterns at database level

**Tradeoff**: Extra RPC call, but much safer.

---

## What I'd Improve With More Time

### High Priority

1. **Semantic Query Caching**: Cache LLM responses for similar queries. "sales by location" ≈ "revenue per location" should hit same cache.

2. **Query Suggestions**: Autocomplete based on schema. Show "Try: top products, hourly trends, channel comparison" as user types.

3. **Incremental View Refresh**: Only update materialized views for changed data, not full refresh.

### Medium Priority

4. **Export Functionality**: Download charts as PNG/SVG, data as CSV/Excel.

5. **Query History**: Save, view, and re-run past queries. Share with team.

6. **Advanced Visualizations**: Heatmaps for hourly/daily patterns, sparklines in tables.

### Nice to Have

7. **Real-time Updates**: Supabase Realtime subscriptions for live order feeds.

8. **Multi-tenant**: Restaurant-level isolation with role-based access.

9. **Anomaly Detection**: Flag unusual sales patterns, alert on data quality issues.

10. **Conversational Refinement**: "Show me that but for last week", "Break that down by channel".

---

## Project Structure

```text
clave/
├── app/                          # Next.js frontend
│   ├── src/
│   │   ├── app/                  # Pages
│   │   ├── components/           # React components
│   │   │   ├── charts/           # Chart renderers
│   │   │   ├── QueryInput.tsx
│   │   │   ├── Widget.tsx        # Individual widget with remove button
│   │   │   ├── DrillDownModal.tsx
│   │   │   └── DataQualityModal.tsx
│   │   ├── hooks/
│   │   │   └── useQuery.ts       # Multi-widget state management
│   │   ├── lib/                  # Supabase client, API helpers
│   │   ├── styles/               # Tailwind styles
│   │   └── types/                # TypeScript interfaces
│   └── package.json
│
├── db/
│   ├── db.sql                    # Full schema export (reference only)
│   └── schema.png                # ERD diagram
│
├── api/                          # FastAPI backend
│   ├── routers/
│   │   ├── query.py              # POST /api/query
│   │   └── drill_down.py         # GET /api/drill-down
│   ├── services/
│   │   ├── query.py              # LLM prompt, NL→SQL, chart config
│   │   └── database.py           # Supabase queries, schema introspection
│   ├── llm/
│   │   ├── base.py               # LLM provider interface
│   │   └── anthropic_provider.py # Claude API wrapper
│   └── config.py
│
├── etl/                          # Data pipeline
│   ├── extract.py                # Toast, DoorDash, Square extractors
│   ├── transform.py              # Normalization, cleaning
│   ├── load.py                   # Batch loading with retry
│   ├── classifier.py             # LLM classification + caching
│   ├── matchers.py               # Fuzzy/phonetic matching
│   ├── review.py                 # Human review CLI
│   ├── audit.py                  # Post-ETL similarity detection
│   ├── models.py                 # Pydantic models
│   └── main.py                   # Pipeline orchestration
│
├── supabase/
│   ├── migrations/
│   │   ├── 001_schema.sql        # Core tables
│   │   ├── 002_functions.sql     # execute_readonly_query, refresh_views
│   │   ├── 003_views.sql         # Materialized views
│   │   ├── 004_etl_support.sql   # Cache tables, review queues
│   │   ├── 005_comments.sql      # Column documentation
│   │   └── 006_indexes.sql       # Performance indexes
│   └── reset.sql
│
├── data/sources/                 # Raw JSON files
│   ├── toast_pos_export.json
│   ├── doordash_orders.json
│   └── square/
│
├── .github/workflows/
│   └── deploy.yml                # CI: migrations → ETL on push
│
├── docker-compose.yml
├── Makefile
├── .env.example
└── README.md
```

---

## License

MIT
