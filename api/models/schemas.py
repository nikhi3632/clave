from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ChartType(str, Enum):
    """Supported chart/visualization types."""

    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    TABLE = "table"
    METRIC = "metric"
    INFO = "info"


class ValueFormat(str, Enum):
    """Value formatting options for display."""

    CURRENCY = "currency"
    NUMBER = "number"
    PERCENT = "percent"


class DrillDownType(str, Enum):
    """Dimension types for drill-down filtering."""

    LOCATION = "location"
    DATE = "date"
    PRODUCT = "product"
    CATEGORY = "category"
    SOURCE = "source"
    CHANNEL = "channel"
    PAYMENT_TYPE = "payment_type"


class DrillDownConfig(BaseModel):
    """Configuration for drill-down functionality on chart data points."""

    enabled: bool = Field(description="Whether drill-down is enabled")
    type: DrillDownType | None = Field(default=None, description="Dimension type to filter by")
    column: str | None = Field(default=None, description="Column with the filter value")
    summary_sql: str | None = Field(
        default=None, alias="summarySQL", description="SQL to calculate drill-down summary"
    )
    summary_label: str | None = Field(
        default=None, alias="summaryLabel", description="Display label for summary value"
    )

    class Config:
        populate_by_name = True


class QueryRequest(BaseModel):
    """Request payload for natural language query endpoint."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Natural language query about restaurant analytics",
        examples=["Show me sales by location", "What were the top 5 selling products?"],
    )


class QueryResponse(BaseModel):
    """Response from natural language query endpoint."""

    success: bool = Field(default=True, description="Whether the query was processed successfully")
    query: str = Field(description="The original natural language query")
    sql: str = Field(description="Generated SQL query")
    chart_type: ChartType = Field(alias="chartType", description="Recommended visualization type")
    title: str = Field(description="Human-readable title for the visualization")
    x_axis: str | None = Field(default=None, alias="xAxis", description="X-axis key")
    y_axis: str | None = Field(default=None, alias="yAxis", description="Y-axis key")
    data_key: str | None = Field(default=None, alias="dataKey", description="Value key (pie)")
    name_key: str | None = Field(default=None, alias="nameKey", description="Label key (pie)")
    value_format: ValueFormat | None = Field(
        default=None, alias="valueFormat", description="How to format values"
    )
    summary: str = Field(description="Human-readable summary of the data")
    data: list[dict[str, Any]] = Field(description="Query result data rows")
    data_range: str = Field(alias="dataRange", description="Date range of available data")
    drill_down: DrillDownConfig | None = Field(
        default=None, alias="drillDown", description="Drill-down configuration"
    )

    class Config:
        populate_by_name = True


class DrillDownParams(BaseModel):
    """Filter parameters for drill-down queries."""

    product: str | None = Field(default=None, description="Filter by product name")
    location: str | None = Field(default=None, description="Filter by location name")
    date: str | None = Field(default=None, description="Filter by date (YYYY-MM-DD)")
    source: str | None = Field(default=None, description="Filter by POS source")
    channel: str | None = Field(default=None, description="Filter by order channel")
    payment_type: str | None = Field(default=None, description="Filter by payment type")
    category: str | None = Field(default=None, description="Filter by product category")
    limit: int = Field(default=50, ge=1, le=500, description="Maximum items to return")


class OrderDetail(BaseModel):
    """Individual order item detail for drill-down view."""

    order_id: str | None = Field(description="External order ID from source system")
    source: str | None = Field(description="POS source (toast, doordash, square)")
    channel: str | None = Field(description="Order channel (dine_in, pickup, delivery)")
    location: str | None = Field(description="Location name")
    product: str | None = Field(description="Canonical product name")
    category: str | None = Field(description="Product category")
    quantity: int | None = Field(description="Quantity ordered")
    unit_price_cents: int | None = Field(description="Unit price in cents")
    item_total_cents: int | None = Field(description="Line item total in cents")
    order_total_cents: int | None = Field(description="Full order total in cents")
    created_at: str | None = Field(description="Order timestamp (ISO 8601)")


class DrillDownResponse(BaseModel):
    """Response from drill-down endpoint."""

    success: bool = Field(default=True, description="Whether the query succeeded")
    filters: DrillDownParams = Field(description="Applied filter parameters")
    count: int = Field(description="Number of items returned")
    orders: list[OrderDetail] = Field(description="Order item details")


class ErrorResponse(BaseModel):
    """Standard error response format."""

    error: str = Field(description="Human-readable error message")
    code: str = Field(description="Machine-readable error code")
    retryable: bool = Field(default=False, description="Whether the request can be retried")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(description="Health status ('ok' if healthy)")
    timestamp: datetime = Field(description="Current server timestamp")
