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


class Location(str, Enum):
    DOWNTOWN = "Downtown"
    AIRPORT = "Airport"
    MALL = "Mall"
    UNIVERSITY = "University"


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

    @property
    def total_cents(self) -> int:
        return self.quantity * self.unit_price_cents


class Order(BaseModel):
    """Validated order ready for loading."""

    external_id: str = Field(min_length=1)
    source: Source
    location: Location
    channel: Channel
    subtotal_cents: int = Field(ge=0)
    tax_cents: int = Field(ge=0, default=0)
    tip_cents: int = Field(ge=0, default=0)
    created_at: datetime
    items: list[OrderItem] = Field(min_length=1)

    @property
    def total_cents(self) -> int:
        return self.subtotal_cents + self.tax_cents + self.tip_cents


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
