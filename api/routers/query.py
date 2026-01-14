import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException

from config import get_settings
from models import ErrorResponse, HealthResponse, QueryRequest, QueryResponse
from services import (
    DatabaseError,
    LLMError,
    execute_query,
    get_data_date_range,
    get_schema_info,
    process_query_with_retry,
    validate_chart_type,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["query"])


@router.get(
    "/query",
    response_model=HealthResponse,
    summary="Health Check",
    description="Returns the current health status and timestamp of the API.",
)
async def health_check():
    """
    Health check endpoint.

    Returns:
        HealthResponse: Status "ok" with current timestamp if the API is healthy.
    """
    return HealthResponse(status="ok", timestamp=datetime.now())


async def _process_query_internal(user_query: str) -> dict:
    """Internal query processing with LLM and database calls."""
    # Process with LLM and automatic retry on SQL errors
    llm_result, data = await process_query_with_retry(
        user_query,
        execute_fn=execute_query,
        max_attempts=2,
    )

    # Get date range and schema for chart validation
    date_range = await get_data_date_range()
    schema = await get_schema_info()

    # Validate and potentially correct chart type based on actual result shape
    validated_result = validate_chart_type(data, llm_result, schema)

    # Build drill-down config for response
    drill_down = None
    if validated_result.drill_down:
        drill_down = {
            "enabled": validated_result.drill_down.enabled,
            "type": validated_result.drill_down.type,
            "column": validated_result.drill_down.column,
            "summarySQL": validated_result.drill_down.summary_sql,
            "summaryLabel": validated_result.drill_down.summary_label,
        }

    return {
        "success": True,
        "query": user_query,
        "sql": validated_result.sql,
        "chartType": validated_result.chart_type,
        "title": validated_result.title,
        "xAxis": validated_result.x_axis,
        "yAxis": validated_result.y_axis,
        "dataKey": validated_result.data_key,
        "nameKey": validated_result.name_key,
        "valueFormat": validated_result.value_format,
        "summary": validated_result.summary,
        "data": data,
        "dataRange": date_range.formatted,
        "drillDown": drill_down,
    }


@router.post(
    "/query",
    response_model=QueryResponse,
    summary="Process Natural Language Query",
    description="""
    Accepts a natural language question about restaurant analytics and returns:
    - Generated SQL query
    - Query results data
    - Recommended chart type and configuration
    - Human-readable summary

    **Example queries:**
    - "Show me sales by location"
    - "What were the top 5 selling products?"
    - "Compare delivery vs dine-in sales"
    - "Graph daily sales trend"
    """,
    responses={
        200: {
            "description": "Query processed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "query": "Show me sales by location",
                        "sql": "SELECT location, SUM(sales_cents) FROM daily_sales GROUP BY 1",
                        "chartType": "bar",
                        "title": "Sales by Location",
                        "xAxis": "location",
                        "yAxis": "sales",
                        "valueFormat": "currency",
                        "summary": "Downtown leads with $12,450 in sales",
                        "data": [{"location": "Downtown", "sales": 1245000}],
                        "dataRange": "January 1-4, 2025",
                        "drillDown": {"enabled": True, "type": "location", "column": "location"},
                    }
                }
            },
        },
        400: {"model": ErrorResponse, "description": "Invalid input query"},
        503: {"model": ErrorResponse, "description": "LLM service unavailable"},
        504: {"model": ErrorResponse, "description": "Request timed out"},
    },
)
async def query(request: QueryRequest):
    """
    Process a natural language query and return SQL + visualization data.

    The query is processed through Claude to generate SQL, which is then executed
    against the database. The LLM also determines the appropriate chart type
    and configuration based on the query intent and result shape.

    Args:
        request: QueryRequest containing the natural language query string.

    Returns:
        QueryResponse with SQL, data, chart configuration, and summary.

    Raises:
        HTTPException 400: If the query is invalid or cannot be processed.
        HTTPException 503: If the LLM service is unavailable.
        HTTPException 504: If the request times out.
    """
    user_query = request.query.strip()
    settings = get_settings()

    try:
        # Wrap entire processing in a timeout
        result = await asyncio.wait_for(
            _process_query_internal(user_query),
            timeout=settings.api_timeout,
        )
        return result

    except asyncio.TimeoutError:
        logger.error(f"Query timed out after {settings.api_timeout}s: {user_query[:100]}")
        raise HTTPException(
            status_code=504,
            detail={
                "error": "Request timed out. Please try a simpler query.",
                "code": "TIMEOUT",
                "retryable": True,
            },
        )
    except LLMError as e:
        status_code = 400 if e.code == "INVALID_INPUT" else 503
        raise HTTPException(
            status_code=status_code,
            detail={"error": str(e), "code": e.code, "retryable": e.retryable},
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=500,
            detail={"error": str(e), "code": e.code, "retryable": e.retryable},
        )
