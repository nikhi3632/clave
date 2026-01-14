"""Extract data from various POS sources."""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from exceptions import ExtractionError
from matchers import get_channel_matcher, get_location_matcher
from models import Source

logger = logging.getLogger(__name__)


# =============================================================================
# LOCATION EXTRACTION (for dynamic location discovery)
# =============================================================================


@dataclass
class ExtractedLocation:
    """Location extracted from source data."""

    name: str
    street: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    timezone: str = "America/New_York"
    source_ids: dict[str, str] = field(default_factory=dict)  # source -> id


def extract_locations_from_toast(data_path: Path) -> list[ExtractedLocation]:
    """Extract locations from Toast POS export."""
    locations = []
    try:
        with open(data_path) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"Could not load Toast data for locations: {e}")
        return locations

    for loc in data.get("locations", []):
        name = loc.get("name", "").strip()
        if not name:
            continue

        address = loc.get("address", {})
        locations.append(
            ExtractedLocation(
                name=name,
                street=address.get("line1"),
                city=address.get("city"),
                state=address.get("state"),
                zip_code=address.get("zip"),
                timezone=loc.get("timezone", "America/New_York"),
                source_ids={"toast": loc.get("guid", "")},
            )
        )

    logger.info(f"Toast: Extracted {len(locations)} locations")
    return locations


def extract_locations_from_doordash(data_path: Path) -> list[ExtractedLocation]:
    """Extract locations from DoorDash stores."""
    locations = []
    try:
        with open(data_path) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"Could not load DoorDash data for locations: {e}")
        return locations

    for store in data.get("stores", []):
        name = store.get("name", "").strip()
        if not name:
            continue

        address = store.get("address", {})
        locations.append(
            ExtractedLocation(
                name=name,
                street=address.get("street"),
                city=address.get("city"),
                state=address.get("state"),
                zip_code=address.get("zip_code"),
                timezone=store.get("timezone", "America/New_York"),
                source_ids={"doordash": store.get("store_id", "")},
            )
        )

    logger.info(f"DoorDash: Extracted {len(locations)} locations")
    return locations


def extract_locations_from_square(locations_path: Path) -> list[ExtractedLocation]:
    """Extract locations from Square locations.json."""
    locations = []
    try:
        with open(locations_path) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"Could not load Square locations: {e}")
        return locations

    for loc in data.get("locations", []):
        name = loc.get("name", "").strip()
        if not name:
            continue

        address = loc.get("address", {})
        locations.append(
            ExtractedLocation(
                name=name,
                street=address.get("address_line_1"),
                city=address.get("locality"),
                state=address.get("administrative_district_level_1"),
                zip_code=address.get("postal_code"),
                timezone=loc.get("timezone", "America/New_York"),
                source_ids={"square": loc.get("id", "")},
            )
        )

    logger.info(f"Square: Extracted {len(locations)} locations")
    return locations


def merge_locations(all_locations: list[ExtractedLocation]) -> list[ExtractedLocation]:
    """Merge locations by normalized name, combining source IDs."""
    merged: dict[str, ExtractedLocation] = {}

    for loc in all_locations:
        key = loc.name.lower().strip()

        if key in merged:
            # Merge source IDs
            merged[key].source_ids.update(loc.source_ids)
            # Fill in missing address fields
            if not merged[key].street and loc.street:
                merged[key].street = loc.street
            if not merged[key].city and loc.city:
                merged[key].city = loc.city
            if not merged[key].state and loc.state:
                merged[key].state = loc.state
            if not merged[key].zip_code and loc.zip_code:
                merged[key].zip_code = loc.zip_code
        else:
            merged[key] = loc

    return list(merged.values())


# =============================================================================
# PAYMENT TYPE NORMALIZATION
# =============================================================================

def normalize_payment_type(raw_type: str | None) -> str | None:
    """
    Normalize payment type across different POS sources.

    Standardizes to: CARD, CASH, WALLET, OTHER
    """
    if not raw_type:
        return None

    upper = raw_type.upper()

    # Card payments (credit/debit)
    if upper in ("CREDIT", "CARD", "DEBIT", "CREDIT_CARD", "DEBIT_CARD"):
        return "CARD"

    # Cash
    if upper == "CASH":
        return "CASH"

    # Digital wallets
    if upper in ("APPLE_PAY", "GOOGLE_PAY", "WALLET", "SAMSUNG_PAY", "PAYPAL"):
        return "WALLET"

    # Everything else
    return "OTHER"


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
                        "original_name": selection.get("displayName"),
                        "special_instructions": None,  # Toast doesn't have this at item level
                    }
                )

        if not items:
            continue

        subtotal = sum(c.get("amount", 0) for c in order.get("checks", []))
        tax = sum(c.get("taxAmount", 0) for c in order.get("checks", []))
        tip = sum(c.get("tipAmount", 0) for c in order.get("checks", []))

        # Extract payment info from first check's first payment
        payment_type = None
        card_type = None
        processing_fee_cents = 0
        refund_status = None
        check_number = None
        checks = order.get("checks", [])
        if checks:
            check_number = checks[0].get("displayNumber")
            payments = checks[0].get("payments", [])
            if payments:
                payment = payments[0]
                payment_type = normalize_payment_type(payment.get("type"))
                card_type = payment.get("cardType")  # VISA, MASTERCARD, etc.
                processing_fee_cents = payment.get("originalProcessingFee", 0)
                refund_status = payment.get("refundStatus")  # NONE, PARTIAL, FULL

        # Extract server info
        server = order.get("server", {})
        server_name = None
        if server:
            first = server.get("firstName", "")
            last = server.get("lastName", "")
            server_name = f"{first} {last}".strip() or None

        # Extract revenue center
        revenue_center = order.get("revenueCenter", {}).get("name")

        # Parse closed_at timestamp
        closed_at = None
        closed_str = order.get("closedDate")
        if closed_str:
            try:
                closed_at = datetime.fromisoformat(closed_str.replace("Z", "+00:00"))
            except ValueError:
                pass

        yield {
            "external_id": order.get("guid", ""),
            "source": Source.TOAST,
            "location": location,
            "channel": channel,
            "sales_cents": subtotal,
            "tax_cents": tax,
            "tip_cents": tip,
            "created_at": created_at,
            "items": items,
            "order_status": "COMPLETED" if not order.get("voided") else "VOIDED",
            "pickup_time": None,
            "delivery_time": None,
            "closed_at": closed_at,
            "is_catering": False,
            "contains_alcohol": False,
            "voided": order.get("voided", False),
            "deleted": order.get("deleted", False),
            "refund_status": refund_status,
            "payment_type": payment_type,
            "card_type": card_type,
            "revenue_center": revenue_center,
            "server_name": server_name,
            "check_number": check_number,
            "order_source": order.get("source"),  # POS, ONLINE, THIRD_PARTY
            "business_date": order.get("businessDate"),
            "delivery_fee_cents": 0,
            "service_fee_cents": 0,
            "commission_cents": 0,
            "merchant_payout_cents": 0,
            "processing_fee_cents": processing_fee_cents,
            "delivery_street": None,
            "delivery_city": None,
            "delivery_state": None,
            "delivery_zip": None,
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
                    "original_name": item.get("name"),
                    "special_instructions": item.get("special_instructions") or None,
                }
            )

        if not items:
            continue

        # Parse pickup and delivery times
        pickup_time = None
        delivery_time = None
        pickup_str = order.get("pickup_time")
        delivery_str = order.get("delivery_time")
        if pickup_str:
            try:
                pickup_time = datetime.fromisoformat(pickup_str.replace("Z", "+00:00"))
            except ValueError:
                pass
        if delivery_str:
            try:
                delivery_time = datetime.fromisoformat(delivery_str.replace("Z", "+00:00"))
            except ValueError:
                pass

        # Extract delivery address (may be null for pickup orders)
        dropoff = order.get("dropoff_address") or {}

        yield {
            "external_id": order.get("external_delivery_id", ""),
            "source": Source.DOORDASH,
            "location": location,
            "channel": channel,
            "sales_cents": order.get("order_subtotal", 0),
            "tax_cents": order.get("tax_amount", 0),
            "tip_cents": order.get("dasher_tip", 0),
            "created_at": created_at,
            "items": items,
            # DoorDash-specific fields
            "order_status": order.get("order_status"),  # DELIVERED, PICKED_UP
            "pickup_time": pickup_time,
            "delivery_time": delivery_time,
            "is_catering": order.get("is_catering", False),
            "contains_alcohol": order.get("contains_alcohol", False),
            "delivery_fee_cents": order.get("delivery_fee", 0),
            "service_fee_cents": order.get("service_fee", 0),
            "commission_cents": order.get("commission", 0),
            "merchant_payout_cents": order.get("merchant_payout", 0),
            # Delivery address
            "delivery_street": dropoff.get("street"),
            "delivery_city": dropoff.get("city"),
            "delivery_state": dropoff.get("state"),
            "delivery_zip": dropoff.get("zip_code"),
            # Not available in DoorDash
            "closed_at": None,
            "voided": False,
            "deleted": False,
            "refund_status": None,
            "payment_type": "UNKNOWN",  # DoorDash doesn't expose payment info
            "card_type": None,
            "processing_fee_cents": 0,
            "revenue_center": None,
            "server_name": None,
            "check_number": None,
            "order_source": "DOORDASH",
            "business_date": None,
            # Debug fields
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


def build_square_payments(payments_path: Path) -> dict[str, dict]:
    """Build lookup from order_id to payment info."""
    payments = {}
    if not payments_path.exists():
        return payments
    try:
        with open(payments_path) as f:
            data = json.load(f)
        for payment in data.get("payments", []):
            order_id = payment.get("order_id")
            if order_id:
                source_type = payment.get("source_type", "")  # CARD, CASH, etc.
                card_brand = None
                if source_type == "CARD":
                    card_brand = payment.get("card_details", {}).get("card", {}).get("card_brand")
                payments[order_id] = {
                    "payment_type": normalize_payment_type(source_type),
                    "card_type": card_brand,
                }
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Could not load Square payments: {e}")
    return payments


def extract_square(
    orders_path: Path,
    catalog_path: Path,
    locations_path: Path | None = None,
    payments_path: Path | None = None,
) -> Iterator[dict[str, Any]]:
    """Extract orders from Square export."""
    location_matcher = get_location_matcher()
    channel_matcher = get_channel_matcher()
    catalog = build_square_catalog(catalog_path)

    # Build payment lookup
    payments_lookup = {}
    if payments_path:
        payments_lookup = build_square_payments(payments_path)

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
                    "original_name": item_name,
                    "special_instructions": line.get("note"),
                }
            )

        if not items:
            continue

        total = order.get("total_money", {}).get("amount", 0)
        tax = order.get("total_tax_money", {}).get("amount", 0)
        tip = order.get("total_tip_money", {}).get("amount", 0)

        # Get payment info from lookup
        order_id = order.get("id", "")
        payment_info = payments_lookup.get(order_id, {})

        # Parse closed_at timestamp
        closed_at = None
        closed_str = order.get("closed_at")
        if closed_str:
            try:
                closed_at = datetime.fromisoformat(closed_str.replace("Z", "+00:00"))
            except ValueError:
                pass

        # Determine voided status from order state
        order_state = order.get("state", "")
        is_voided = order_state == "CANCELED"

        yield {
            "external_id": order_id,
            "source": Source.SQUARE,
            "location": location,
            "channel": channel,
            "sales_cents": total - tax - tip,
            "tax_cents": tax,
            "tip_cents": tip,
            "created_at": created_at,
            "items": items,
            "order_status": order_state,  # OPEN, COMPLETED, CANCELED
            "pickup_time": None,
            "delivery_time": None,
            "closed_at": closed_at,
            "is_catering": False,
            "contains_alcohol": False,
            "voided": is_voided,
            "deleted": False,
            "refund_status": None,
            "payment_type": payment_info.get("payment_type"),
            "card_type": payment_info.get("card_type"),
            "processing_fee_cents": 0,
            "revenue_center": None,
            "server_name": None,
            "check_number": None,
            "order_source": "SQUARE",
            "business_date": None,
            "delivery_fee_cents": 0,
            "service_fee_cents": order.get("total_service_charge_money", {}).get("amount", 0),
            "commission_cents": 0,
            "merchant_payout_cents": 0,
            "delivery_street": None,
            "delivery_city": None,
            "delivery_state": None,
            "delivery_zip": None,
            # Debug fields
            "_location_input": location_name,
            "_location_method": loc_method,
            "_channel_input": channel_str,
            "_channel_method": chan_method,
        }


