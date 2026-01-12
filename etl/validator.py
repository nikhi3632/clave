"""ETL data validation and anomaly detection."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from supabase import Client

logger = logging.getLogger(__name__)

# Thresholds for anomaly detection
MAX_ORDER_CENTS = 50000  # $500 max per order
MAX_ITEM_CENTS = 20000  # $200 max per item
MIN_ITEM_CENTS = 50  # $0.50 min per item (avoid zero/near-zero)
MAX_QUANTITY = 50  # Max items per line
MAX_FUTURE_HOURS = 24  # Orders can't be more than 24h in future


@dataclass
class Anomaly:
    """Detected data anomaly."""

    source: str
    severity: str  # 'info', 'warning', 'error'
    anomaly_type: str
    description: str
    external_id: str | None = None
    product_name: str | None = None
    location: str | None = None
    expected_value: float | None = None
    actual_value: float | None = None
    raw_data: dict | None = None


@dataclass
class ValidationStats:
    """Statistics from validation run."""

    total_validated: int = 0
    errors: int = 0
    warnings: int = 0
    info: int = 0


@dataclass
class Validator:
    """Validate ETL data and detect anomalies."""

    run_id: str
    client: Client
    anomalies: list[Anomaly] = field(default_factory=list)
    stats: ValidationStats = field(default_factory=ValidationStats)
    _price_cache: dict[str, list[int]] = field(default_factory=dict)

    def validate_order(self, order: Any, source: str) -> bool:
        """
        Validate an order and its items.

        Args:
            order: Order object with items.
            source: Source system (toast, doordash, square).

        Returns:
            True if order is valid (may have warnings), False if critical error.
        """
        self.stats.total_validated += 1
        is_valid = True

        # Check order total
        if order.subtotal_cents > MAX_ORDER_CENTS:
            self._add_anomaly(Anomaly(
                source=source,
                severity="warning",
                anomaly_type="high_order_total",
                description=f"Order total ${order.subtotal_cents/100:.2f} exceeds ${MAX_ORDER_CENTS/100:.0f}",
                external_id=order.external_id,
                expected_value=MAX_ORDER_CENTS,
                actual_value=order.subtotal_cents,
            ))

        # Check for negative amounts
        if order.subtotal_cents < 0:
            self._add_anomaly(Anomaly(
                source=source,
                severity="error",
                anomaly_type="negative_amount",
                description="Order has negative subtotal",
                external_id=order.external_id,
                actual_value=order.subtotal_cents,
            ))
            is_valid = False

        # Check order date
        if order.created_at:
            now = datetime.now(order.created_at.tzinfo) if order.created_at.tzinfo else datetime.now()
            if order.created_at > now + timedelta(hours=MAX_FUTURE_HOURS):
                self._add_anomaly(Anomaly(
                    source=source,
                    severity="error",
                    anomaly_type="future_date",
                    description=f"Order date {order.created_at} is in the future",
                    external_id=order.external_id,
                ))
                is_valid = False

        # Validate each item
        for item in order.items:
            self._validate_item(item, order.external_id, source)

        return is_valid

    def _validate_item(self, item: Any, order_id: str, source: str) -> None:
        """Validate a single order item."""
        # Check price bounds
        if item.unit_price_cents < MIN_ITEM_CENTS:
            self._add_anomaly(Anomaly(
                source=source,
                severity="warning",
                anomaly_type="low_item_price",
                description=f"Item price ${item.unit_price_cents/100:.2f} below minimum",
                external_id=order_id,
                product_name=item.product_name,
                expected_value=MIN_ITEM_CENTS,
                actual_value=item.unit_price_cents,
            ))

        if item.unit_price_cents > MAX_ITEM_CENTS:
            self._add_anomaly(Anomaly(
                source=source,
                severity="warning",
                anomaly_type="high_item_price",
                description=f"Item price ${item.unit_price_cents/100:.2f} exceeds maximum",
                external_id=order_id,
                product_name=item.product_name,
                expected_value=MAX_ITEM_CENTS,
                actual_value=item.unit_price_cents,
            ))

        # Check quantity
        if item.quantity > MAX_QUANTITY:
            self._add_anomaly(Anomaly(
                source=source,
                severity="warning",
                anomaly_type="high_quantity",
                description=f"Item quantity {item.quantity} exceeds maximum",
                external_id=order_id,
                product_name=item.product_name,
                expected_value=MAX_QUANTITY,
                actual_value=item.quantity,
            ))

        # Track prices for variance detection
        name = item.product_name.lower()
        if name not in self._price_cache:
            self._price_cache[name] = []
        self._price_cache[name].append(item.unit_price_cents)

    def check_price_variance(self) -> None:
        """Check for price variance across products after all orders processed."""
        for product, prices in self._price_cache.items():
            if len(prices) < 2:
                continue

            min_price = min(prices)
            max_price = max(prices)

            # Flag if max > 2x min (same as view)
            if min_price > 0 and max_price > min_price * 2:
                self._add_anomaly(Anomaly(
                    source="all",
                    severity="info",
                    anomaly_type="price_variance",
                    description=f"Price varies ${min_price/100:.2f}-${max_price/100:.2f}",
                    product_name=product,
                    expected_value=min_price,
                    actual_value=max_price,
                ))

    def _add_anomaly(self, anomaly: Anomaly) -> None:
        """Add an anomaly and update stats."""
        self.anomalies.append(anomaly)
        if anomaly.severity == "error":
            self.stats.errors += 1
        elif anomaly.severity == "warning":
            self.stats.warnings += 1
        else:
            self.stats.info += 1

    def save_anomalies(self) -> int:
        """
        Save detected anomalies to database.

        Returns:
            Number of anomalies saved.
        """
        if not self.anomalies:
            return 0

        records = []
        for a in self.anomalies:
            records.append({
                "run_id": self.run_id,
                "source": a.source,
                "severity": a.severity,
                "anomaly_type": a.anomaly_type,
                "description": a.description,
                "external_id": a.external_id,
                "product_name": a.product_name,
                "location": a.location,
                "expected_value": a.expected_value,
                "actual_value": a.actual_value,
                "raw_data": a.raw_data,
            })

        try:
            self.client.table("etl_anomalies").insert(records).execute()
            logger.info(f"Saved {len(records)} anomalies to database")
            return len(records)
        except Exception as e:
            logger.error(f"Failed to save anomalies: {e}")
            return 0

    def log_summary(self) -> None:
        """Log validation summary."""
        logger.info(
            f"Validation: {self.stats.total_validated} orders, "
            f"{self.stats.errors} errors, "
            f"{self.stats.warnings} warnings, "
            f"{self.stats.info} info"
        )
        if self.stats.errors > 0:
            logger.warning(f"ETL had {self.stats.errors} validation errors!")
