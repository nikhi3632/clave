import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException

from models import ErrorResponse, HealthResponse, QueryRequest, QueryResponse
from services import (
    DatabaseError,
    LLMError,
    execute_query,
    get_data_date_range,
    process_query,
    validate_chart_type,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["query"])

# API-level timeout (LLM + DB combined)
API_TIMEOUT_SECONDS = 30


@router.get("/query", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="ok", timestamp=datetime.now())


async def _process_query_internal(user_query: str) -> dict:
    """Internal query processing with LLM and database calls."""
    # Process with LLM
    llm_result = await process_query(user_query)

    # Execute SQL and get date range
    data = await execute_query(llm_result.sql)
    date_range = await get_data_date_range()

    # Validate and potentially correct chart type based on actual result shape
    validated_result = validate_chart_type(data, llm_result)

    # Build drill-down config for response
    drill_down = None
    if validated_result.drill_down:
        drill_down = {
            "enabled": validated_result.drill_down.enabled,
            "type": validated_result.drill_down.type,
            "column": validated_result.drill_down.column,
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
    responses={400: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def query(request: QueryRequest):
    """Process a natural language query and return SQL + visualization data."""
    user_query = request.query.strip()

    try:
        # Wrap entire processing in a timeout
        result = await asyncio.wait_for(
            _process_query_internal(user_query),
            timeout=API_TIMEOUT_SECONDS,
        )
        return result

    except asyncio.TimeoutError:
        logger.error(f"Query timed out after {API_TIMEOUT_SECONDS}s: {user_query[:100]}")
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
        status_code = 503 if e.code == "CONFIG_ERROR" else 500
        raise HTTPException(
            status_code=status_code,
            detail={"error": str(e), "code": e.code, "retryable": e.retryable},
        )
