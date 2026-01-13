from fastapi import APIRouter, HTTPException, Query

from services import get_supabase_client

router = APIRouter(prefix="/api", tags=["drill-down"])


@router.get("/drill-down")
async def drill_down(
    product: str | None = Query(default=None),
    location: str | None = Query(default=None),
    date: str | None = Query(default=None),
    source: str | None = Query(default=None),
    channel: str | None = Query(default=None),
    payment_type: str | None = Query(default=None),
    category: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
):
    """Get detailed order data with filters."""
    # At least one filter required
    if not any([product, location, date, source, channel, payment_type, category]):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "At least one filter is required",
                "code": "VALIDATION_ERROR",
            },
        )

    try:
        client = get_supabase_client()

        # Build query
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
                subtotal_cents,
                tax_cents,
                tip_cents,
                total_cents,
                created_at,
                locations!inner ( name )
            ),
            products!inner ( canonical_name, category )
            """
        ).order("orders(created_at)", desc=True)

        # Apply filters
        if product:
            query = query.eq("products.canonical_name", product)
        if location:
            query = query.eq("orders.locations.name", location)
        if source:
            query = query.eq("orders.source", source)
        if channel:
            query = query.eq("orders.channel", channel)
        if payment_type:
            query = query.eq("orders.payment_type", payment_type)
        if category:
            query = query.eq("products.category", category)

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
                "order_subtotal_cents": order_data.get("subtotal_cents") if order_data else None,
                "order_tax_cents": order_data.get("tax_cents") if order_data else None,
                "order_tip_cents": order_data.get("tip_cents") if order_data else None,
                "order_total_cents": order_data.get("total_cents") if order_data else None,
                "created_at": order_data.get("created_at") if order_data else None,
            })

        # Filter by date if specified
        if date:
            orders = [o for o in orders if o.get("created_at", "").startswith(date)]

        # Calculate summary from unique orders
        unique_orders: dict[str, dict] = {}
        for o in orders:
            oid = o.get("order_id")
            if oid and oid not in unique_orders:
                unique_orders[oid] = {
                    "subtotal_cents": o.get("order_subtotal_cents", 0),
                    "tax_cents": o.get("order_tax_cents", 0),
                    "tip_cents": o.get("order_tip_cents", 0),
                    "total_cents": o.get("order_total_cents", 0),
                }

        item_subtotal = sum(o.get("item_total_cents", 0) for o in orders)
        order_count = len(unique_orders)
        total_tax = sum(v["tax_cents"] for v in unique_orders.values())
        total_tips = sum(v["tip_cents"] for v in unique_orders.values())
        total_revenue = sum(v["total_cents"] for v in unique_orders.values())

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
                "item_subtotal_cents": item_subtotal,
                "tax_cents": total_tax,
                "tip_cents": total_tips,
                "revenue_cents": total_revenue,
            },
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": str(e), "code": "QUERY_ERROR"},
        )
