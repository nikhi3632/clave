import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from supabase import Client, create_client

from config import get_settings

logger = logging.getLogger(__name__)


# ============================================================
# Comment Parsing Utilities
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
# Structured Metadata Dataclasses
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


class DatabaseError(Exception):
    """Custom error for database operations."""

    def __init__(self, message: str, code: str, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


# Dangerous SQL patterns to block
DANGEROUS_SQL_PATTERNS = [
    re.compile(r"\b(DROP|DELETE|INSERT|UPDATE|ALTER|TRUNCATE|CREATE|GRANT|REVOKE)\b", re.I),
    re.compile(r"\b(EXEC|EXECUTE|CALL)\b", re.I),
    re.compile(r";\s*\w", re.I),  # Multiple statements
    re.compile(r"--"),  # SQL comments
    re.compile(r"/\*"),  # Block comments
]


@lru_cache
def get_supabase_client() -> Client:
    """Get or create Supabase client (cached)."""
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_anon_key)


async def execute_query(sql: str, retry_count: int = 0) -> list[dict[str, Any]]:
    """Execute a read-only SQL query with validation and retry logic."""
    # Validate SQL
    normalized_sql = sql.strip().upper()
    if not normalized_sql.startswith("SELECT") and not normalized_sql.startswith("WITH"):
        raise DatabaseError("Only SELECT queries are allowed", "INVALID_QUERY", False)

    for pattern in DANGEROUS_SQL_PATTERNS:
        if pattern.search(sql):
            raise DatabaseError("Query contains disallowed patterns", "INVALID_QUERY", False)

    try:
        client = get_supabase_client()
        result = client.rpc("execute_readonly_query", {"query_text": sql}).execute()

        if result.data is None:
            return []

        return result.data

    except Exception as e:
        error_msg = str(e).lower()

        # Connection errors are retryable
        settings = get_settings()
        if "connection" in error_msg or "timeout" in error_msg or "network" in error_msg:
            if retry_count < settings.db_max_retries:
                await asyncio.sleep(settings.db_retry_delay * (retry_count + 1))
                return await execute_query(sql, retry_count + 1)
            raise DatabaseError(
                "Unable to connect to database. Please try again.",
                "CONNECTION_ERROR",
                True,
            )

        # Syntax errors
        if "syntax" in error_msg or "parse" in error_msg:
            raise DatabaseError(
                "The generated query has a syntax error. Please try rephrasing your question.",
                "SYNTAX_ERROR",
                False,
            )

        # Permission errors
        if "permission" in error_msg or "denied" in error_msg:
            raise DatabaseError("Access denied for this query", "PERMISSION_ERROR", False)

        # Column/table not found
        if "does not exist" in error_msg or "not found" in error_msg:
            logger.error(f"Invalid reference in query: {e}")
            logger.error(f"SQL that failed: {sql}")
            raise DatabaseError(
                "Query references invalid data. Please try a different question.",
                "INVALID_REFERENCE",
                False,
            )

        # Log the raw error for debugging, return friendly message
        logger.error(f"Database query failed: {e}")
        raise DatabaseError(
            "Unable to execute query. Please try again or rephrase your question.",
            "QUERY_ERROR",
            True,
        )


@dataclass
class DataDateRange:
    min_date: str
    max_date: str
    formatted: str


# Cache for date range
_date_range_cache: dict[str, tuple[DataDateRange, float]] = {}


def _format_date_range(min_date: str, max_date: str) -> str:
    """Format date range for human-readable display."""
    from datetime import datetime

    min_dt = datetime.strptime(min_date, "%Y-%m-%d")
    max_dt = datetime.strptime(max_date, "%Y-%m-%d")

    min_month = min_dt.strftime("%B")
    max_month = max_dt.strftime("%B")
    min_day = min_dt.day
    max_day = max_dt.day
    min_year = min_dt.year
    max_year = max_dt.year

    if min_month == max_month and min_year == max_year:
        return f"{min_month} {min_day}-{max_day}, {min_year}"

    if min_year == max_year:
        return f"{min_month} {min_day} - {max_month} {max_day}, {min_year}"

    return f"{min_month} {min_day}, {min_year} - {max_month} {max_day}, {max_year}"


async def get_data_date_range() -> DataDateRange:
    """Get the actual date range of available data."""
    cache_key = "date_range"

    settings = get_settings()
    if cache_key in _date_range_cache:
        cached, cached_at = _date_range_cache[cache_key]
        if time.time() - cached_at < settings.date_range_cache_ttl:
            return cached

    try:
        client = get_supabase_client()
        sql = "SELECT MIN(date)::text as min_date, MAX(date)::text as max_date FROM daily_sales"
        result = client.rpc("execute_readonly_query", {"query_text": sql}).execute()

        if result.data and len(result.data) > 0:
            min_date = result.data[0]["min_date"]
            max_date = result.data[0]["max_date"]
            date_range = DataDateRange(
                min_date=min_date,
                max_date=max_date,
                formatted=_format_date_range(min_date, max_date),
            )
            _date_range_cache[cache_key] = (date_range, time.time())
            return date_range

    except Exception as e:
        logger.warning(f"Failed to fetch date range, using fallback: {e}")

    # Fallback
    return DataDateRange(
        min_date="2025-01-01",
        max_date="2025-01-04",
        formatted="January 1-4, 2025",
    )


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


# Cache for schema info
_schema_cache: dict[str, tuple[SchemaInfo, float]] = {}


async def get_schema_info() -> SchemaInfo:
    """Get dynamic schema information from the database."""
    cache_key = "schema"
    settings = get_settings()

    if cache_key in _schema_cache:
        cached, cached_at = _schema_cache[cache_key]
        if time.time() - cached_at < settings.schema_cache_ttl:
            return cached

    client = get_supabase_client()

    # ============================================================
    # 1. Get legacy dimension values (for backward compatibility)
    # ============================================================

    locations_sql = "SELECT DISTINCT name FROM locations ORDER BY name"
    locations_result = client.rpc("execute_readonly_query", {"query_text": locations_sql}).execute()
    locations = [r["name"] for r in (locations_result.data or [])]

    sources_sql = "SELECT DISTINCT source FROM orders ORDER BY source"
    sources_result = client.rpc("execute_readonly_query", {"query_text": sources_sql}).execute()
    sources = [r["source"] for r in (sources_result.data or [])]

    channels_sql = "SELECT DISTINCT channel FROM orders ORDER BY channel"
    channels_result = client.rpc("execute_readonly_query", {"query_text": channels_sql}).execute()
    channels = [r["channel"] for r in (channels_result.data or [])]

    categories_sql = (
        "SELECT DISTINCT category FROM products "
        "WHERE category IS NOT NULL ORDER BY category"
    )
    categories_result = client.rpc(
        "execute_readonly_query", {"query_text": categories_sql}
    ).execute()
    categories = [r["category"] for r in (categories_result.data or [])]

    payment_types_sql = (
        "SELECT DISTINCT payment_type FROM orders "
        "WHERE payment_type IS NOT NULL ORDER BY payment_type"
    )
    payment_types_result = client.rpc(
        "execute_readonly_query", {"query_text": payment_types_sql}
    ).execute()
    payment_types = [r["payment_type"] for r in (payment_types_result.data or [])]

    # Get date range
    date_range = await get_data_date_range()

    # ============================================================
    # 2. Get table schemas and comments
    # ============================================================

    tables_sql = (
        "SELECT table_name, column_name, data_type "
        "FROM information_schema.columns "
        "WHERE table_schema = 'public' "
        "AND table_name IN ('orders', 'order_items', 'products', 'locations') "
        "ORDER BY table_name, ordinal_position"
    )
    tables_result = client.rpc("execute_readonly_query", {"query_text": tables_sql}).execute()

    tables: dict[str, list[dict[str, str]]] = {}
    for row in tables_result.data or []:
        table = row["table_name"]
        if table not in tables:
            tables[table] = []
        tables[table].append({"column": row["column_name"], "type": row["data_type"]})

    # Get table-level comments (for dimension discovery)
    table_comments_sql = (
        "SELECT c.relname as table_name, d.description "
        "FROM pg_catalog.pg_description d "
        "JOIN pg_catalog.pg_class c ON d.objoid = c.oid "
        "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relkind = 'r' AND d.objsubid = 0"
    )
    table_comments_result = client.rpc(
        "execute_readonly_query", {"query_text": table_comments_sql}
    ).execute()

    table_comments: dict[str, str] = {}
    for row in table_comments_result.data or []:
        table_comments[row["table_name"]] = row["description"]

    # ============================================================
    # 3. Discover dimensions from table comments
    # ============================================================

    discovered_dimensions: dict[str, DimensionInfo] = {}
    for table_name, comment in table_comments.items():
        dims = parse_dimension_table_comment(table_name, comment)
        for dim in dims:
            discovered_dimensions[dim.name] = dim

    # Fill in dimension values
    if "location" in discovered_dimensions:
        discovered_dimensions["location"].values = locations
    if "product" in discovered_dimensions:
        discovered_dimensions["product"].values = [
            r["canonical_name"]
            for r in (
                client.rpc(
                    "execute_readonly_query",
                    {"query_text": "SELECT DISTINCT canonical_name FROM products"},
                ).execute().data or []
            )
        ]
    if "category" in discovered_dimensions:
        discovered_dimensions["category"].values = categories

    # Add implicit dimensions (source, channel) that aren't from dimension tables
    discovered_dimensions["source"] = DimensionInfo(
        name="source",
        table="orders",
        display_column="source",
        filter_pattern="WHERE source = :filter_value",
        values=sources,
    )
    discovered_dimensions["channel"] = DimensionInfo(
        name="channel",
        table="orders",
        display_column="channel",
        filter_pattern="WHERE channel = :filter_value",
        values=channels,
    )

    # ============================================================
    # 4. Get materialized view schemas and comments
    # ============================================================

    views_sql = (
        "SELECT c.relname as view_name, a.attname as column_name, "
        "pg_catalog.format_type(a.atttypid, a.atttypmod) as data_type "
        "FROM pg_catalog.pg_class c "
        "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
        "JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid "
        "WHERE c.relkind = 'm' AND n.nspname = 'public' "
        "AND a.attnum > 0 AND NOT a.attisdropped "
        "ORDER BY c.relname, a.attnum"
    )
    views_result = client.rpc("execute_readonly_query", {"query_text": views_sql}).execute()

    raw_views: dict[str, list[dict[str, str]]] = {}
    for row in views_result.data or []:
        view = row["view_name"]
        if view not in raw_views:
            raw_views[view] = []
        raw_views[view].append({"column": row["column_name"], "type": row["data_type"]})

    # Get view-level comments
    view_comments_sql = (
        "SELECT c.relname as view_name, d.description "
        "FROM pg_catalog.pg_description d "
        "JOIN pg_catalog.pg_class c ON d.objoid = c.oid "
        "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relkind = 'm' AND d.objsubid = 0"
    )
    view_comments_result = client.rpc(
        "execute_readonly_query", {"query_text": view_comments_sql}
    ).execute()

    view_comments: dict[str, str] = {}
    for row in view_comments_result.data or []:
        view_comments[row["view_name"]] = row["description"]

    # Parse view metadata and filter out internal views
    parsed_views: dict[str, ViewMetadata] = {}
    for view_name, columns in raw_views.items():
        comment = view_comments.get(view_name)
        metadata = parse_view_comment(view_name, comment, columns)
        if metadata.is_analytics:
            parsed_views[view_name] = metadata

    # ============================================================
    # 5. Get column comments and parse synonyms
    # ============================================================

    comments_sql = (
        "SELECT c.relname as table_name, a.attname as column_name, d.description "
        "FROM pg_catalog.pg_description d "
        "JOIN pg_catalog.pg_class c ON d.objoid = c.oid "
        "JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid AND a.attnum = d.objsubid "
        "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND d.objsubid > 0"
    )
    comments_result = client.rpc(
        "execute_readonly_query", {"query_text": comments_sql}
    ).execute()

    column_comments: dict[str, str] = {}
    parsed_columns: dict[str, ColumnInfo] = {}

    for row in comments_result.data or []:
        key = f"{row['table_name']}.{row['column_name']}"
        comment = row["description"]
        column_comments[key] = comment

        # Parse synonyms from comment
        parsed = parse_column_comment(comment)

        # Get column type from view or table
        col_type = "unknown"
        if row["table_name"] in raw_views:
            for col in raw_views[row["table_name"]]:
                if col["column"] == row["column_name"]:
                    col_type = col["type"]
                    break
        elif row["table_name"] in tables:
            for col in tables[row["table_name"]]:
                if col["column"] == row["column_name"]:
                    col_type = col["type"]
                    break

        parsed_columns[key] = ColumnInfo(
            name=row["column_name"],
            data_type=col_type,
            synonyms=parsed["synonyms"],
            note=parsed.get("note"),
        )

    # ============================================================
    # 6. Get schema conventions
    # ============================================================

    schema_comment_sql = (
        "SELECT d.description FROM pg_catalog.pg_description d "
        "JOIN pg_catalog.pg_namespace n ON d.objoid = n.oid "
        "WHERE n.nspname = 'public' AND d.objsubid = 0"
    )
    schema_comment_result = client.rpc(
        "execute_readonly_query", {"query_text": schema_comment_sql}
    ).execute()

    schema_comment = None
    if schema_comment_result.data:
        schema_comment = schema_comment_result.data[0].get("description")

    conventions = parse_schema_conventions(schema_comment)

    # ============================================================
    # 7. Build and cache SchemaInfo
    # ============================================================

    schema_info = SchemaInfo(
        views=parsed_views,
        dimensions=discovered_dimensions,
        columns=parsed_columns,
        conventions=conventions,
        date_range=date_range,
        tables=tables,
        column_comments=column_comments,
        view_comments=view_comments,
        # Legacy fields for backward compatibility
        locations=locations,
        sources=sources,
        channels=channels,
        categories=categories,
        payment_types=payment_types,
    )

    _schema_cache[cache_key] = (schema_info, time.time())
    return schema_info
