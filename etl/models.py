"""Pydantic models for ETL validation."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

# =============================================================================
# ENUMS
# =============================================================================


class Source(str, Enum):
    TOAST = "toast"
    DOORDASH = "doordash"
    SQUARE = "square"


class Channel(str, Enum):
    DINE_IN = "dine_in"
    PICKUP = "pickup"
    DELIVERY = "delivery"


# Location is now dynamic - extracted from source data during ETL
# No hardcoded enum; locations are created in DB from source files


# =============================================================================
# ORDER MODELS
# =============================================================================


class Modifier(BaseModel):
    """Order item modifier."""

    name: str
    price_cents: int = 0


class OrderItem(BaseModel):
    """Validated order item ready for loading."""

    product_name: str = Field(min_length=1)
    canonical_name: str | None = None
    category: str | None = None
    quantity: int = Field(ge=1, default=1)
    unit_price_cents: int = Field(ge=0)
    modifiers: list[Modifier] = Field(default_factory=list)
    match_confidence: float | None = None
    match_method: str | None = None
    # Additional item details
    original_name: str | None = None  # Name before normalization
    special_instructions: str | None = None  # Customer notes

    @property
    def total_cents(self) -> int:
        return self.quantity * self.unit_price_cents


class Order(BaseModel):
    """Validated order ready for loading."""

    external_id: str = Field(min_length=1)
    source: Source
    location: str = Field(min_length=1)  # Dynamic location name from source data
    channel: Channel
    # Financial fields
    sales_cents: int = Field(ge=0)
    tax_cents: int = Field(ge=0, default=0)
    tip_cents: int = Field(ge=0, default=0)
    # Delivery platform fees (DoorDash)
    delivery_fee_cents: int = Field(ge=0, default=0)
    service_fee_cents: int = Field(ge=0, default=0)
    commission_cents: int = Field(ge=0, default=0)
    merchant_payout_cents: int = Field(ge=0, default=0)
    processing_fee_cents: int = Field(ge=0, default=0)
    # Order status & timing
    order_status: str | None = None
    pickup_time: datetime | None = None
    delivery_time: datetime | None = None
    closed_at: datetime | None = None
    # Order flags
    is_catering: bool = False
    contains_alcohol: bool = False
    voided: bool = False
    deleted: bool = False
    refund_status: str | None = None
    # Payment info
    payment_type: str | None = None
    card_type: str | None = None
    # Toast-specific
    revenue_center: str | None = None
    server_name: str | None = None
    check_number: str | None = None
    order_source: str | None = None
    business_date: str | None = None
    # Delivery address (for delivery orders)
    delivery_street: str | None = None
    delivery_city: str | None = None
    delivery_state: str | None = None
    delivery_zip: str | None = None
    # Timestamps
    created_at: datetime
    items: list[OrderItem] = Field(min_length=1)

    @property
    def total_cents(self) -> int:
        return self.sales_cents + self.tax_cents + self.tip_cents


class Product(BaseModel):
    """Canonical product for products table."""

    canonical_name: str = Field(min_length=1)
    category: str | None = None
    original_names: list[str] = Field(default_factory=list)


class TransformResult(BaseModel):
    """Result of transforming a single record."""

    success: bool
    order: Order | None = None
    error: str | None = None
    warnings: list[str] = Field(default_factory=list)
    changes: list[str] = Field(default_factory=list)
