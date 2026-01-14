"""Transform and normalize extracted data."""

import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from exceptions import TransformationError
from matchers import CategoryMatcher, ProductMatcher, get_category_matcher, get_product_matcher
from models import Modifier, Order, OrderItem, Product, TransformResult

if TYPE_CHECKING:
    from classifier import CategoryClassifier, ProductNameClassifier

logger = logging.getLogger(__name__)


@dataclass
class CleanupRecord:
    """Record of a data cleanup operation."""

    field: str
    original: str
    cleaned: str
    reason: str


def clean_category(category: str | None, matcher: CategoryMatcher) -> tuple[str | None, str | None]:
    """
    Clean category: remove emojis, normalize spelling.
    Returns (cleaned, reason) where reason is emoji_removed/typo_fixed/case_normalized/None.
    """
    if not category:
        return None, None

    original = category

    # Remove emojis
    cleaned = "".join(c for c in category if unicodedata.category(c) not in ("So", "Mn", "Cf"))
    reason = "emoji_removed" if cleaned != category else None
    category = cleaned.strip()

    if not category:
        return None, reason

    # Handle combined categories (e.g., "Sides & Appetizers")
    if any(sep in category.lower() for sep in (" & ", " and ", "/", ", ")):
        parts = re.split(r"\s*[&/,]\s*|\s+and\s+", category)
        normalized = []
        any_typo = False
        for part in parts:
            part = part.strip()
            if part:
                result = matcher.match(part)
                normalized.append(result.matched)
                if result.method in ("phonetic", "fuzzy"):
                    any_typo = True
        result_str = " & ".join(normalized) if normalized else category.title()
        if any_typo:
            reason = "typo_fixed"
    else:
        match_result = matcher.match(category)
        result_str = match_result.matched or category.title()
        if match_result.method in ("phonetic", "fuzzy"):
            reason = "typo_fixed"

    if result_str != original and reason is None:
        if result_str.lower() == original.lower():
            reason = "case_normalized"

    return result_str, reason if result_str != original else None


class Transformer:
    """Transform raw extracted data into validated orders."""

    def __init__(
        self,
        existing_products: list[str] | None = None,
        product_matcher: ProductMatcher | None = None,
        category_matcher: CategoryMatcher | None = None,
        category_classifier: "CategoryClassifier | None" = None,
        product_name_classifier: "ProductNameClassifier | None" = None,
    ):
        self.product_matcher = product_matcher or get_product_matcher()
        self.category_matcher = category_matcher or get_category_matcher()
        self.category_classifier = category_classifier
        self.product_name_classifier = product_name_classifier

        # Seed with existing products
        if existing_products:
            self.product_matcher.seed(existing_products)

        self.products_seen: dict[str, Product] = {}
        self.cleanups: list[CleanupRecord] = []
        self._all_original_names: set[str] = set()  # All unique original names for LLM

    def transform(self, raw: dict[str, Any]) -> TransformResult:
        """Transform a raw order into a validated order."""
        warnings: list[str] = []
        changes: list[str] = []
        order_id = raw.get("external_id", "unknown")

        try:
            items = []
            for raw_item in raw.get("items", []):
                item, item_changes, item_warnings = self._transform_item(raw_item)
                items.append(item)
                changes.extend(item_changes)
                warnings.extend(item_warnings)

            if not items:
                raise TransformationError(order_id, "No valid items")

            order = Order(
                external_id=raw["external_id"],
                source=raw["source"],
                location=raw["location"],
                channel=raw["channel"],
                # Financial fields
                sales_cents=raw["sales_cents"],
                tax_cents=raw["tax_cents"],
                tip_cents=raw["tip_cents"],
                delivery_fee_cents=raw.get("delivery_fee_cents", 0),
                service_fee_cents=raw.get("service_fee_cents", 0),
                commission_cents=raw.get("commission_cents", 0),
                merchant_payout_cents=raw.get("merchant_payout_cents", 0),
                processing_fee_cents=raw.get("processing_fee_cents", 0),
                # Order status & timing
                order_status=raw.get("order_status"),
                pickup_time=raw.get("pickup_time"),
                delivery_time=raw.get("delivery_time"),
                closed_at=raw.get("closed_at"),
                # Order flags
                is_catering=raw.get("is_catering", False),
                contains_alcohol=raw.get("contains_alcohol", False),
                voided=raw.get("voided", False),
                deleted=raw.get("deleted", False),
                refund_status=raw.get("refund_status"),
                # Payment info
                payment_type=raw.get("payment_type"),
                card_type=raw.get("card_type"),
                # Toast-specific
                revenue_center=raw.get("revenue_center"),
                server_name=raw.get("server_name"),
                check_number=raw.get("check_number"),
                order_source=raw.get("order_source"),
                business_date=raw.get("business_date"),
                # Delivery address
                delivery_street=raw.get("delivery_street"),
                delivery_city=raw.get("delivery_city"),
                delivery_state=raw.get("delivery_state"),
                delivery_zip=raw.get("delivery_zip"),
                # Timestamps
                created_at=raw["created_at"],
                items=items,
            )

            return TransformResult(success=True, order=order, warnings=warnings, changes=changes)

        except TransformationError:
            raise
        except KeyError as e:
            logger.error(f"Missing field in order {order_id}: {e}")
            return TransformResult(
                success=False, error=f"Missing field: {e}", warnings=warnings, changes=changes
            )
        except Exception as e:
            logger.error(f"Transform failed for {order_id}: {e}")
            return TransformResult(success=False, error=str(e), warnings=warnings, changes=changes)

    def _transform_item(self, raw: dict[str, Any]) -> tuple[OrderItem, list[str], list[str]]:
        """Transform a raw item."""
        changes: list[str] = []
        warnings: list[str] = []

        original_name = raw.get("product_name", "")
        original_category = raw.get("category")

        # Collect original name for LLM normalization
        if original_name:
            self._all_original_names.add(original_name)
            # Also register with ProductNameClassifier if available
            if self.product_name_classifier:
                self.product_name_classifier.add_product(original_name)

        # Check LLM cache FIRST - it has authoritative mappings
        # This prevents fuzzy matcher from wrongly grouping similar-sounding items
        # (e.g., "Margarita" cocktail vs "Margherita Pizza")
        llm_canonical = None
        if self.product_name_classifier:
            # Returns None if not in cache, canonical name if cached
            # Even identity mappings like "Margarita" → "Margarita" are authoritative
            llm_canonical = self.product_name_classifier.get_canonical_name(original_name)

        if llm_canonical is not None:
            # Use LLM's authoritative canonical name
            canonical = llm_canonical
            confidence = 1.0
            method = "llm_cache"
            changes.append(f"LLM cached: '{original_name}' -> '{canonical}'")
        else:
            # Fall back to fuzzy matching for new products
            match = self.product_matcher.match(original_name)
            canonical = match.matched
            confidence = match.confidence
            method = match.method

        if method == "new":
            self.product_matcher.add(original_name)
            canonical = original_name
            changes.append(f"New product: '{original_name}'")
        elif method != "llm_cache" and canonical != original_name:
            changes.append(
                f"Normalized: '{original_name}' -> '{canonical}' ({method}, {confidence:.2f})"
            )

        if 0 < confidence < 0.8:
            warnings.append(
                f"Low confidence: '{original_name}' -> '{canonical}' ({confidence:.2f})"
            )

        # Clean category
        cleaned_category, cleanup_reason = clean_category(original_category, self.category_matcher)
        if cleanup_reason:
            changes.append(
                f"Category: '{original_category}' -> '{cleaned_category}' ({cleanup_reason})"
            )
            self.cleanups.append(
                CleanupRecord(
                    field="category",
                    original=original_category or "",
                    cleaned=cleaned_category or "",
                    reason=cleanup_reason,
                )
            )

        # Use LLM classifier for missing categories
        if self.category_classifier:
            # Register with classifier (will use cache or queue for LLM)
            self.category_classifier.get_category(canonical, cleaned_category)

        # Track product
        if canonical not in self.products_seen:
            self.products_seen[canonical] = Product(
                canonical_name=canonical,
                category=cleaned_category,
                original_names=[original_name],
            )
        elif original_name not in self.products_seen[canonical].original_names:
            self.products_seen[canonical].original_names.append(original_name)

        # Build modifiers
        modifiers = [
            Modifier(name=m["name"], price_cents=m.get("price_cents", 0))
            for m in raw.get("modifiers", [])
        ]

        return (
            OrderItem(
                product_name=original_name,
                canonical_name=canonical,
                category=cleaned_category,
                quantity=raw.get("quantity", 1),
                unit_price_cents=raw.get("unit_price_cents", 0),
                modifiers=modifiers,
                match_confidence=confidence if confidence > 0 else None,
                match_method=method if method != "new" else None,
                original_name=raw.get("original_name"),
                special_instructions=raw.get("special_instructions"),
            ),
            changes,
            warnings,
        )

    def get_products(self) -> list[Product]:
        return list(self.products_seen.values())

    def get_cleanups(self) -> list[CleanupRecord]:
        return self.cleanups

    def apply_llm_categories(self) -> int:
        """
        Apply LLM-classified categories to products.

        Call this after classify_pending() has been run on the classifier.
        This updates ALL products to use normalized categories from the classifier.

        Returns:
            Number of products updated with LLM categories.
        """
        if not self.category_classifier:
            return 0

        updated = 0
        for canonical, product in self.products_seen.items():
            llm_category = self.category_classifier.get_cached_category(canonical)
            if llm_category and llm_category != product.category:
                product.category = llm_category
                updated += 1

        if updated:
            logger.info(f"Applied normalized categories to {updated} products")

        return updated

    def apply_llm_product_names(self, orders: list[Order] | None = None) -> int:
        """
        Apply LLM-normalized product names.

        Call this after classify_pending() has been run on the ProductNameClassifier.
        This handles two cases:
        1. CONSOLIDATE: Different original names map to the same canonical
           (e.g., "Lg Coke" and "Large Coca-Cola" both become "Coca-Cola")
        2. SPLIT: Original names in one product map to DIFFERENT canonicals
           (e.g., "Margarita" and "Margherita Pizza" were wrongly grouped)

        Args:
            orders: List of orders to update with new canonical names.

        Returns:
            Number of products affected (consolidated + split).
        """
        if not self.product_name_classifier:
            return 0

        new_products: dict[str, Product] = {}
        # Map original_name -> new_canonical (for order item updates)
        orig_name_mapping: dict[str, str] = {}
        consolidated = 0
        split_count = 0

        for old_canonical, product in self.products_seen.items():
            # Group original_names by their LLM canonical name
            # e.g., {"Margarita": ["Margarita"], "Margherita Pizza": ["Margherita Pizza", "..."]}
            canonical_groups: dict[str, list[str]] = {}

            for orig_name in product.original_names:
                llm_name = self.product_name_classifier.get_canonical_name(orig_name)
                # If no LLM mapping, default to the current product's canonical
                target_canonical = llm_name if llm_name is not None else old_canonical

                if target_canonical not in canonical_groups:
                    canonical_groups[target_canonical] = []
                canonical_groups[target_canonical].append(orig_name)

            # Track if we're splitting (multiple groups from one product)
            if len(canonical_groups) > 1:
                split_count += 1
                logger.debug(
                    f"Splitting product '{old_canonical}' into: {list(canonical_groups.keys())}"
                )

            # Process each group - either merge into existing or create new product
            for new_canonical, orig_names in canonical_groups.items():
                # Track mapping for order item updates
                for orig in orig_names:
                    if new_canonical != old_canonical:
                        orig_name_mapping[orig] = new_canonical

                if new_canonical in new_products:
                    # Merge into existing product
                    existing = new_products[new_canonical]
                    for orig in orig_names:
                        if orig not in existing.original_names:
                            existing.original_names.append(orig)
                    # Keep category if existing is None
                    if existing.category is None and product.category:
                        existing.category = product.category
                    consolidated += 1
                else:
                    # Create new product for this canonical
                    new_products[new_canonical] = Product(
                        canonical_name=new_canonical,
                        category=product.category,
                        original_names=list(orig_names),
                    )

                    # If this is a split (new canonical differs from old), register
                    # with category classifier so it gets proper classification
                    if new_canonical != old_canonical and self.category_classifier:
                        self.category_classifier.get_category(new_canonical, None)

        self.products_seen = new_products

        # Update OrderItems using original name (product_name) to find new canonical
        if orders and orig_name_mapping:
            items_updated = 0
            for order in orders:
                for item in order.items:
                    # Use the item's original product_name to look up correct canonical
                    if item.product_name in orig_name_mapping:
                        item.canonical_name = orig_name_mapping[item.product_name]
                        items_updated += 1
            if items_updated:
                logger.debug(f"Updated {items_updated} order items with normalized names")

        if consolidated or split_count:
            logger.info(
                f"LLM normalization: {consolidated} merged, {split_count} split "
                f"(now {len(new_products)} unique products)"
            )

        return consolidated + split_count
