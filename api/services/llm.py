import asyncio
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import anthropic

from config import get_settings

from .database import SchemaInfo, get_schema_info

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Custom error for LLM operations."""

    def __init__(self, message: str, code: str, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


ChartType = Literal["bar", "line", "pie", "table", "metric", "info"]
ValueFormat = Literal["currency", "number", "percent"]
DrillDownType = Literal["location", "date", "product", "category", "source", "channel"]


@dataclass
class DrillDownConfig:
    """Configuration for drill-down functionality."""

    enabled: bool
    type: DrillDownType | None = None
    column: str | None = None


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
    drill_down: DrillDownConfig | None = None


# SQL validation patterns
DANGEROUS_SQL_PATTERNS = [
    re.compile(r"\b(DROP|DELETE|INSERT|UPDATE|ALTER|TRUNCATE|CREATE|GRANT|REVOKE)\b", re.I),
    re.compile(r"\b(EXEC|EXECUTE|CALL)\b", re.I),
    re.compile(r";\s*\w", re.I),
    re.compile(r"--"),
    re.compile(r"/\*"),
]


def _simplify_pg_type(pg_type: str) -> str:
    """Convert PostgreSQL type to simplified type name."""
    pg_type = pg_type.lower()
    if "int" in pg_type or pg_type == "bigint" or pg_type == "smallint":
        return "INTEGER"
    if pg_type in ("text", "character varying", "varchar", "char"):
        return "TEXT"
    if pg_type == "uuid":
        return "UUID"
    if pg_type == "boolean":
        return "BOOLEAN"
    if pg_type == "date":
        return "DATE"
    if "timestamp" in pg_type:
        return "TIMESTAMPTZ"
    if pg_type in ("numeric", "decimal", "real", "double precision"):
        return "NUMERIC"
    return pg_type.upper()


def _format_table_schema(name: str, columns: list[dict[str, str]], comments: dict[str, str]) -> str:
    """Format a table's columns as markdown with comments."""
    lines = [f"**{name}**"]
    for col in columns:
        col_type = _simplify_pg_type(col["type"])
        comment_key = f"{name}.{col['column']}"
        comment = comments.get(comment_key, "")
        if comment:
            lines.append(f"- {col['column']}: {col_type} — {comment}")
        else:
            lines.append(f"- {col['column']}: {col_type}")
    return "\n".join(lines)


def _format_view_schema(name: str, columns: list[dict[str, str]], view_comments: dict[str, str]) -> str:
    """Format a view's columns as markdown with view-level comment."""
    comment = view_comments.get(name, "")
    header = f"**{name}**" + (f" — {comment}" if comment else "")
    col_lines = [f"- {c['column']}: {_simplify_pg_type(c['type'])}" for c in columns]
    return header + "\n" + "\n".join(col_lines)


def build_schema_context(schema: SchemaInfo) -> str:
    """Build dynamic schema context from database introspection."""
    locations_str = ", ".join(schema.locations) if schema.locations else "No locations"
    sources_str = ", ".join(schema.sources) if schema.sources else "No sources"
    channels_str = ", ".join(schema.channels) if schema.channels else "No channels"
    categories_str = ", ".join(schema.categories) if schema.categories else "No categories"
    payment_types_str = ", ".join(schema.payment_types) if schema.payment_types else "No payment types"

    # Format tables with comments
    tables_md = "\n\n".join(
        _format_table_schema(name, cols, schema.column_comments)
        for name, cols in sorted(schema.tables.items())
    )

    # Format views with comments
    views_md = "\n\n".join(
        _format_view_schema(name, cols, schema.view_comments)
        for name, cols in sorted(schema.views.items())
    )

    return f"""You are an analytics assistant for a restaurant chain.
Locations: {locations_str}
Data range: {schema.date_range.formatted}
POS sources: {sources_str}

## Database Schema

### Tables
Column comments contain synonyms and business rules - follow them.

{tables_md}

### Materialized Views (USE THESE FOR FASTER QUERIES)

{views_md}

## Dynamic Values (from actual data)
- Locations: {locations_str}
- Sources: {sources_str}
- Channels: {channels_str}
- Categories: {categories_str}
- Payment types: {payment_types_str}

## Date Handling (CRITICAL)
- The AVAILABLE DATA RANGE will be provided in each query context
- The CURRENT DATE will also be provided in each query context

### When user asks about dates:
1. **Date IN the available range** → Generate normal SQL query
2. **Date OUTSIDE the available range** → Return an info response

### If date is outside the available range, respond with:
- sql: "SELECT 1 as placeholder WHERE false"
- chartType: "info"
- title: "Date Outside Available Range"
- summary: MUST include the actual available dates and helpful suggestions.
"""

CHART_SELECTION_GUIDELINES = """
## Chart Type Selection Guidelines

Choose the visualization based on the DATA SEMANTICS and what would best communicate the insight:

### METRIC - Single aggregate value
- Use when the result is ONE number (total revenue, count of orders, average value)
- Result shape: 1 row, 1-2 columns

### LINE - Time series data
- Use when showing how values change over time (hourly, daily, weekly patterns)
- Result shape: multiple rows with a time/date column

### BAR - Categorical comparisons
- Use when comparing values across discrete categories (locations, products, channels)
- Result shape: multiple rows with a category column and value column

### PIE - Part-of-whole relationships
- Use when showing how parts contribute to a total (percentage breakdowns)
- Best for 2-7 categories; avoid for many categories
- Result shape: multiple rows with category and percentage/count

### TABLE - Detailed data
- Use when showing multi-dimensional data or raw records
- Result shape: multiple rows and columns with mixed data types

Use your judgment for ambiguous cases. The system will validate your choice against the actual result shape.
"""

TASK_PROMPT = """
## Your Task

Given a user's natural language query about restaurant analytics, return a JSON object with:
1. sql: A valid PostgreSQL SELECT query using the schema above
2. chartType: One of "bar", "line", "pie", "table", "metric" (follow the Chart Selection Guidelines above)
3. title: A short title for the visualization
4. xAxis: Column name for x-axis (bar/line charts)
5. yAxis: Column name for y-axis (bar/line charts)
6. dataKey: Column name for values (pie charts)
7. nameKey: Column name for labels (pie charts)
8. valueFormat: One of "currency" (for revenue/dollars), "number" (for counts/quantities), "percent" (for percentages)
9. summary: A 1-2 sentence insight about what the data shows
10. drillDown: Object for drill-down when user clicks a data point:
    - enabled: true if clicking should show underlying order details, false otherwise
    - type: one of "location", "date", "product", "category", "source", "channel" (the dimension to filter by)
    - column: which result column contains the value to filter by

SQL Rules:
- Always use the materialized views when possible
- Convert cents to dollars in the SQL (divide by 100.0)
- Round dollar amounts to 2 decimal places
- Use descriptive column aliases

## Drill-Down Guidelines

Enable drill-down when the query groups by a filterable dimension:
- location → drillDown: { enabled: true, type: "location", column: "location" }
- date/day → drillDown: { enabled: true, type: "date", column: "date" }
- product → drillDown: { enabled: true, type: "product", column: "product" }
- category → drillDown: { enabled: true, type: "category", column: "category" }
- source → drillDown: { enabled: true, type: "source", column: "source" }
- channel → drillDown: { enabled: true, type: "channel", column: "channel" }

Disable drill-down for:
- Single metrics (total revenue, count) → drillDown: { enabled: false }
- Complex aggregations without clear dimension → drillDown: { enabled: false }
- Time series (hourly/daily trends) can use date drill-down

## Handling Non-Analytics Queries

If the user's query is NOT about restaurant analytics (greetings, off-topic questions, etc.):
- Set sql to: SELECT 1 as placeholder WHERE false
- Set chartType to: "info"
- Set title to: "Welcome to Restaurant Analytics"
- Set summary to a helpful message explaining what queries are supported, with 2-3 examples
- Set drillDown to: { enabled: false }

Return ONLY valid JSON, no markdown code blocks or explanation."""


def build_system_prompt(schema: SchemaInfo) -> str:
    """Build complete system prompt with dynamic schema."""
    schema_context = build_schema_context(schema)
    return f"{schema_context}\n{CHART_SELECTION_GUIDELINES}\n{TASK_PROMPT}"


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
    except json.JSONDecodeError as e:
        logger.error(f"LLM parse error: {e}. Response: {text[:200]}")
        raise LLMError(
            "Couldn't process that query. Please try rephrasing your question.",
            "PARSE_ERROR",
            True,
        )

    if not data.get("sql") or not isinstance(data["sql"], str):
        logger.error(f"LLM response missing SQL: {data}")
        raise LLMError(
            "Couldn't generate a query. Please try rephrasing your question.",
            "INVALID_RESPONSE",
            True,
        )

    chart_type = data.get("chartType")
    if chart_type not in ["bar", "line", "pie", "table", "metric", "info"]:
        logger.error(f"LLM returned invalid chart type: {chart_type}")
        raise LLMError(
            "Couldn't determine how to display the results. Please try again.",
            "INVALID_RESPONSE",
            True,
        )

    # Validate chart-specific fields
    if chart_type in ["bar", "line"]:
        if not data.get("xAxis") or not data.get("yAxis"):
            logger.error(f"LLM {chart_type} chart missing axes: {data}")
            raise LLMError(
                "Couldn't configure the chart. Please try rephrasing your question.",
                "INVALID_RESPONSE",
                True,
            )

    if chart_type == "pie":
        if not data.get("dataKey") or not data.get("nameKey"):
            logger.error(f"LLM pie chart missing keys: {data}")
            raise LLMError(
                "Couldn't configure the chart. Please try rephrasing your question.",
                "INVALID_RESPONSE",
                True,
            )

    _validate_sql(data["sql"])

    # Parse drill-down config
    drill_down_data = data.get("drillDown", {})
    drill_down = None
    if isinstance(drill_down_data, dict):
        enabled = drill_down_data.get("enabled", False)
        dd_type = drill_down_data.get("type")
        dd_column = drill_down_data.get("column")

        # Validate drill-down type
        valid_types = {"location", "date", "product", "category", "source", "channel"}
        if dd_type and dd_type not in valid_types:
            dd_type = None
            enabled = False

        drill_down = DrillDownConfig(
            enabled=enabled,
            type=dd_type if enabled else None,
            column=dd_column if enabled else None,
        )

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
        drill_down=drill_down,
    )


async def _call_llm_with_retry(user_query: str, retry_count: int = 0) -> str:
    """Call LLM with retry logic."""
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    try:
        current_date = _get_current_date_context()
        schema = await get_schema_info()
        system_prompt = build_system_prompt(schema)

        response = client.messages.create(
            model=settings.llm_model,
            max_tokens=1024,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": f"""Context:
- Current date: {current_date}
- Available data range: {schema.date_range.formatted} ({schema.date_range.min_date} to {schema.date_range.max_date})

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
        if retry_count < settings.llm_max_retries:
            delay = settings.llm_initial_retry_delay * (2**retry_count)
            await asyncio.sleep(delay)
            return await _call_llm_with_retry(user_query, retry_count + 1)
        raise LLMError("Rate limit exceeded, please try again later", "RATE_LIMIT", False)

    except anthropic.APIStatusError as e:
        logger.error(f"Anthropic API error {e.status_code}: {e.message}")
        is_retryable = e.status_code >= 500 or e.status_code == 429
        if is_retryable and retry_count < settings.llm_max_retries:
            delay = settings.llm_initial_retry_delay * (2**retry_count)
            await asyncio.sleep(delay)
            return await _call_llm_with_retry(user_query, retry_count + 1)
        raise LLMError(
            "AI service is temporarily unavailable. Please try again.",
            f"API_ERROR_{e.status_code}",
            True,
        )

    except anthropic.AuthenticationError as e:
        logger.error(f"Anthropic auth error: {e}")
        raise LLMError(
            "Service configuration error. Please contact support.",
            "AUTH_ERROR",
            False,
        )


def validate_chart_type(data: list[dict], result: LLMResult) -> LLMResult:
    """
    Validate and potentially correct chart type based on actual result shape.

    This provides guardrails against LLM chart selection mistakes.
    """
    if not data or result.chart_type == "info":
        return result

    num_rows = len(data)
    num_cols = len(data[0]) if data else 0
    columns = list(data[0].keys()) if data else []
    columns_lower = [c.lower() for c in columns]

    # Check for time-related columns
    time_columns = {"date", "day", "hour", "day_name", "week", "month", "created_at"}
    has_time_column = any(col in time_columns for col in columns_lower)

    # Single value → metric
    if num_rows == 1 and num_cols <= 2:
        if result.chart_type not in ["metric", "table"]:
            return LLMResult(
                sql=result.sql,
                chart_type="metric",
                title=result.title,
                x_axis=None,
                y_axis=None,
                data_key=columns[0] if columns else None,
                name_key=None,
                value_format=result.value_format,
                summary=result.summary,
                drill_down=DrillDownConfig(enabled=False),  # Metrics don't have drill-down
            )

    # Time series data → line (unless explicitly table)
    if has_time_column and num_rows > 1 and result.chart_type not in ["line", "table"]:
        # Find the time column and value column
        time_col = next((c for c in columns if c.lower() in time_columns), columns[0])
        value_col = next((c for c in columns if c.lower() not in time_columns), columns[-1])
        return LLMResult(
            sql=result.sql,
            chart_type="line",
            title=result.title,
            x_axis=time_col,
            y_axis=value_col,
            data_key=None,
            name_key=None,
            value_format=result.value_format,
            summary=result.summary,
            drill_down=DrillDownConfig(enabled=True, type="date", column=time_col),
        )

    # Too many categories for pie → bar
    if result.chart_type == "pie" and num_rows > 10:
        return LLMResult(
            sql=result.sql,
            chart_type="bar",
            title=result.title,
            x_axis=result.name_key,
            y_axis=result.data_key,
            data_key=None,
            name_key=None,
            value_format=result.value_format,
            summary=result.summary,
            drill_down=result.drill_down,  # Preserve drill-down
        )

    # Many columns → table
    if num_cols > 4 and result.chart_type not in ["table"]:
        return LLMResult(
            sql=result.sql,
            chart_type="table",
            title=result.title,
            x_axis=None,
            y_axis=None,
            data_key=None,
            name_key=None,
            value_format=result.value_format,
            summary=result.summary,
            drill_down=result.drill_down,  # Preserve drill-down
        )

    return result


async def process_query(user_query: str) -> LLMResult:
    """Process a natural language query and return SQL + visualization config."""
    if not user_query or len(user_query.strip()) == 0:
        raise LLMError("Query cannot be empty", "INVALID_INPUT", False)

    if len(user_query) > 1000:
        raise LLMError("Query is too long (max 1000 characters)", "INVALID_INPUT", False)

    response_text = await _call_llm_with_retry(user_query)
    return _parse_response(response_text)
