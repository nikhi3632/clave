"""Query service - LLM-based query processing with schema interpretation."""

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from config import get_settings
from llm import APIError, LLMError, RateLimitError, get_provider

from .database import DatabaseError, DataDateRange, get_raw_schema

logger = logging.getLogger(__name__)


# ============================================================
# Type Definitions
# ============================================================

ChartType = Literal["bar", "line", "pie", "table", "metric", "info"]
ValueFormat = Literal["currency", "number", "percent"]


# ============================================================
# Comment Parsing Utilities (LLM-specific interpretation)
# ============================================================


def _extract_field(comment: str, field_name: str) -> str | None:
    """Extract a single-line field value from a structured comment."""
    pattern = rf"^{re.escape(field_name)}\s*(.+?)$"
    match = re.search(pattern, comment, re.MULTILINE | re.IGNORECASE)
    return match.group(1).strip() if match else None


def _extract_list(comment: str, field_name: str) -> list[str]:
    """Extract a comma-separated list from a structured comment."""
    value = _extract_field(comment, field_name)
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _is_internal_view(comment: str | None) -> bool:
    """Check if a view is marked as internal (not for analytics)."""
    if not comment:
        return False
    return comment.strip().upper().startswith("INTERNAL:")


# ============================================================
# Parsed Schema Dataclasses (LLM context)
# ============================================================


@dataclass
class ViewMetadata:
    """Parsed metadata from a view's COMMENT ON."""

    name: str
    purpose: str | None = None
    dimensions: list[str] = field(default_factory=list)
    metrics: list[str] = field(default_factory=list)
    use_for: str | None = None
    columns: list[dict[str, str]] = field(default_factory=list)  # [{column, type}]
    is_analytics: bool = True


@dataclass
class DimensionInfo:
    """Metadata about a dimension (from table COMMENT ON)."""

    name: str  # "location", "product", "category"
    table: str  # "locations", "products"
    display_column: str  # "name", "canonical_name"
    filter_pattern: str | None = None  # JOIN pattern with :filter_value
    values: list[str] = field(default_factory=list)  # Actual values from data


@dataclass
class ColumnInfo:
    """Metadata about a column including synonyms."""

    name: str
    data_type: str
    synonyms: list[str] = field(default_factory=list)
    note: str | None = None


@dataclass
class SchemaConventions:
    """Schema-level conventions parsed from COMMENT ON SCHEMA."""

    currency_unit: str = "cents"
    currency_divisor: int = 100
    currency_decimals: int = 2
    naming_conventions: str | None = None
    raw_comment: str | None = None


@dataclass
class SchemaInfo:
    """Dynamic schema information for LLM context."""

    # Parsed view metadata (analytics views only)
    views: dict[str, ViewMetadata]

    # Discovered dimensions from table comments
    dimensions: dict[str, DimensionInfo]

    # Column info with synonyms
    columns: dict[str, ColumnInfo]  # "view.column" -> ColumnInfo

    # Schema conventions
    conventions: SchemaConventions

    # Date range
    date_range: DataDateRange

    # Base tables (for reference)
    tables: dict[str, list[dict[str, str]]]  # table -> [{column, type}]

    # Raw comments (for backward compatibility during transition)
    column_comments: dict[str, str]  # "table.column" -> comment
    view_comments: dict[str, str]  # "view_name" -> comment

    # Legacy dimension values (for backward compatibility)
    locations: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    channels: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    payment_types: list[str] = field(default_factory=list)


# ============================================================
# Comment Parsing Functions
# ============================================================


def parse_view_comment(
    name: str, comment: str | None, columns: list[dict[str, str]]
) -> ViewMetadata:
    """Parse a view's COMMENT ON into structured metadata."""
    if not comment or _is_internal_view(comment):
        return ViewMetadata(name=name, columns=columns, is_analytics=False)

    return ViewMetadata(
        name=name,
        purpose=_extract_field(comment, "PURPOSE:"),
        dimensions=_extract_list(comment, "DIMENSIONS:"),
        metrics=_extract_list(comment, "METRICS:"),
        use_for=_extract_field(comment, "USE FOR:"),
        columns=columns,
        is_analytics=True,
    )


def parse_column_comment(comment: str | None) -> dict[str, Any]:
    """Parse a column's COMMENT ON for synonyms and notes."""
    if not comment:
        return {"synonyms": [], "note": None}

    synonyms = _extract_list(comment, "SYNONYMS:")
    note = _extract_field(comment, "NOTE:")

    return {"synonyms": synonyms, "note": note}


def parse_dimension_table_comment(
    table_name: str, comment: str | None
) -> list[DimensionInfo]:
    """Parse a table's COMMENT ON for dimension metadata."""
    if not comment or "DIMENSION:" not in comment.upper():
        return []

    dimensions = []

    # Extract dimension names
    dim_field = _extract_field(comment, "DIMENSION:")
    if not dim_field:
        return []

    dim_names = [d.strip() for d in dim_field.split(",")]

    # Extract display columns (may be per-dimension)
    display_col = _extract_field(comment, "DISPLAY_COLUMN:")
    display_cols = _extract_field(comment, "DISPLAY_COLUMNS:")

    for dim_name in dim_names:
        # Try to find dimension-specific display column
        display_column = None
        if display_cols:
            # Parse "canonical_name (for product), category (for category)"
            for part in display_cols.split(","):
                if f"({dim_name})" in part.lower() or f"(for {dim_name})" in part.lower():
                    display_column = part.split("(")[0].strip()
                    break
        if not display_column and display_col:
            display_column = display_col

        # Get filter pattern
        filter_pattern = _extract_field(comment, f"FILTER_PATTERN_{dim_name}:")
        if not filter_pattern:
            filter_pattern = _extract_field(comment, "FILTER_PATTERN:")

        dimensions.append(
            DimensionInfo(
                name=dim_name,
                table=table_name,
                display_column=display_column or "name",
                filter_pattern=filter_pattern,
                values=[],  # Filled in later
            )
        )

    return dimensions


def parse_schema_conventions(comment: str | None) -> SchemaConventions:
    """Parse COMMENT ON SCHEMA for conventions."""
    if not comment:
        return SchemaConventions()

    # Parse currency info
    currency_line = _extract_field(comment, "CURRENCY:")
    currency_unit = "cents"
    currency_divisor = 100
    currency_decimals = 2

    if currency_line:
        if "cents" in currency_line.lower():
            currency_unit = "cents"
        if "100" in currency_line:
            currency_divisor = 100

    naming = None
    if "NAMING CONVENTIONS:" in comment.upper():
        # Extract everything after NAMING CONVENTIONS: until next section or end
        match = re.search(
            r"NAMING CONVENTIONS:\s*\n([\s\S]*?)(?=\n[A-Z]+:|$)",
            comment,
            re.IGNORECASE,
        )
        if match:
            naming = match.group(1).strip()

    return SchemaConventions(
        currency_unit=currency_unit,
        currency_divisor=currency_divisor,
        currency_decimals=currency_decimals,
        naming_conventions=naming,
        raw_comment=comment,
    )


# ============================================================
# Schema Building (interprets raw data for LLM)
# ============================================================

# Cache for parsed schema
_schema_cache: dict[str, tuple[SchemaInfo, float]] = {}


async def get_schema_info() -> SchemaInfo:
    """Get parsed schema information for LLM context."""
    cache_key = "schema"
    settings = get_settings()

    if cache_key in _schema_cache:
        cached, cached_at = _schema_cache[cache_key]
        if time.time() - cached_at < settings.schema_cache_ttl:
            return cached

    # Get raw schema from database
    raw = await get_raw_schema()

    # ============================================================
    # 1. Discover dimensions from table comments
    # ============================================================

    discovered_dimensions: dict[str, DimensionInfo] = {}
    for table_name, comment in raw.table_comments.items():
        dims = parse_dimension_table_comment(table_name, comment)
        for dim in dims:
            discovered_dimensions[dim.name] = dim

    # Fill in dimension values from raw schema
    if "location" in discovered_dimensions:
        discovered_dimensions["location"].values = raw.locations
    if "product" in discovered_dimensions:
        discovered_dimensions["product"].values = raw.products
    if "category" in discovered_dimensions:
        discovered_dimensions["category"].values = raw.categories

    # Add implicit dimensions (source, channel) that aren't from dimension tables
    discovered_dimensions["source"] = DimensionInfo(
        name="source",
        table="orders",
        display_column="source",
        filter_pattern="WHERE source = :filter_value",
        values=raw.sources,
    )
    discovered_dimensions["channel"] = DimensionInfo(
        name="channel",
        table="orders",
        display_column="channel",
        filter_pattern="WHERE channel = :filter_value",
        values=raw.channels,
    )
    discovered_dimensions["payment_type"] = DimensionInfo(
        name="payment_type",
        table="orders",
        display_column="payment_type",
        filter_pattern="WHERE payment_type = :filter_value",
        values=raw.payment_types,
    )

    # ============================================================
    # 2. Parse view metadata and filter out internal views
    # ============================================================

    parsed_views: dict[str, ViewMetadata] = {}
    for view_name, columns in raw.views.items():
        comment = raw.view_comments.get(view_name)
        metadata = parse_view_comment(view_name, comment, columns)
        if metadata.is_analytics:
            parsed_views[view_name] = metadata

    # ============================================================
    # 3. Parse column comments for synonyms
    # ============================================================

    parsed_columns: dict[str, ColumnInfo] = {}
    for key, comment in raw.column_comments.items():
        table_name, col_name = key.split(".", 1)
        parsed = parse_column_comment(comment)

        # Get column type from view or table
        col_type = "unknown"
        if table_name in raw.views:
            for col in raw.views[table_name]:
                if col["column"] == col_name:
                    col_type = col["type"]
                    break
        elif table_name in raw.tables:
            for col in raw.tables[table_name]:
                if col["column"] == col_name:
                    col_type = col["type"]
                    break

        parsed_columns[key] = ColumnInfo(
            name=col_name,
            data_type=col_type,
            synonyms=parsed["synonyms"],
            note=parsed.get("note"),
        )

    # ============================================================
    # 4. Parse schema conventions
    # ============================================================

    conventions = parse_schema_conventions(raw.schema_comment)

    # ============================================================
    # 5. Build and cache SchemaInfo
    # ============================================================

    schema_info = SchemaInfo(
        views=parsed_views,
        dimensions=discovered_dimensions,
        columns=parsed_columns,
        conventions=conventions,
        date_range=raw.date_range,
        tables=raw.tables,
        column_comments=raw.column_comments,
        view_comments=raw.view_comments,
        # Legacy fields for backward compatibility
        locations=raw.locations,
        sources=raw.sources,
        channels=raw.channels,
        categories=raw.categories,
        payment_types=raw.payment_types,
    )

    _schema_cache[cache_key] = (schema_info, time.time())
    return schema_info


# ============================================================
# LLM Response Types
# ============================================================


@dataclass
class DrillDownConfig:
    """Configuration for drill-down functionality."""

    enabled: bool
    type: str | None = None  # Validated against schema.dimensions at runtime
    column: str | None = None
    summary_sql: str | None = None  # SQL query to calculate drill-down summary
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


# ============================================================
# SQL Validation
# ============================================================

DANGEROUS_SQL_PATTERNS = [
    re.compile(r"\b(DROP|DELETE|INSERT|UPDATE|ALTER|TRUNCATE|CREATE|GRANT|REVOKE)\b", re.I),
    re.compile(r"\b(EXEC|EXECUTE|CALL)\b", re.I),
    re.compile(r";\s*\w", re.I),
    re.compile(r"--"),
    re.compile(r"/\*"),
]


def _validate_sql(sql: str) -> None:
    """Validate SQL for safety."""
    trimmed = sql.strip().upper()
    if not trimmed.startswith("SELECT") and not trimmed.startswith("WITH"):
        raise LLMError("Invalid SQL: must be a SELECT query", "INVALID_SQL", False)

    for pattern in DANGEROUS_SQL_PATTERNS:
        if pattern.search(sql):
            raise LLMError("Invalid SQL: contains disallowed operations", "INVALID_SQL", False)


# ============================================================
# Schema Formatting for LLM Prompt
# ============================================================


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

### Query Intent
**Default to single values.** Unless the user explicitly requests a breakdown/grouping, return ONE aggregate number.

### Aggregation Rule
When querying multi-dimension views, ALWAYS use SUM() on metric columns.

### Column Selection
1. Column comments show SYNONYMS - map user terms to actual column names
2. Look for the column whose synonyms best match what the user asked for
3. Business concept: AOV/average order/average ticket = what customer pays (total with tax+tips), not net sales

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


# ============================================================
# LLM Response Parsing
# ============================================================


def _get_current_date_context() -> str:
    """Get current date in readable format."""
    return datetime.now().strftime("%A, %B %d, %Y")


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


# ============================================================
# LLM Calling
# ============================================================


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

        date_min = schema.date_range.min_date
        date_max = schema.date_range.max_date
        response = await provider.complete(
            messages=[
                {
                    "role": "user",
                    "content": f"""Context:
- Current date: {current_date}
- Available data range: {schema.date_range.formatted} ({date_min} to {date_max})

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


# ============================================================
# Chart Type Validation
# ============================================================


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


# ============================================================
# Error Recovery
# ============================================================


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
    date_min = schema.date_range.min_date
    date_max = schema.date_range.max_date

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
- Available data range: {schema.date_range.formatted} ({date_min} to {date_max})

User query: "{user_query}"

{error_context}

Return the corrected JSON object.""",
            }
        ],
        system=system_prompt,
        max_tokens=1024,
    )

    return response.content


# ============================================================
# Public API
# ============================================================


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

            # Check for duplicate dimension values in bar/pie charts
            if data and result.chart_type in ("bar", "pie") and len(data) > 1:
                first_col = list(data[0].keys())[0]
                values = [row.get(first_col) for row in data]
                if len(values) != len(set(values)):
                    # Found duplicates - this indicates missing GROUP BY
                    duplicates = [v for v in set(values) if values.count(v) > 1]
                    error_msg = (
                        f"Result has duplicate values in '{first_col}' column: {duplicates[:3]}. "
                        f"This usually means missing GROUP BY. "
                        f"Use GROUP BY {first_col} and SUM() on metric columns."
                    )
                    if attempt < max_attempts - 1:
                        last_error = Exception(error_msg)
                        logger.warning(f"Duplicate dimension values detected: {error_msg}")
                        continue  # Retry with error context

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
