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
                subtotal_cents=raw["subtotal_cents"],
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

        # Match product using fuzzy matching (will be improved by LLM later)
        match = self.product_matcher.match(original_name)
        canonical = match.matched
        confidence = match.confidence
        method = match.method

        if method == "new":
            self.product_matcher.add(original_name)
            canonical = original_name
            changes.append(f"New product: '{original_name}'")
        elif canonical != original_name:
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

    def apply_llm_product_names(self) -> int:
        """
        Apply LLM-normalized product names.

        Call this after classify_pending() has been run on the ProductNameClassifier.
        This consolidates products with different original names that map to the same
        canonical name (e.g., "Lg Coke" and "Large Coca-Cola" both become "Coca-Cola").

        Returns:
            Number of products consolidated.
        """
        if not self.product_name_classifier:
            return 0

        # Build mapping: old canonical -> new LLM canonical
        # and consolidate products
        new_products: dict[str, Product] = {}
        consolidated = 0

        for old_canonical, product in self.products_seen.items():
            # Get LLM canonical name for this product's original names
            # Use the first original name to get the canonical
            llm_canonical = old_canonical
            for orig_name in product.original_names:
                llm_name = self.product_name_classifier.get_canonical_name(orig_name)
                if llm_name and llm_name != orig_name:
                    llm_canonical = llm_name
                    break

            if llm_canonical in new_products:
                # Merge into existing product
                existing = new_products[llm_canonical]
                for orig in product.original_names:
                    if orig not in existing.original_names:
                        existing.original_names.append(orig)
                # Keep the category if the existing one is None
                if existing.category is None and product.category:
                    existing.category = product.category
                consolidated += 1
            else:
                # Update canonical name and add
                product.canonical_name = llm_canonical
                new_products[llm_canonical] = product

        self.products_seen = new_products

        if consolidated:
            logger.info(
                f"Consolidated {consolidated} products using LLM normalization "
                f"(now {len(new_products)} unique products)"
            )

        return consolidated
