"""Extract data from various POS sources."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from .exceptions import ExtractionError
from .matchers import get_channel_matcher, get_location_matcher
from .models import Source

logger = logging.getLogger(__name__)


# =============================================================================
# TOAST EXTRACTOR
# =============================================================================


def extract_toast(data_path: Path) -> Iterator[dict[str, Any]]:
    """Extract orders from Toast POS export."""
    location_matcher = get_location_matcher()
    channel_matcher = get_channel_matcher()

    try:
        with open(data_path) as f:
            data = json.load(f)
    except FileNotFoundError:
        raise ExtractionError("toast", f"File not found: {data_path}")
    except json.JSONDecodeError as e:
        raise ExtractionError("toast", f"Invalid JSON: {e}")

    # Build location lookup
    location_names = {}
    for loc in data.get("locations", []):
        location_names[loc.get("guid", "")] = loc.get("name", "")

    orders = data.get("orders", [])
    logger.info(f"Toast: Processing {len(orders)} orders")

    for order in orders:
        # Match location
        restaurant_guid = order.get("restaurantGuid", "")
        location_name = location_names.get(restaurant_guid, restaurant_guid)
        location, loc_method = location_matcher.match(location_name)
        if not location:
            location, loc_method = location_matcher.match(restaurant_guid)
        if not location:
            logger.debug(f"Skipping order - no location: {restaurant_guid}")
            continue

        # Match channel
        dining_option = order.get("diningOption", {})
        channel_str = dining_option.get("name", "Dine In")
        channel, chan_method = channel_matcher.match(channel_str)

        # Parse timestamp
        date_str = order.get("openedDate") or order.get("paidDate") or order.get("closedDate", "")
        if not date_str:
            continue

        try:
            created_at = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError as e:
            logger.warning(f"Invalid date '{date_str}': {e}")
            continue

        # Extract items
        items = []
        for check in order.get("checks", []):
            for selection in check.get("selections", []):
                item_name = selection.get("displayName", "")
                if not item_name:
                    continue

                quantity = selection.get("quantity", 1)
                price_cents = selection.get("preDiscountPrice", 0)
                unit_price = price_cents // quantity if quantity > 0 else price_cents
                # Category is in itemGroup.name (e.g., "🍔 Burgers")
                category = selection.get("itemGroup", {}).get("name")

                modifiers = [
                    {"name": m.get("displayName", ""), "price_cents": m.get("price", 0)}
                    for m in selection.get("modifiers", [])
                    if m.get("displayName")
                ]

                items.append(
                    {
                        "product_name": item_name,
                        "category": category,
                        "quantity": quantity,
                        "unit_price_cents": unit_price,
                        "modifiers": modifiers,
                    }
                )

        if not items:
            continue

        subtotal = sum(c.get("amount", 0) for c in order.get("checks", []))
        tax = sum(c.get("taxAmount", 0) for c in order.get("checks", []))
        tip = sum(c.get("totalTipAmount", 0) for c in order.get("checks", []))

        yield {
            "external_id": order.get("guid", ""),
            "source": Source.TOAST,
            "location": location,
            "channel": channel,
            "subtotal_cents": subtotal,
            "tax_cents": tax,
            "tip_cents": tip,
            "created_at": created_at,
            "items": items,
            "_location_input": location_name,
            "_location_method": loc_method,
            "_channel_input": channel_str,
            "_channel_method": chan_method,
        }


# =============================================================================
# DOORDASH EXTRACTOR
# =============================================================================


def extract_doordash(data_path: Path) -> Iterator[dict[str, Any]]:
    """Extract orders from DoorDash export."""
    location_matcher = get_location_matcher()
    channel_matcher = get_channel_matcher()

    try:
        with open(data_path) as f:
            data = json.load(f)
    except FileNotFoundError:
        raise ExtractionError("doordash", f"File not found: {data_path}")
    except json.JSONDecodeError as e:
        raise ExtractionError("doordash", f"Invalid JSON: {e}")

    # Build store lookup
    store_names = {}
    for store in data.get("stores", []):
        store_names[store.get("store_id", "")] = store.get("name", "")

    orders = data.get("orders", [])
    logger.info(f"DoorDash: Processing {len(orders)} orders")

    for order in orders:
        # Match location
        store_id = order.get("store_id", "")
        store_name = store_names.get(store_id, store_id)
        location, loc_method = location_matcher.match(store_name)
        if not location:
            location, loc_method = location_matcher.match(store_id)
        if not location:
            continue

        # Match channel
        channel_str = order.get("order_fulfillment_method", "MERCHANT_DELIVERY")
        channel, chan_method = channel_matcher.match(channel_str)

        # Parse timestamp
        date_str = order.get("created_at", "")
        if not date_str:
            continue

        try:
            created_at = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            continue

        # Extract items
        items = []
        for item in order.get("order_items", []):
            item_name = item.get("name", "")
            if not item_name:
                continue

            modifiers = [
                {"name": o.get("name", ""), "price_cents": o.get("price", 0)}
                for o in item.get("options", [])
                if o.get("name")
            ]

            items.append(
                {
                    "product_name": item_name,
                    "category": item.get("category"),
                    "quantity": item.get("quantity", 1),
                    "unit_price_cents": item.get("unit_price", 0),
                    "modifiers": modifiers,
                }
            )

        if not items:
            continue

        yield {
            "external_id": order.get("external_delivery_id", ""),
            "source": Source.DOORDASH,
            "location": location,
            "channel": channel,
            "subtotal_cents": order.get("order_subtotal", 0),
            "tax_cents": order.get("tax_amount", 0),
            "tip_cents": order.get("dasher_tip", 0),
            "created_at": created_at,
            "items": items,
            "_location_input": store_name,
            "_location_method": loc_method,
            "_channel_input": channel_str,
            "_channel_method": chan_method,
        }


# =============================================================================
# SQUARE EXTRACTOR
# =============================================================================


def build_square_catalog(catalog_path: Path) -> dict[str, dict]:
    """Build lookup tables from Square catalog."""
    try:
        with open(catalog_path) as f:
            data = json.load(f)
    except FileNotFoundError:
        raise ExtractionError("square", f"Catalog not found: {catalog_path}")
    except json.JSONDecodeError as e:
        raise ExtractionError("square", f"Invalid catalog JSON: {e}")

    lookup: dict[str, dict] = {"items": {}, "variations": {}, "categories": {}}

    for obj in data.get("objects", []):
        obj_type = obj.get("type")
        obj_id = obj.get("id")

        if obj_type == "CATEGORY":
            lookup["categories"][obj_id] = {"name": obj.get("category_data", {}).get("name", "")}

        elif obj_type == "ITEM":
            item_data = obj.get("item_data", {})
            lookup["items"][obj_id] = {
                "name": item_data.get("name", ""),
                "category_id": item_data.get("category_id"),
            }
            for var in item_data.get("variations", []):
                var_data = var.get("item_variation_data", {})
                lookup["variations"][var.get("id")] = {
                    "name": var_data.get("name", ""),
                    "item_id": obj_id,
                    "price_cents": var_data.get("price_money", {}).get("amount", 0),
                }

    return lookup


def extract_square(
    orders_path: Path,
    catalog_path: Path,
    locations_path: Path | None = None,
) -> Iterator[dict[str, Any]]:
    """Extract orders from Square export."""
    location_matcher = get_location_matcher()
    channel_matcher = get_channel_matcher()
    catalog = build_square_catalog(catalog_path)

    # Build location lookup
    location_names = {}
    if locations_path and locations_path.exists():
        try:
            with open(locations_path) as f:
                for loc in json.load(f).get("locations", []):
                    location_names[loc.get("id", "")] = loc.get("name", "")
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Could not load Square locations: {e}")

    try:
        with open(orders_path) as f:
            data = json.load(f)
    except FileNotFoundError:
        raise ExtractionError("square", f"Orders not found: {orders_path}")
    except json.JSONDecodeError as e:
        raise ExtractionError("square", f"Invalid orders JSON: {e}")

    orders = data.get("orders", [])
    logger.info(f"Square: Processing {len(orders)} orders")

    for order in orders:
        # Match location
        location_id = order.get("location_id", "")
        location_name = location_names.get(location_id, location_id)
        location, loc_method = location_matcher.match(location_name)
        if not location:
            location, loc_method = location_matcher.match(location_id)
        if not location:
            continue

        # Match channel
        fulfillments = order.get("fulfillments", [])
        channel_str = fulfillments[0].get("type", "DINE_IN") if fulfillments else "DINE_IN"
        channel, chan_method = channel_matcher.match(channel_str)

        # Parse timestamp
        date_str = order.get("created_at", "")
        if not date_str:
            continue

        try:
            created_at = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            continue

        # Extract items
        items = []
        for line in order.get("line_items", []):
            cat_obj_id = line.get("catalog_object_id", "")
            variation = catalog["variations"].get(cat_obj_id, {})
            item = catalog["items"].get(variation.get("item_id", ""), {})

            item_name = item.get("name") or variation.get("name", "Unknown Item")
            category_id = item.get("category_id")
            category = catalog["categories"].get(category_id, {}).get("name")

            quantity = int(line.get("quantity", "1"))
            total = line.get("total_money", {}).get("amount", 0)

            modifiers = [
                {"name": m.get("modifier_id", ""), "price_cents": 0}
                for m in line.get("applied_modifiers", [])
            ]

            items.append(
                {
                    "product_name": item_name,
                    "category": category,
                    "quantity": quantity,
                    "unit_price_cents": total // quantity if quantity > 0 else total,
                    "modifiers": modifiers,
                }
            )

        if not items:
            continue

        total = order.get("total_money", {}).get("amount", 0)
        tax = order.get("total_tax_money", {}).get("amount", 0)
        tip = order.get("total_tip_money", {}).get("amount", 0)

        yield {
            "external_id": order.get("id", ""),
            "source": Source.SQUARE,
            "location": location,
            "channel": channel,
            "subtotal_cents": total - tax - tip,
            "tax_cents": tax,
            "tip_cents": tip,
            "created_at": created_at,
            "items": items,
            "_location_input": location_name,
            "_location_method": loc_method,
            "_channel_input": channel_str,
            "_channel_method": chan_method,
        }


# =============================================================================
# SEEDING (called from main.py)
# =============================================================================


def seed_locations(names: list[str]) -> None:
    """Seed location matcher with database names."""
    get_location_matcher().seed(names)
