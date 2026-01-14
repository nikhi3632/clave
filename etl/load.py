"""Load transformed data into Supabase."""

from __future__ import annotations

import logging
import os
import time
from functools import wraps
from typing import TYPE_CHECKING, Callable, TypeVar

from supabase import Client, create_client

from config import get_config
from exceptions import LoadError
from models import Order, Product

if TYPE_CHECKING:
    from extract import ExtractedLocation

logger = logging.getLogger(__name__)

T = TypeVar("T")


# =============================================================================
# RETRY DECORATOR
# =============================================================================


def with_retry(
    max_retries: int | None = None,
    delay: float | None = None,
    exceptions: tuple = (Exception,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator that retries a function on failure.

    Args:
        max_retries: Maximum number of retry attempts.
        delay: Delay between retries in seconds.
        exceptions: Tuple of exceptions to catch and retry.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            config = get_config().database
            retries = max_retries if max_retries is not None else config.max_retries
            retry_delay = delay if delay is not None else config.retry_delay_seconds

            last_error: Exception | None = None

            for attempt in range(retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_error = e
                    if attempt < retries:
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{retries + 1}): {e}"
                        )
                        time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                    else:
                        logger.error(f"{func.__name__} failed after {retries + 1} attempts: {e}")

            raise last_error  # type: ignore

        return wrapper

    return decorator


# =============================================================================
# SUPABASE CLIENT
# =============================================================================


def get_supabase_client() -> Client:
    """
    Create Supabase client from environment variables.

    Raises:
        LoadError: If required environment variables are not set.
    """
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")

    if not url or not key:
        raise LoadError(
            "config",
            "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in environment",
        )

    return create_client(url, key)


# =============================================================================
# LOADER CLASS
# =============================================================================


class Loader:
    """Load data into Supabase with retry logic and batch operations."""

    def __init__(self, client: Client | None = None):
        """
        Initialize the loader.

        Args:
            client: Optional Supabase client (for testing).
        """
        self.client = client or get_supabase_client()
        self._location_cache: dict[str, str] = {}
        self._product_cache: dict[str, str] = {}

    # -------------------------------------------------------------------------
    # READ OPERATIONS
    # -------------------------------------------------------------------------

    @with_retry()
    def get_existing_products(self) -> list[str]:
        """
        Fetch existing canonical product names from database.

        Returns:
            List of canonical product names.
        """
        result = self.client.table("products").select("canonical_name").execute()
        products = [row["canonical_name"] for row in result.data] if result.data else []
        logger.debug(f"Loaded {len(products)} existing products from database")
        return products

    @with_retry()
    def get_location_names(self) -> list[str]:
        """
        Fetch location names from database.

        Returns:
            List of location names.
        """
        result = self.client.table("locations").select("name").execute()
        locations = [row["name"] for row in result.data] if result.data else []
        logger.debug(f"Loaded {len(locations)} locations from database")
        return locations

    @with_retry()
    def upsert_locations(self, locations: list[ExtractedLocation]) -> dict[str, str]:
        """
        Upsert locations to database.

        Args:
            locations: List of extracted locations from source files.

        Returns:
            Mapping of location name -> location UUID.
        """
        if not locations:
            return {}

        for loc in locations:
            data = {
                "name": loc.name,
                "street": loc.street,
                "city": loc.city,
                "state": loc.state,
                "zip_code": loc.zip_code,
                "timezone": loc.timezone,
            }
            self.client.table("locations").upsert(data, on_conflict="name").execute()
            logger.debug(f"Upserted location: {loc.name}")

        # Refresh cache and return mapping
        result = self.client.table("locations").select("id, name").execute()
        mapping = {row["name"]: row["id"] for row in result.data} if result.data else {}

        # Update cache
        self._location_cache.update(mapping)

        logger.info(f"Upserted {len(locations)} locations")
        return mapping

    # -------------------------------------------------------------------------
    # HELPER METHODS
    # -------------------------------------------------------------------------

    @with_retry()
    def _get_location_id(self, name: str) -> str:
        """
        Get location UUID by name.

        Args:
            name: Location name to look up.

        Returns:
            Location UUID.

        Raises:
            LoadError: If location is not found.
        """
        if name in self._location_cache:
            return self._location_cache[name]

        result = self.client.table("locations").select("id").eq("name", name).single().execute()

        if not result.data:
            raise LoadError("locations", f"Location not found: {name}")

        self._location_cache[name] = result.data["id"]
        return result.data["id"]

    @with_retry()
    def _get_or_create_product(self, product: Product) -> str:
        """
        Get or create product, return UUID.

        Args:
            product: Product to find or create.

        Returns:
            Product UUID.
        """
        if product.canonical_name in self._product_cache:
            return self._product_cache[product.canonical_name]

        # Try to find existing
        result = (
            self.client.table("products")
            .select("id")
            .eq("canonical_name", product.canonical_name)
            .execute()
        )

        if result.data:
            product_id = result.data[0]["id"]
        else:
            # Create new
            insert_result = (
                self.client.table("products")
                .insert(
                    {
                        "canonical_name": product.canonical_name,
                        "category": product.category,
                        "original_names": product.original_names,
                    }
                )
                .execute()
            )
            product_id = insert_result.data[0]["id"]
            logger.debug(f"Created product: {product.canonical_name}")

        self._product_cache[product.canonical_name] = product_id
        return product_id

    # -------------------------------------------------------------------------
    # BATCH OPERATIONS
    # -------------------------------------------------------------------------

    @with_retry()
    def load_products_batch(self, products: list[Product]) -> int:
        """
        Load products in batch with upsert.

        Args:
            products: List of products to load.

        Returns:
            Number of products loaded.
        """
        if not products:
            return 0

        config = get_config().database
        batch_size = config.batch_size
        loaded = 0

        for i in range(0, len(products), batch_size):
            batch = products[i : i + batch_size]
            batch_data = [
                {
                    "canonical_name": p.canonical_name,
                    "category": p.category,
                    "original_names": p.original_names,
                }
                for p in batch
            ]

            # Upsert to handle duplicates
            result = (
                self.client.table("products")
                .upsert(batch_data, on_conflict="canonical_name")
                .execute()
            )

            # Cache the IDs
            for row in result.data:
                self._product_cache[row["canonical_name"]] = row["id"]

            loaded += len(batch)
            logger.debug(f"Loaded products batch: {len(batch)}")

        logger.info(f"Loaded {loaded} products in batches")
        return loaded

    def load_products(self, products: list[Product]) -> int:
        """
        Load products (uses batch operation internally).

        Args:
            products: List of products to load.

        Returns:
            Number of products loaded.
        """
        return self.load_products_batch(products)

    # -------------------------------------------------------------------------
    # ORDER OPERATIONS
    # -------------------------------------------------------------------------

    @with_retry()
    def load_order(self, order: Order) -> str:
        """
        Load a single order and its items.

        Args:
            order: Order to load.

        Returns:
            Order UUID.

        Raises:
            LoadError: If order cannot be loaded.
        """
        try:
            location_id = self._get_location_id(order.location)  # location is now a string
        except LoadError:
            raise
        except Exception as e:
            raise LoadError("orders", f"Failed to get location: {e}")

        # Insert order with all fields
        order_data = {
            "external_id": order.external_id,
            "source": order.source.value,
            "location_id": location_id,
            "channel": order.channel.value,
            # Financial fields
            "sales_cents": order.sales_cents,
            "tax_cents": order.tax_cents,
            "tip_cents": order.tip_cents,
            "delivery_fee_cents": order.delivery_fee_cents,
            "service_fee_cents": order.service_fee_cents,
            "commission_cents": order.commission_cents,
            "merchant_payout_cents": order.merchant_payout_cents,
            "processing_fee_cents": order.processing_fee_cents,
            # Order status & timing
            "order_status": order.order_status,
            "pickup_time": order.pickup_time.isoformat() if order.pickup_time else None,
            "delivery_time": order.delivery_time.isoformat() if order.delivery_time else None,
            "closed_at": order.closed_at.isoformat() if order.closed_at else None,
            # Order flags
            "is_catering": order.is_catering,
            "contains_alcohol": order.contains_alcohol,
            "voided": order.voided,
            "deleted": order.deleted,
            "refund_status": order.refund_status,
            # Payment info
            "payment_type": order.payment_type,
            "card_type": order.card_type,
            # Toast-specific
            "revenue_center": order.revenue_center,
            "server_name": order.server_name,
            "check_number": order.check_number,
            "order_source": order.order_source,
            "business_date": order.business_date,
            # Delivery address
            "delivery_street": order.delivery_street,
            "delivery_city": order.delivery_city,
            "delivery_state": order.delivery_state,
            "delivery_zip": order.delivery_zip,
            # Timestamps
            "created_at": order.created_at.isoformat(),
        }

        try:
            # Use upsert to handle duplicates
            result = (
                self.client.table("orders")
                .upsert(order_data, on_conflict="source,external_id")
                .execute()
            )

            order_id = result.data[0]["id"]

            # Delete existing items (in case of re-run)
            self.client.table("order_items").delete().eq("order_id", order_id).execute()

            # Insert items
            items_data = []
            for item in order.items:
                # Get product ID
                product = Product(
                    canonical_name=item.canonical_name or item.product_name,
                    category=item.category,
                    original_names=[item.product_name],
                )
                product_id = self._get_or_create_product(product)

                items_data.append(
                    {
                        "order_id": order_id,
                        "product_id": product_id,
                        "quantity": item.quantity,
                        "unit_price_cents": item.unit_price_cents,
                        "modifiers": [m.model_dump() for m in item.modifiers],
                        "original_name": item.original_name,
                        "special_instructions": item.special_instructions,
                    }
                )

            if items_data:
                self.client.table("order_items").insert(items_data).execute()

            return order_id

        except Exception as e:
            raise LoadError("orders", f"Failed to load order {order.external_id}: {e}")

    @with_retry()
    def load_orders_batch(self, orders: list[Order]) -> tuple[int, list[str]]:
        """
        Load orders in batch.

        Args:
            orders: List of orders to load.

        Returns:
            Tuple of (loaded_count, list of errors).
        """
        loaded = 0
        errors: list[str] = []

        for order in orders:
            try:
                self.load_order(order)
                loaded += 1
            except LoadError as e:
                errors.append(str(e))
            except Exception as e:
                errors.append(f"Order {order.external_id}: {e}")

        logger.info(f"Loaded {loaded}/{len(orders)} orders")
        if errors:
            logger.warning(f"Failed to load {len(errors)} orders")

        return loaded, errors

    # -------------------------------------------------------------------------
    # MAINTENANCE
    # -------------------------------------------------------------------------

    @with_retry()
    def refresh_views(self) -> None:
        """Refresh materialized views."""
        logger.info("Refreshing materialized views...")
        self.client.rpc("refresh_analytics_views").execute()
        logger.info("Materialized views refreshed")

    @with_retry()
    def cleanup_orphan_products(self) -> int:
        """
        Delete products that have no order_items.

        This cleans up stale products that were superseded by LLM normalization
        (e.g., "Lg Coke" superseded by "Coca-Cola").

        Returns:
            Number of products deleted.
        """
        # Get all product IDs
        all_products = self.client.table("products").select("id").execute()
        all_ids = {row["id"] for row in (all_products.data or [])}

        if not all_ids:
            return 0

        # Get all referenced product IDs from order_items
        referenced = self.client.table("order_items").select("product_id").execute()
        referenced_ids = {row["product_id"] for row in (referenced.data or [])}

        # Find orphans (products with no order_items)
        orphan_ids = list(all_ids - referenced_ids)

        if not orphan_ids:
            return 0

        # Delete orphans
        self.client.table("products").delete().in_("id", orphan_ids).execute()

        logger.info(f"Cleaned up {len(orphan_ids)} orphan products")
        return len(orphan_ids)

    def close(self) -> None:
        """
        Clean up resources and close connections.

        This should be called when shutting down the ETL pipeline gracefully.
        """
        logger.debug("Closing loader resources...")

        # Clear caches to free memory
        self._location_cache.clear()
        self._product_cache.clear()

        # The Supabase client doesn't have an explicit close method,
        # but we can help garbage collection by removing references
        if hasattr(self, "client"):
            # Close any underlying HTTP session if available
            if hasattr(self.client, "_session") and self.client._session:
                try:
                    self.client._session.close()
                except Exception as e:
                    logger.debug(f"Error closing HTTP session: {e}")

            # Clear client reference
            self.client = None  # type: ignore

        logger.debug("Loader resources closed")

    def __enter__(self) -> "Loader":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit with cleanup."""
        self.close()
