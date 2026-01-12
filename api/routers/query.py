from datetime import datetime

from fastapi import APIRouter, HTTPException

from models import ErrorResponse, HealthResponse, QueryRequest, QueryResponse
from services import DatabaseError, LLMError, execute_query, get_data_date_range, process_query

router = APIRouter(prefix="/api", tags=["query"])


@router.get("/query", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="ok", timestamp=datetime.now())


@router.post(
    "/query",
    response_model=QueryResponse,
    responses={400: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def query(request: QueryRequest):
    """Process a natural language query and return SQL + visualization data."""
    user_query = request.query.strip()

    # Process with LLM
    try:
        llm_result = await process_query(user_query)
    except LLMError as e:
        status_code = 400 if e.code == "INVALID_INPUT" else 503
        raise HTTPException(
            status_code=status_code,
            detail={"error": str(e), "code": e.code, "retryable": e.retryable},
        )

    # Execute SQL and get date range
    try:
        data = await execute_query(llm_result.sql)
        date_range = await get_data_date_range()
    except DatabaseError as e:
        status_code = 503 if e.code == "CONFIG_ERROR" else 500
        raise HTTPException(
            status_code=status_code,
            detail={"error": str(e), "code": e.code, "retryable": e.retryable},
        )

    return {
        "success": True,
        "query": user_query,
        "sql": llm_result.sql,
        "chartType": llm_result.chart_type,
        "title": llm_result.title,
        "xAxis": llm_result.x_axis,
        "yAxis": llm_result.y_axis,
        "dataKey": llm_result.data_key,
        "nameKey": llm_result.name_key,
        "valueFormat": llm_result.value_format,
        "summary": llm_result.summary,
        "data": data,
        "dataRange": date_range.formatted,
    }
