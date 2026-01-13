from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ChartType(str, Enum):
    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    TABLE = "table"
    METRIC = "metric"
    INFO = "info"


class ValueFormat(str, Enum):
    CURRENCY = "currency"
    NUMBER = "number"
    PERCENT = "percent"


class DrillDownType(str, Enum):
    LOCATION = "location"
    DATE = "date"
    PRODUCT = "product"
    CATEGORY = "category"
    SOURCE = "source"
    CHANNEL = "channel"


class DrillDownConfig(BaseModel):
    """Configuration for drill-down functionality."""

    enabled: bool
    type: DrillDownType | None = None
    column: str | None = None


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)


class QueryResponse(BaseModel):
    success: bool = True
    query: str
    sql: str
    chart_type: ChartType = Field(alias="chartType")
    title: str
    x_axis: str | None = Field(default=None, alias="xAxis")
    y_axis: str | None = Field(default=None, alias="yAxis")
    data_key: str | None = Field(default=None, alias="dataKey")
    name_key: str | None = Field(default=None, alias="nameKey")
    value_format: ValueFormat | None = Field(default=None, alias="valueFormat")
    summary: str
    data: list[dict[str, Any]]
    data_range: str = Field(alias="dataRange")
    drill_down: DrillDownConfig | None = Field(default=None, alias="drillDown")

    class Config:
        populate_by_name = True


class DrillDownParams(BaseModel):
    product: str | None = None
    location: str | None = None
    date: str | None = None
    source: str | None = None
    channel: str | None = None
    payment_type: str | None = None
    category: str | None = None
    limit: int = Field(default=50, ge=1, le=500)


class OrderDetail(BaseModel):
    order_id: str | None
    source: str | None
    channel: str | None
    location: str | None
    product: str | None
    category: str | None
    quantity: int | None
    unit_price_cents: int | None
    item_total_cents: int | None
    order_total_cents: int | None
    created_at: str | None


class DrillDownResponse(BaseModel):
    success: bool = True
    filters: DrillDownParams
    count: int
    orders: list[OrderDetail]


class ErrorResponse(BaseModel):
    error: str
    code: str
    retryable: bool = False


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
