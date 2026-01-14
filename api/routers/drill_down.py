import asyncio
import logging
import re

from fastapi import APIRouter, HTTPException, Query

from config import get_settings
from services import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["drill-down"])


def _execute_summary_sql(summary_sql: str, filter_value: str) -> int | None:
    """Execute the summary SQL with the filter value substituted.

    Returns the primary value in cents, or None if execution fails.
    """
    client = get_supabase_client()

    # Validate the SQL is safe (SELECT only)
    trimmed = summary_sql.strip().upper()
    if not trimmed.startswith("SELECT"):
        logger.warning(f"Invalid summary SQL (not SELECT): {summary_sql[:100]}")
        return None

    # Check for dangerous patterns
    dangerous_patterns = [
        r"\b(DROP|DELETE|INSERT|UPDATE|ALTER|TRUNCATE|CREATE|GRANT|REVOKE)\b",
        r"\b(EXEC|EXECUTE|CALL)\b",
        r";\s*\w",
    ]
    for pattern in dangerous_patterns:
        if re.search(pattern, summary_sql, re.I):
            logger.warning(f"Dangerous SQL pattern in summary SQL: {summary_sql[:100]}")
            return None

    try:
        # Execute via RPC function for safety
        result = client.rpc(
            "execute_readonly_query",
            {"query_text": summary_sql.replace(":filter_value", f"'{filter_value}'")}
        ).execute()

        if result.data and len(result.data) > 0:
            row = result.data[0]
            # Get the 'value' column, or the first numeric column
            if "value" in row:
                return int(row["value"]) if row["value"] is not None else 0
            # Fallback: get first numeric value
            for v in row.values():
                if isinstance(v, (int, float)):
                    return int(v)
        return 0
    except Exception as e:
        logger.error(f"Failed to execute summary SQL: {e}")
        return None


def _fetch_drill_down_data_sync(
    product: str | None,
    location: str | None,
    date: str | None,
    source: str | None,
    channel: str | None,
    payment_type: str | None,
    category: str | None,
    limit: int,
    summary_sql: str | None,
    summary_label: str | None,
) -> dict:
    """Synchronous function to fetch drill-down data (runs in thread pool)."""
    client = get_supabase_client()

    # Build query for order items (for display)
    query = client.from_("order_items").select(
        """
        quantity,
        unit_price_cents,
        total_cents,
        orders!inner (
            external_id,
            source,
            channel,
            payment_type,
            sales_cents,
            tax_cents,
            tip_cents,
            total_cents,
            created_at,
            locations!inner ( name )
        ),
        products!inner ( canonical_name, category )
        """
    ).order("orders(created_at)", desc=True)

    # Apply filters and determine filter_value for summary SQL
    filter_value = None
    if product:
        query = query.eq("products.canonical_name", product)
        filter_value = product
    if location:
        query = query.eq("orders.locations.name", location)
        filter_value = location
    if source:
        query = query.eq("orders.source", source)
        filter_value = source
    if channel:
        query = query.eq("orders.channel", channel)
        filter_value = channel
    if payment_type:
        query = query.eq("orders.payment_type", payment_type)
        filter_value = payment_type
    if category:
        query = query.eq("products.category", category)
        filter_value = category
    if date:
        filter_value = date

    result = query.execute()

    # Transform to flat structure
    orders = []
    for item in result.data or []:
        order_data = item.get("orders", {})
        product_data = item.get("products", {})
        location_data = order_data.get("locations", {}) if order_data else {}

        orders.append({
            "order_id": order_data.get("external_id") if order_data else None,
            "source": order_data.get("source") if order_data else None,
            "channel": order_data.get("channel") if order_data else None,
            "payment_type": order_data.get("payment_type") if order_data else None,
            "location": location_data.get("name") if location_data else None,
            "product": product_data.get("canonical_name") if product_data else None,
            "category": product_data.get("category") if product_data else None,
            "quantity": item.get("quantity"),
            "unit_price_cents": item.get("unit_price_cents"),
            "item_total_cents": item.get("total_cents"),
            "order_sales_cents": order_data.get("sales_cents") if order_data else None,
            "order_tax_cents": order_data.get("tax_cents") if order_data else None,
            "order_tip_cents": order_data.get("tip_cents") if order_data else None,
            "order_total_cents": order_data.get("total_cents") if order_data else None,
            "created_at": order_data.get("created_at") if order_data else None,
        })

    # Filter by date if specified (PostgREST doesn't support date filtering easily)
    if date:
        orders = [o for o in orders if o.get("created_at", "").startswith(date)]

    # Calculate basic stats from fetched orders
    unique_orders: dict[str, dict] = {}
    for o in orders:
        oid = o.get("order_id")
        if oid and oid not in unique_orders:
            unique_orders[oid] = {
                "sales_cents": o.get("order_sales_cents", 0),
                "tax_cents": o.get("order_tax_cents", 0),
                "tip_cents": o.get("order_tip_cents", 0),
                "total_cents": o.get("order_total_cents", 0),
            }

    total_quantity = sum(o.get("quantity", 0) for o in orders)
    order_count = len(unique_orders)

    # Execute summary SQL to get primary_value (100% accuracy with chart)
    primary_value = None
    if summary_sql and filter_value:
        primary_value = _execute_summary_sql(summary_sql, filter_value)

    # Fallback: if no summary SQL or execution failed, calculate from orders
    if primary_value is None:
        primary_value = sum(v["sales_cents"] for v in unique_orders.values())

    primary_label = summary_label or "Total"

    return {
        "success": True,
        "filters": {
            "product": product,
            "location": location,
            "date": date,
            "source": source,
            "channel": channel,
            "payment_type": payment_type,
            "category": category,
            "limit": limit,
        },
        "count": len(orders),
        "orders": orders,
        "summary": {
            "item_count": len(orders),
            "order_count": order_count,
            "total_quantity": total_quantity,
            "primary_value": primary_value,
            "primary_label": primary_label,
        },
    }


@router.get(
    "/drill-down",
    summary="Get Order Details (Drill-Down)",
    description="""
    Fetches detailed order-level data filtered by one or more dimensions.
    Used when clicking on chart data points to see underlying orders.

    At least one filter parameter is required.

    **Filter options:**
    - `product`: Filter by product name (e.g., "Grilled Chicken")
    - `location`: Filter by location (e.g., "Downtown")
    - `date`: Filter by date (e.g., "2025-01-02")
    - `source`: Filter by POS source ("toast", "doordash", "square")
    - `channel`: Filter by channel ("dine_in", "pickup", "delivery")
    - `payment_type`: Filter by payment type ("cash", "credit", etc.)
    - `category`: Filter by product category ("Entrees", "Drinks", etc.)
    """,
    responses={
        200: {
            "description": "Order details retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "filters": {"location": "Downtown", "limit": 50},
                        "count": 25,
                        "orders": [
                            {
                                "order_id": "ORD-001",
                                "source": "toast",
                                "channel": "dine_in",
                                "location": "Downtown",
                                "product": "Grilled Chicken",
                                "quantity": 2,
                                "item_total_cents": 2400,
                                "created_at": "2025-01-02T12:30:00Z",
                            }
                        ],
                        "summary": {
                            "item_count": 25,
                            "order_count": 15,
                            "sales_cents": 45000,
                        },
                    }
                }
            },
        },
        400: {"description": "No filter provided"},
        504: {"description": "Request timed out"},
    },
)
async def drill_down(
    product: str | None = Query(default=None, description="Filter by product name"),
    location: str | None = Query(default=None, description="Filter by location name"),
    date: str | None = Query(default=None, description="Filter by date (YYYY-MM-DD)"),
    source: str | None = Query(default=None, description="Filter by POS source"),
    channel: str | None = Query(default=None, description="Filter by order channel"),
    payment_type: str | None = Query(default=None, description="Filter by payment type"),
    category: str | None = Query(default=None, description="Filter by product category"),
    limit: int = Query(default=50, ge=1, le=500, description="Maximum number of items to return"),
    summary_sql: str | None = Query(
        default=None, alias="summarySQL", description="SQL to calculate summary value"
    ),
    summary_label: str | None = Query(
        default=None, alias="summaryLabel", description="Label for summary value"
    ),
):
    """
    Get detailed order data with filters.

    Retrieves order-level details for drill-down analysis. At least one filter
    parameter must be provided. Returns individual order items with their
    associated order and product information, plus summary statistics.

    Args:
        product: Filter by canonical product name.
        location: Filter by location name.
        date: Filter by date (YYYY-MM-DD format).
        source: Filter by POS source (toast, doordash, square).
        channel: Filter by order channel (dine_in, pickup, delivery).
        payment_type: Filter by payment type.
        category: Filter by product category.
        limit: Maximum items to return (1-500, default 50).

    Returns:
        Dict containing filtered orders, applied filters, and summary statistics.

    Raises:
        HTTPException 400: If no filter is provided.
        HTTPException 504: If the request times out.
        HTTPException 500: If a database error occurs.
    """
    # At least one filter required
    if not any([product, location, date, source, channel, payment_type, category]):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Please select a data point to view details",
                "code": "VALIDATION_ERROR",
            },
        )

    settings = get_settings()

    try:
        # Run sync DB call in thread pool with timeout
        result = await asyncio.wait_for(
            asyncio.to_thread(
                _fetch_drill_down_data_sync,
                product,
                location,
                date,
                source,
                channel,
                payment_type,
                category,
                limit,
                summary_sql,
                summary_label,
            ),
            timeout=settings.drill_down_timeout,
        )
        return result

    except asyncio.TimeoutError:
        logger.error(f"Drill-down timed out after {settings.drill_down_timeout}s")
        raise HTTPException(
            status_code=504,
            detail={
                "error": "Request timed out. Please try again.",
                "code": "TIMEOUT",
                "retryable": True,
            },
        )
    except Exception as e:
        logger.error(f"Drill-down query failed: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Unable to fetch order details. Please try again.",
                "code": "QUERY_ERROR",
                "retryable": True,
            },
        )
