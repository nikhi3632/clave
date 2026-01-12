import asyncio
import re
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from supabase import Client, create_client

from config import get_settings


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


MAX_RETRIES = 2
RETRY_DELAY = 0.5


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
        if "connection" in error_msg or "timeout" in error_msg or "network" in error_msg:
            if retry_count < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY * (retry_count + 1))
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
            raise DatabaseError(
                "Query references invalid table or column. Please try a different question.",
                "INVALID_REFERENCE",
                False,
            )

        raise DatabaseError(f"Query failed: {e}", "QUERY_ERROR", False)


@dataclass
class DataDateRange:
    min_date: str
    max_date: str
    formatted: str


# Cache for date range
_date_range_cache: dict[str, tuple[DataDateRange, float]] = {}
DATE_RANGE_CACHE_TTL = 300  # 5 minutes


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

    if cache_key in _date_range_cache:
        cached, cached_at = _date_range_cache[cache_key]
        if time.time() - cached_at < DATE_RANGE_CACHE_TTL:
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

    except Exception:
        pass

    # Fallback
    return DataDateRange(
        min_date="2025-01-01",
        max_date="2025-01-04",
        formatted="January 1-4, 2025",
    )
