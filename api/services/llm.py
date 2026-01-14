import asyncio
import json
import logging
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from config import get_settings

# Add project root to path for shared llm module (for local dev)
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from llm import APIError, LLMError, RateLimitError, get_provider  # noqa: E402

from .database import SchemaInfo, ViewMetadata, get_schema_info  # noqa: E402

logger = logging.getLogger(__name__)


ChartType = Literal["bar", "line", "pie", "table", "metric", "info"]
ValueFormat = Literal["currency", "number", "percent"]
# DrillDownType is now validated dynamically against schema.dimensions


@dataclass
class DrillDownConfig:
    """Configuration for drill-down functionality."""

    enabled: bool
    type: str | None = None  # Validated against schema.dimensions at runtime
    column: str | None = None
    summary_sql: str | None = None  # SQL query to calculate drill-down summary (same logic as chart)
    summary_label: str | None = None  # Display label for the summary value


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
            # Extract just first line of comment for brevity
            first_line = comment.split("\n")[0].strip()
            lines.append(f"- {col['column']}: {col_type} — {first_line}")
        else:
            lines.append(f"- {col['column']}: {col_type}")
    return "\n".join(lines)


def _format_view_from_metadata(view: ViewMetadata, column_comments: dict[str, str]) -> str:
    """Format a view using parsed metadata."""
    lines = [f"**{view.name}**"]

    # Add purpose if available
    if view.purpose:
        lines[0] += f" — {view.purpose}"

    # Add use_for hint
    if view.use_for:
        lines.append(f"  USE FOR: {view.use_for}")

    # Add dimensions and metrics
    if view.dimensions:
        lines.append(f"  DIMENSIONS: {', '.join(view.dimensions)}")
    if view.metrics:
        lines.append(f"  METRICS: {', '.join(view.metrics)}")

    # Add columns with their comments (show synonyms)
    lines.append("  Columns:")
    for col in view.columns:
        col_type = _simplify_pg_type(col["type"])
        comment_key = f"{view.name}.{col['column']}"
        comment = column_comments.get(comment_key, "")

        col_line = f"    - {col['column']}: {col_type}"
        if comment:
            # Extract synonyms if present
            if "SYNONYMS:" in comment.upper():
                import re
                match = re.search(r"SYNONYMS:\s*([^\n]+)", comment, re.IGNORECASE)
                if match:
                    col_line += f" (synonyms: {match.group(1).strip()})"
        lines.append(col_line)

    return "\n".join(lines)


def _generate_dimensions_section(schema: SchemaInfo) -> str:
    """Generate dimensions documentation from database metadata."""
    lines = []
    for name, dim in sorted(schema.dimensions.items()):
        values_preview = ", ".join(dim.values[:5]) if dim.values else "none"
        if len(dim.values) > 5:
            values_preview += f", ... ({len(dim.values)} total)"
        lines.append(f"- **{name}**: {values_preview}")
        if dim.filter_pattern:
            lines.append(f"  Filter: {dim.filter_pattern}")
    return "\n".join(lines)


def _generate_views_section(schema: SchemaInfo) -> str:
    """Generate views documentation from parsed metadata."""
    lines = []
    for name, view in sorted(schema.views.items()):
        lines.append(_format_view_from_metadata(view, schema.column_comments))
    return "\n\n".join(lines)


def build_schema_context(schema: SchemaInfo) -> str:
    """Build dynamic schema context from database introspection."""
    # Format tables with comments
    tables_md = "\n\n".join(
        _format_table_schema(name, cols, schema.column_comments)
        for name, cols in sorted(schema.tables.items())
    )

    # Format views from parsed metadata
    views_md = _generate_views_section(schema)

    # Generate dimensions section
    dimensions_md = _generate_dimensions_section(schema)

    # Generate valid drill-down types from dimensions
    drill_down_types = ", ".join(f'"{d}"' for d in schema.dimensions.keys())

    return f"""You are an analytics assistant.
Data range: {schema.date_range.formatted}

## Available Dimensions
{dimensions_md}

## Base Tables
{tables_md}

## Analytics Views (USE THESE FOR QUERIES)
Each view shows its PURPOSE, what it's useful FOR, available DIMENSIONS and METRICS.
Column synonyms show alternative terms users might use.

{views_md}

## Query Generation Principles

### Finding the Right View
1. Read each view's PURPOSE to understand what it's optimized for
2. Match your query goal to a view's "USE FOR" hints
3. Check that the view has the DIMENSIONS and METRICS you need
4. Prefer views over base tables for aggregations

### Column Selection
1. Column comments show SYNONYMS - map user terms to actual column names
2. Look for the column whose synonyms best match what the user asked for
3. If user says "revenue" or "sales", look for columns with those synonyms

### Currency
- Monetary values stored in cents (integers)
- Return raw cents in SQL - frontend handles formatting
- Do NOT divide by 100 in queries

### Drill-Down SQL (summarySQL)
1. For summarySQL, use base tables (orders, order_items) with appropriate joins
2. Check dimension info above for FILTER patterns
3. Use :filter_value as placeholder for the clicked dimension value
4. Return a single row with column named "value" (in cents for monetary values)
5. Valid drill-down types: {drill_down_types}, "date"

### Date Handling
- Available data: {schema.date_range.min_date} to {schema.date_range.max_date}
- No date specified → Query ALL available data
- Relative date (yesterday, last week) → Calculate from current date
- Date outside range → Return info response with available dates
"""

CHART_SELECTION_GUIDELINES = """
## Chart Type Selection

Choose based on data semantics:

- **METRIC**: Single aggregate value (1 row, 1-2 columns)
- **LINE**: Time series data (multiple rows with date/hour column)
- **BAR**: Categorical comparisons (multiple rows with category + value)
- **PIE**: Part-of-whole (2-7 categories)
- **TABLE**: Multi-dimensional or detailed data
"""

TASK_PROMPT = """
## Your Task

Return a JSON object with:
1. **sql**: PostgreSQL SELECT query using the views/tables above
2. **chartType**: "bar", "line", "pie", "table", or "metric"
3. **title**: Short title for the visualization
4. **xAxis/yAxis**: Column names for bar/line charts
5. **dataKey/nameKey**: Column names for pie charts
6. **valueFormat**: "currency", "number", or "percent"
7. **summary**: 1-2 sentence insight
8. **drillDown**: Configuration for clicking data points:
   - enabled: true if dimension is drillable
   - type: the dimension name from Available Dimensions above
   - column: which result column contains the filter value
   - summarySQL: Query returning single row with "value" column, using :filter_value placeholder
   - summaryLabel: Display label for the value

## SQL Principles

1. **Use views for aggregations** - they're pre-optimized
2. **Return raw values** - do not convert cents to dollars in SQL
3. **Use column synonyms** - check column comments for alternative names
4. **Descriptive aliases** - name columns clearly

## Drill-Down Principles

1. **Enable when grouped by a dimension** - location, product, date, etc.
2. **summarySQL must match main query logic** - same aggregation, filtered
3. **Use base tables for summarySQL** - orders, order_items with joins
4. **Check dimension FILTER patterns** - use the pattern shown in Available Dimensions
5. **Return value in cents** - frontend formats it
6. **Disable for single metrics** - no dimension to filter by

## Non-Analytics Queries

For greetings or off-topic:
- sql: "SELECT 1 as placeholder WHERE false"
- chartType: "info"
- title: "Welcome"
- summary: Helpful message with example queries
- drillDown: { enabled: false }

Return ONLY valid JSON, no markdown or explanation."""


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
        summary_sql = drill_down_data.get("summarySQL")
        summary_label = drill_down_data.get("summaryLabel")

        # Drill-down type validation is now dynamic
        # Accept any string type - validated at runtime against schema.dimensions
        if dd_type and not isinstance(dd_type, str):
            dd_type = None
            enabled = False

        # Validate summarySQL if provided
        if summary_sql:
            try:
                _validate_sql(summary_sql)
            except LLMError:
                logger.warning(f"Invalid summarySQL, disabling: {summary_sql}")
                summary_sql = None

        drill_down = DrillDownConfig(
            enabled=enabled,
            type=dd_type if enabled else None,
            column=dd_column if enabled else None,
            summary_sql=summary_sql if enabled else None,
            summary_label=summary_label if enabled else None,
        )

    # Validate value_format
    value_format = data.get("valueFormat")
    valid_formats = {"currency", "number", "percent"}
    if value_format not in valid_formats:
        value_format = None

    return LLMResult(
        sql=data["sql"],
        chart_type=chart_type,
        title=data.get("title", "Query Result"),
        x_axis=data.get("xAxis"),
        y_axis=data.get("yAxis"),
        data_key=data.get("dataKey"),
        name_key=data.get("nameKey"),
        value_format=value_format,
        summary=data.get("summary", "Query executed successfully."),
        drill_down=drill_down,
    )


async def _call_llm_with_retry(user_query: str, retry_count: int = 0) -> str:
    """Call LLM with retry logic."""
    settings = get_settings()
    provider = get_provider(
        api_key=settings.anthropic_api_key,
        model=settings.llm_model,
        provider=settings.llm_provider,
    )

    try:
        current_date = _get_current_date_context()
        schema = await get_schema_info()
        system_prompt = build_system_prompt(schema)

        response = await provider.complete(
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
            system=system_prompt,
            max_tokens=1024,
        )

        return response.content

    except RateLimitError:
        if retry_count < settings.llm_max_retries:
            delay = settings.llm_initial_retry_delay * (2**retry_count)
            await asyncio.sleep(delay)
            return await _call_llm_with_retry(user_query, retry_count + 1)
        raise LLMError("Rate limit exceeded, please try again later", "RATE_LIMIT", False)

    except APIError as e:
        if e.retryable and retry_count < settings.llm_max_retries:
            delay = settings.llm_initial_retry_delay * (2**retry_count)
            await asyncio.sleep(delay)
            return await _call_llm_with_retry(user_query, retry_count + 1)
        raise


def validate_chart_type(
    data: list[dict], result: LLMResult, schema: SchemaInfo | None = None
) -> LLMResult:
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

    # Check for time-related columns using common patterns
    # These are semantic indicators that work across schemas
    time_indicators = {"date", "day", "hour", "week", "month", "year", "time", "created"}
    has_time_column = any(
        any(indicator in col for indicator in time_indicators)
        for col in columns_lower
    )

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
        time_col = next(
            (c for c in columns if any(t in c.lower() for t in time_indicators)), columns[0]
        )
        value_col = next(
            (c for c in columns if not any(t in c.lower() for t in time_indicators)), columns[-1]
        )
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
            drill_down=result.drill_down,  # Preserve original drill-down config
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


async def _call_llm_with_error_context(
    user_query: str,
    failed_sql: str,
    error_message: str,
) -> str:
    """Call LLM with error context for self-correction."""
    settings = get_settings()
    provider = get_provider(
        api_key=settings.anthropic_api_key,
        model=settings.llm_model,
        provider=settings.llm_provider,
    )

    current_date = _get_current_date_context()
    schema = await get_schema_info()
    system_prompt = build_system_prompt(schema)

    error_context = f"""
## Correction Needed

Your previous SQL query failed. Please correct it.

**Failed SQL:**
```sql
{failed_sql}
```

**Error:**
{error_message}

**How to fix:**
1. Check that all column names exist in the view/table you're querying
2. Check that table/view names are spelled correctly
3. Use column synonyms from the schema comments if needed
4. For sales columns: both views and orders table use 'sales_cents'

Generate a corrected query.
"""

    response = await provider.complete(
        messages=[
            {
                "role": "user",
                "content": f"""Context:
- Current date: {current_date}
- Available data range: {schema.date_range.formatted} ({schema.date_range.min_date} to {schema.date_range.max_date})

User query: "{user_query}"

{error_context}

Return the corrected JSON object.""",
            }
        ],
        system=system_prompt,
        max_tokens=1024,
    )

    return response.content


async def process_query(user_query: str) -> LLMResult:
    """Process a natural language query and return SQL + visualization config."""
    settings = get_settings()

    if not user_query or len(user_query.strip()) == 0:
        raise LLMError("Query cannot be empty", "INVALID_INPUT", False)

    if len(user_query) > settings.max_query_length:
        raise LLMError(
            f"Query is too long (max {settings.max_query_length} characters)",
            "INVALID_INPUT",
            False,
        )

    response_text = await _call_llm_with_retry(user_query)
    return _parse_response(response_text)


async def process_query_with_retry(
    user_query: str,
    execute_fn,
    max_attempts: int = 2,
) -> tuple[LLMResult, list[dict]]:
    """
    Process query with automatic retry on SQL execution failure.

    Args:
        user_query: The user's natural language query
        execute_fn: Async function that executes SQL and returns results
        max_attempts: Maximum number of attempts (default 2)

    Returns:
        Tuple of (LLMResult, data rows)

    Raises:
        LLMError or DatabaseError if all attempts fail
    """
    from .database import DatabaseError

    settings = get_settings()

    if not user_query or len(user_query.strip()) == 0:
        raise LLMError("Query cannot be empty", "INVALID_INPUT", False)

    if len(user_query) > settings.max_query_length:
        raise LLMError(
            f"Query is too long (max {settings.max_query_length} characters)",
            "INVALID_INPUT",
            False,
        )

    last_error = None
    last_result = None

    for attempt in range(max_attempts):
        try:
            if attempt == 0:
                # First attempt - normal query
                response_text = await _call_llm_with_retry(user_query)
            else:
                # Retry with error context
                logger.info(f"Retrying query with error context (attempt {attempt + 1})")
                response_text = await _call_llm_with_error_context(
                    user_query,
                    last_result.sql if last_result else "",
                    str(last_error),
                )

            result = _parse_response(response_text)
            last_result = result

            # Try to execute the SQL
            data = await execute_fn(result.sql)
            return result, data

        except DatabaseError as e:
            last_error = e
            logger.warning(f"Query attempt {attempt + 1} failed: {e}")

            # If not retryable or last attempt, raise
            if not e.retryable or attempt == max_attempts - 1:
                raise

        except LLMError:
            # LLM errors are not retryable with context
            raise

    # Should not reach here, but just in case
    raise last_error or LLMError("Query failed", "UNKNOWN_ERROR", False)
