"""Database service - pure database operations without LLM concerns."""

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Any

from supabase import Client, create_client

from config import get_settings

logger = logging.getLogger(__name__)


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


# ============================================================
# Raw Schema Data (no parsing, just raw query results)
# ============================================================


@dataclass
class RawSchemaData:
    """Raw schema data from database introspection (no interpretation)."""

    # Tables and their columns
    tables: dict[str, list[dict[str, str]]]  # table -> [{column, type}]

    # Views and their columns
    views: dict[str, list[dict[str, str]]]  # view -> [{column, type}]

    # Raw comments (unparsed)
    table_comments: dict[str, str]  # table_name -> comment
    view_comments: dict[str, str]  # view_name -> comment
    column_comments: dict[str, str]  # "table.column" -> comment
    schema_comment: str | None  # COMMENT ON SCHEMA public

    # Dimension values (raw lists)
    locations: list[str]
    sources: list[str]
    channels: list[str]
    categories: list[str]
    payment_types: list[str]
    products: list[str]

    # Date range
    date_range: DataDateRange


# Cache for raw schema
_raw_schema_cache: dict[str, tuple[RawSchemaData, float]] = {}


async def get_raw_schema() -> RawSchemaData:
    """Get raw schema data from database (no parsing/interpretation)."""
    cache_key = "raw_schema"
    settings = get_settings()

    if cache_key in _raw_schema_cache:
        cached, cached_at = _raw_schema_cache[cache_key]
        if time.time() - cached_at < settings.schema_cache_ttl:
            return cached

    client = get_supabase_client()

    # ============================================================
    # 1. Get dimension values
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

    products_sql = "SELECT DISTINCT canonical_name FROM products ORDER BY canonical_name"
    products_result = client.rpc(
        "execute_readonly_query", {"query_text": products_sql}
    ).execute()
    products = [r["canonical_name"] for r in (products_result.data or [])]

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

    # Get table-level comments
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
    # 3. Get materialized view schemas and comments
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

    views: dict[str, list[dict[str, str]]] = {}
    for row in views_result.data or []:
        view = row["view_name"]
        if view not in views:
            views[view] = []
        views[view].append({"column": row["column_name"], "type": row["data_type"]})

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

    # ============================================================
    # 4. Get column comments
    # ============================================================

    column_comments_sql = (
        "SELECT c.relname as table_name, a.attname as column_name, d.description "
        "FROM pg_catalog.pg_description d "
        "JOIN pg_catalog.pg_class c ON d.objoid = c.oid "
        "JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid AND a.attnum = d.objsubid "
        "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND d.objsubid > 0"
    )
    column_comments_result = client.rpc(
        "execute_readonly_query", {"query_text": column_comments_sql}
    ).execute()

    column_comments: dict[str, str] = {}
    for row in column_comments_result.data or []:
        key = f"{row['table_name']}.{row['column_name']}"
        column_comments[key] = row["description"]

    # ============================================================
    # 5. Get schema-level comment
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

    # ============================================================
    # 6. Build and cache RawSchemaData
    # ============================================================

    raw_schema = RawSchemaData(
        tables=tables,
        views=views,
        table_comments=table_comments,
        view_comments=view_comments,
        column_comments=column_comments,
        schema_comment=schema_comment,
        locations=locations,
        sources=sources,
        channels=channels,
        categories=categories,
        payment_types=payment_types,
        products=products,
        date_range=date_range,
    )

    _raw_schema_cache[cache_key] = (raw_schema, time.time())
    return raw_schema
