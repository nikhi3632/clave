import asyncio
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import anthropic

from config import get_settings

from .database import get_data_date_range


class LLMError(Exception):
    """Custom error for LLM operations."""

    def __init__(self, message: str, code: str, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


ChartType = Literal["bar", "line", "pie", "table", "metric", "info"]
ValueFormat = Literal["currency", "number", "percent"]


@dataclass
class LLMResult:
    sql: str
    chart_type: ChartType
    title: str
    x_axis: str | None = None
    y_axis: str | None = None
    data_key: str | None = None
    name_key: str | None = None
    value_format: ValueFormat | None = None
    summary: str = ""


# SQL validation patterns
DANGEROUS_SQL_PATTERNS = [
    re.compile(r"\b(DROP|DELETE|INSERT|UPDATE|ALTER|TRUNCATE|CREATE|GRANT|REVOKE)\b", re.I),
    re.compile(r"\b(EXEC|EXECUTE|CALL)\b", re.I),
    re.compile(r";\s*\w", re.I),
    re.compile(r"--"),
    re.compile(r"/\*"),
]


SCHEMA_CONTEXT = """
You are an analytics assistant for a restaurant chain with 4 locations: Downtown, Airport, Mall, University.
Data covers January 1-4, 2025 from 3 POS sources: toast, doordash, square.

## Database Schema

### Tables

**locations**
- id: UUID
- name: TEXT (Downtown, Airport, Mall, University)

**products**
- id: UUID
- canonical_name: TEXT (normalized product name)
- category: TEXT (Appetizers, Breakfast, Desserts, Drinks, Entrees, Sides)

**orders**
- id: UUID
- external_id: TEXT
- source: TEXT (toast, doordash, square)
- location_id: UUID (FK to locations)
- channel: TEXT (dine_in, pickup, delivery)
- subtotal_cents: INTEGER
- tax_cents: INTEGER
- tip_cents: INTEGER
- total_cents: INTEGER (computed: subtotal + tax + tip)
- created_at: TIMESTAMPTZ

**order_items**
- id: UUID
- order_id: UUID (FK to orders)
- product_id: UUID (FK to products)
- quantity: INTEGER
- unit_price_cents: INTEGER
- total_cents: INTEGER (computed: quantity * unit_price)

### Materialized Views (USE THESE FOR FASTER QUERIES)

**daily_sales** - Daily aggregates by location/channel/source
- location: TEXT
- date: DATE
- channel: TEXT
- source: TEXT
- order_count: INTEGER
- revenue_cents: INTEGER
- avg_order_cents: INTEGER

**hourly_sales** - Hourly patterns by location
- location: TEXT
- date: DATE
- hour: INTEGER (0-23)
- day_name: TEXT (Monday, Tuesday, etc.)
- day_of_week: INTEGER (0=Sunday, 6=Saturday)
- order_count: INTEGER
- revenue_cents: INTEGER

**product_performance** - Product sales by location/channel
- product: TEXT
- category: TEXT
- location: TEXT
- channel: TEXT
- order_count: INTEGER
- units_sold: INTEGER
- revenue_cents: INTEGER

**channel_breakdown** - Channel comparison by location
- location: TEXT
- channel: TEXT
- source: TEXT
- order_count: INTEGER
- revenue_cents: INTEGER
- avg_order_cents: INTEGER
- total_tips_cents: INTEGER

## Important Notes
- All monetary values are in CENTS (divide by 100 for dollars)
- Use materialized views when possible - they're pre-aggregated
- Channel values: dine_in, pickup, delivery
  - "takeout" or "to-go" → use channel = 'pickup'
  - "in-store" or "eat-in" → use channel = 'dine_in'
- Source values: toast, doordash, square
- Category values: Appetizers, Breakfast, Desserts, Drinks, Entrees, Sides
  - "beverages" or "drinks" → use category = 'Drinks'
  - "main courses" or "mains" → use category = 'Entrees'
- Location values: Downtown, Airport, Mall, University

## Date Handling (CRITICAL)
- The AVAILABLE DATA RANGE will be provided in each query context (dynamically fetched from database)
- The CURRENT DATE will also be provided in each query context
- Use these to determine if a user's date query can be answered

### When user asks about dates:
1. **Date IN the available range** → Generate normal SQL query
2. **Date OUTSIDE the available range** → Return an info response (see below)

### Relative date keywords to detect:
- "yesterday", "today", "last week", "this week", "this month"
- "recent", "latest", "past X days"
- Any specific date outside the available data range

### If date is outside the available range, respond with:
- sql: "SELECT 1 as placeholder WHERE false"
- chartType: "info"
- title: "Date Outside Available Range"
- summary: MUST include the actual available dates and helpful suggestions.
"""

CHART_SELECTION_RULES = """
## Chart Type Selection Rules

Choose the chart type based on the DATA SHAPE and QUERY INTENT:

### BAR CHART - Use when:
- Comparing discrete categories (locations, products, channels)
- Showing rankings or top N items
- Keywords: "by", "per", "compare", "top", "best", "worst", "ranking"

### LINE CHART - Use when:
- Showing change over TIME (hours, days, weeks)
- Displaying trends or patterns
- Keywords: "trend", "over time", "pattern", "hourly", "daily", "weekly", "growth"

### PIE CHART - Use when:
- Showing parts of a whole (percentages, proportions)
- Keywords: "percentage", "proportion", "share", "breakdown", "distribution", "split"

### TABLE - Use when:
- User wants detailed/raw data
- Multiple columns of mixed data types
- Keywords: "list", "show all", "details", "breakdown by multiple dimensions"

### METRIC (single number) - Use when:
- Query asks for ONE specific value
- Keywords: "total", "how much", "how many", "what is the", "count of"

## Decision Priority
1. If asking for a single number → metric
2. If time-based (hour/day/date in result) → line
3. If asking about percentages/proportions → pie
4. If asking for detailed list → table
5. Otherwise (comparing categories) → bar
"""

SYSTEM_PROMPT = f"""{SCHEMA_CONTEXT}

{CHART_SELECTION_RULES}

## Your Task

Given a user's natural language query about restaurant analytics, return a JSON object with:
1. sql: A valid PostgreSQL SELECT query using the schema above
2. chartType: One of "bar", "line", "pie", "table", "metric" (follow the Chart Selection Rules above)
3. title: A short title for the visualization
4. xAxis: Column name for x-axis (bar/line charts)
5. yAxis: Column name for y-axis (bar/line charts)
6. dataKey: Column name for values (pie charts)
7. nameKey: Column name for labels (pie charts)
8. valueFormat: One of "currency" (for revenue/dollars), "number" (for counts/quantities), "percent" (for percentages)
9. summary: A 1-2 sentence insight about what the data shows

SQL Rules:
- Always use the materialized views when possible
- Convert cents to dollars in the SQL (divide by 100.0)
- Round dollar amounts to 2 decimal places
- Use descriptive column aliases

## Handling Non-Analytics Queries

If the user's query is NOT about restaurant analytics (greetings, off-topic questions, etc.):
- Set sql to: SELECT 1 as placeholder WHERE false
- Set chartType to: "info"
- Set title to: "Welcome to Restaurant Analytics"
- Set summary to a helpful message explaining what queries are supported, with 2-3 examples

Return ONLY valid JSON, no markdown code blocks or explanation."""


MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1.0


def _get_current_date_context() -> str:
    """Get current date in readable format."""
    return datetime.now().strftime("%A, %B %d, %Y")


def _validate_sql(sql: str) -> None:
    """Validate SQL for safety."""
    trimmed = sql.strip().upper()
    if not trimmed.startswith("SELECT") and not trimmed.startswith("WITH"):
        raise LLMError("Invalid SQL: must be a SELECT query", "INVALID_SQL", False)

    for pattern in DANGEROUS_SQL_PATTERNS:
        if pattern.search(sql):
            raise LLMError("Invalid SQL: contains disallowed operations", "INVALID_SQL", False)


def _parse_response(text: str) -> LLMResult:
    """Parse LLM response JSON."""
    clean_text = text.strip()
    if clean_text.startswith("```json"):
        clean_text = clean_text[7:]
    elif clean_text.startswith("```"):
        clean_text = clean_text[3:]
    if clean_text.endswith("```"):
        clean_text = clean_text[:-3]
    clean_text = clean_text.strip()

    try:
        data = json.loads(clean_text)
    except json.JSONDecodeError:
        raise LLMError(f"Failed to parse AI response: {text[:100]}...", "PARSE_ERROR", True)

    if not data.get("sql") or not isinstance(data["sql"], str):
        raise LLMError("Invalid response: missing SQL query", "INVALID_RESPONSE", True)

    chart_type = data.get("chartType")
    if chart_type not in ["bar", "line", "pie", "table", "metric", "info"]:
        raise LLMError("Invalid response: invalid chart type", "INVALID_RESPONSE", True)

    # Validate chart-specific fields
    if chart_type in ["bar", "line"]:
        if not data.get("xAxis") or not data.get("yAxis"):
            raise LLMError(
                f"Invalid response: {chart_type} chart requires xAxis and yAxis",
                "INVALID_RESPONSE",
                True,
            )

    if chart_type == "pie":
        if not data.get("dataKey") or not data.get("nameKey"):
            raise LLMError(
                "Invalid response: pie chart requires dataKey and nameKey",
                "INVALID_RESPONSE",
                True,
            )

    _validate_sql(data["sql"])

    return LLMResult(
        sql=data["sql"],
        chart_type=chart_type,
        title=data.get("title", "Query Result"),
        x_axis=data.get("xAxis"),
        y_axis=data.get("yAxis"),
        data_key=data.get("dataKey"),
        name_key=data.get("nameKey"),
        value_format=data.get("valueFormat"),
        summary=data.get("summary", "Query executed successfully."),
    )


async def _call_llm_with_retry(user_query: str, retry_count: int = 0) -> str:
    """Call LLM with retry logic."""
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    try:
        current_date = _get_current_date_context()
        date_range = await get_data_date_range()

        response = client.messages.create(
            model=settings.llm_model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"""Context:
- Current date: {current_date}
- Available data range: {date_range.formatted} ({date_range.min_date} to {date_range.max_date})

User query: "{user_query}"

Return the JSON object with sql, chartType, title, xAxis/yAxis or dataKey/nameKey, and summary.""",
                }
            ],
        )

        content = response.content[0]
        if content.type != "text":
            raise LLMError("Unexpected response type from LLM", "INVALID_RESPONSE", True)

        return content.text

    except anthropic.RateLimitError:
        if retry_count < MAX_RETRIES:
            delay = INITIAL_RETRY_DELAY * (2**retry_count)
            await asyncio.sleep(delay)
            return await _call_llm_with_retry(user_query, retry_count + 1)
        raise LLMError("Rate limit exceeded, please try again later", "RATE_LIMIT", False)

    except anthropic.APIStatusError as e:
        is_retryable = e.status_code >= 500 or e.status_code == 429
        if is_retryable and retry_count < MAX_RETRIES:
            delay = INITIAL_RETRY_DELAY * (2**retry_count)
            await asyncio.sleep(delay)
            return await _call_llm_with_retry(user_query, retry_count + 1)
        raise LLMError(f"AI service error: {e.message}", f"API_ERROR_{e.status_code}", False)

    except anthropic.AuthenticationError:
        raise LLMError("AI service authentication failed", "AUTH_ERROR", False)


async def process_query(user_query: str) -> LLMResult:
    """Process a natural language query and return SQL + visualization config."""
    if not user_query or len(user_query.strip()) == 0:
        raise LLMError("Query cannot be empty", "INVALID_INPUT", False)

    if len(user_query) > 1000:
        raise LLMError("Query is too long (max 1000 characters)", "INVALID_INPUT", False)

    response_text = await _call_llm_with_retry(user_query)
    return _parse_response(response_text)
