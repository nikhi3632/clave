"""LLM-based product category classification with caching and mapping."""

import json
import logging
import os
from dataclasses import dataclass

from supabase import Client

from exceptions import ETLError
from llm_client import get_client

logger = logging.getLogger(__name__)

# Default model for classification
DEFAULT_MODEL = "claude-sonnet-4-20250514"

# Confidence thresholds (configurable via env)
AUTO_APPROVE_THRESHOLD = float(os.environ.get("AUTO_APPROVE_THRESHOLD", "0.9"))
REVIEW_THRESHOLD = float(os.environ.get("REVIEW_THRESHOLD", "0.7"))


@dataclass
class CategoryResult:
    """Result of category classification."""

    category: str
    confidence: str  # 'source', 'llm', 'llm_auto', 'reviewed', 'manual'
    score: float = 1.0  # 0.0-1.0 confidence score
    reason: str = ""  # Why this category was chosen


@dataclass
class LLMClassification:
    """Single classification result from LLM."""

    category: str
    score: float  # 0.0-1.0
    reason: str


@dataclass
class ClassificationStats:
    """Statistics about LLM classification results."""

    total: int = 0
    from_cache: int = 0
    llm_agreed: int = 0  # LLM agreed with source hint
    llm_auto_approved: int = 0  # LLM override auto-approved (high confidence)
    llm_needs_review: int = 0  # LLM override flagged for review
    no_source_hint: int = 0  # No source category provided


class CategoryClassifier:
    """Classify products into categories using mappings and LLM with caching.

    Category assignment flow:
    1. Check if source category has a user-defined mapping -> use mapped category
    2. Check if source category matches an existing category -> use as-is
    3. Otherwise queue for LLM classification -> may be flagged for review
    """

    def __init__(self, supabase_client: Client):
        """
        Initialize the classifier.

        Args:
            supabase_client: Supabase client for cache operations.
        """
        self.client = supabase_client
        self._cache: dict[str, CategoryResult] = {}
        self._pending_classifications: dict[str, str] = {}
        self.stats = ClassificationStats()
        self.needs_review: list[dict] = []  # Items flagged for human review

        # Category mappings (source -> canonical) loaded from DB
        self._category_mappings: dict[str, str] = {}
        # Known categories (from products with orders)
        self._known_categories: set[str] = set()

        # Initialize LLM provider
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ETLError("ANTHROPIC_API_KEY must be set for category classification")

        self.model = os.environ.get("LLM_MODEL", DEFAULT_MODEL)
        self._provider = get_client(
            api_key=api_key,
            model=self.model,
            provider=os.environ.get("LLM_PROVIDER", "anthropic"),
        )

    def load_cache(self) -> int:
        """
        Load existing classifications, mappings, and known categories from database.

        Returns:
            Number of cached entries loaded.
        """
        # Load product category cache
        try:
            result = self.client.table("product_category_cache").select("*").execute()

            for row in result.data or []:
                self._cache[row["product_name"].lower()] = CategoryResult(
                    category=row["category"],
                    confidence=row["confidence"],
                )

            logger.info(f"Loaded {len(self._cache)} cached category classifications")

        except Exception as e:
            logger.warning(f"Could not load category cache: {e}")

        # Load category mappings (user-curated)
        try:
            result = self.client.table("category_mappings").select("*").execute()

            for row in result.data or []:
                self._category_mappings[row["source_category"].lower()] = row[
                    "canonical_category"
                ]

            if self._category_mappings:
                logger.info(f"Loaded {len(self._category_mappings)} category mappings")

        except Exception as e:
            logger.debug(f"Could not load category mappings: {e}")

        # Load known categories from products that have been ordered (trusted)
        try:
            result = self.client.table("products").select("category").execute()

            for row in result.data or []:
                cat = row.get("category")
                if cat:
                    self._known_categories.add(cat)

            if self._known_categories:
                logger.info(f"Found {len(self._known_categories)} known categories")

        except Exception as e:
            logger.debug(f"Could not load known categories: {e}")

        return len(self._cache)

    def get_category(
        self, product_name: str, source_category: str | None = None
    ) -> CategoryResult | None:
        """
        Get category for a product, using cache or queuing for LLM classification.

        Args:
            product_name: Name of the product.
            source_category: Category hint from source data (passed to LLM as context).

        Returns:
            CategoryResult if found in cache, None if needs LLM classification.
        """
        # Normalize for lookup
        name_lower = product_name.lower()
        self.stats.total += 1

        # Check cache first (from previous runs)
        if name_lower in self._cache:
            self.stats.from_cache += 1
            return self._cache[name_lower]

        # Queue for LLM classification with source hint
        if product_name not in self._pending_classifications:
            # Store source category as hint (or empty string if none)
            self._pending_classifications[product_name] = f"hint:{source_category or ''}"

        return None

    def _normalize_category(self, category: str) -> str | None:
        """
        Normalize a category string using mappings and known categories.

        Priority:
        1. Check user-defined mappings (source -> canonical)
        2. Check exact match against known categories
        3. Check case-insensitive match against known categories
        4. Return cleaned category as-is (new category)

        Args:
            category: Raw category string.

        Returns:
            Normalized category or None if empty.
        """
        if not category:
            return None

        # Remove emojis and clean
        import unicodedata

        cleaned = "".join(
            c for c in category if unicodedata.category(c) not in ("So", "Mn", "Cf")
        )
        cleaned = cleaned.strip()

        if not cleaned:
            return None

        cleaned_lower = cleaned.lower()

        # 1. Check user-defined mappings first
        if cleaned_lower in self._category_mappings:
            return self._category_mappings[cleaned_lower]

        # 2. Check for exact match against known categories
        if cleaned in self._known_categories:
            return cleaned

        # 3. Check for case-insensitive match against known categories
        for known in self._known_categories:
            if cleaned_lower == known.lower():
                return known

        # 4. Return title-cased version as a new category
        return cleaned.title()

    def classify_pending(self, batch_size: int = 20) -> int:
        """
        Classify all pending products using LLM.

        Args:
            batch_size: Number of products to classify per LLM call.

        Returns:
            Number of products classified.
        """
        # Get products that need classification (starts with "hint:")
        to_classify = {
            name: val.replace("hint:", "") if val.startswith("hint:") else ""
            for name, val in self._pending_classifications.items()
            if val.startswith("hint:")
        }

        if not to_classify:
            logger.debug("No products need LLM classification")
            return 0

        logger.info(f"Classifying {len(to_classify)} products with LLM...")

        classified = 0
        items = list(to_classify.items())

        for i in range(0, len(items), batch_size):
            batch = items[i : i + batch_size]
            batch_with_hints = {name: hint for name, hint in batch}

            try:
                results = self._classify_batch(batch_with_hints)

                for name, llm_result in results.items():
                    name_lower = name.lower()
                    source_hint = batch_with_hints.get(name, "")
                    category = llm_result.category

                    # Determine confidence level and whether review is needed
                    normalized_hint = self._normalize_category(source_hint) if source_hint else None

                    if not source_hint:
                        # No source hint - trust LLM
                        self.stats.no_source_hint += 1
                        confidence_type = "llm"
                    elif normalized_hint == category:
                        # LLM agrees with source
                        self.stats.llm_agreed += 1
                        confidence_type = "llm"
                    elif llm_result.score >= AUTO_APPROVE_THRESHOLD:
                        # High confidence override - auto-approve
                        self.stats.llm_auto_approved += 1
                        confidence_type = "llm_auto"
                        logger.debug(
                            f"Auto-approved ({llm_result.score:.0%}): "
                            f"{name} → {category} (was: {source_hint})"
                        )
                    else:
                        # Below threshold - flag for review
                        self.stats.llm_needs_review += 1
                        confidence_type = "llm"
                        self.needs_review.append({
                            "product_name": name,
                            "source_category": source_hint,
                            "llm_category": category,
                            "confidence": llm_result.score,
                            "reason": llm_result.reason,
                        })

                    self._cache[name_lower] = CategoryResult(
                        category=category,
                        confidence=confidence_type,
                        score=llm_result.score,
                        reason=llm_result.reason,
                    )
                    self._pending_classifications[name] = category
                    classified += 1

            except Exception as e:
                logger.error(f"LLM classification failed for batch: {e}")
                # Continue with next batch

        logger.info(f"Classified {classified} products with LLM")
        self._log_stats()
        return classified

    def _log_stats(self) -> None:
        """Log classification statistics."""
        llm_total = (
            self.stats.llm_agreed
            + self.stats.llm_auto_approved
            + self.stats.llm_needs_review
            + self.stats.no_source_hint
        )
        if llm_total == 0:
            return

        logger.info(
            f"LLM stats: {self.stats.llm_agreed} agreed, "
            f"{self.stats.llm_auto_approved} auto-approved, "
            f"{self.stats.llm_needs_review} need review, "
            f"{self.stats.no_source_hint} no source"
        )

        if self.needs_review:
            logger.info(f"Items flagged for review: {len(self.needs_review)}")
            for item in self.needs_review:
                logger.info(
                    f"  - {item['product_name']}: {item['source_category']} → "
                    f"{item['llm_category']} ({item['confidence']:.0%}) - {item['reason']}"
                )

    def _classify_batch(self, products: dict[str, str]) -> dict[str, LLMClassification]:
        """
        Classify a batch of products using Claude.

        Args:
            products: Dict mapping product names to source category hints.

        Returns:
            Dict mapping product names to LLMClassification objects.
        """
        # Format products with hints
        products_info = []
        for name, hint in products.items():
            if hint:
                products_info.append(f"{name} (source says: {hint})")
            else:
                products_info.append(name)

        # Build category context from known categories
        known_list = sorted(self._known_categories) if self._known_categories else []
        category_guidance = ""
        if known_list:
            category_guidance = f"""Known categories in this system (prefer these if applicable):
{json.dumps(known_list)}

"""

        prompt = f"""Classify these restaurant menu items into categories.

{category_guidance}Products to classify:
{json.dumps(products_info)}

Guidelines:
- Use standard restaurant category names (Entrees, Appetizers, Sides, Drinks, Desserts, Breakfast)
- If a known category fits, use it exactly
- Main dishes (burgers, sandwiches, steaks, pasta) → typically "Entrees"
- Starters (wings, nachos, dips) → typically "Appetizers"
- Coffee, soda, beer, wine, cocktails → typically "Drinks"
- Sweet items (cake, ice cream, churros) → typically "Desserts"

NOTE: Some items include "(source says: X)" hints from POS data.
Use these as context but trust your judgment - the source may be wrong.

Respond with a JSON object. For each product, provide:
- category: the category name (use title case, e.g., "Drinks" not "drinks")
- confidence: 0.0-1.0 (1.0 = certain, 0.5 = ambiguous/could be multiple)
- reason: brief explanation, especially if overriding source or uncertain

Example:
{{
  "House Wine": {{"category": "Drinks", "confidence": 1.0, "reason": "Wine is a drink"}},
  "Chicken Wings": {{"category": "Appetizers", "confidence": 0.7, "reason": "Could be entree"}}
}}"""

        response = self._provider.complete_sync(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
        )

        # Parse response
        content = response.content.strip()

        # Handle markdown code blocks
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1])

        try:
            result = json.loads(content)

            # Parse into LLMClassification objects
            validated: dict[str, LLMClassification] = {}
            for name, data in result.items():
                if isinstance(data, dict):
                    category = data.get("category", "Entrees")
                    confidence = float(data.get("confidence", 0.8))
                    reason = data.get("reason", "")
                else:
                    # Fallback for simple format
                    category = data
                    confidence = 0.8
                    reason = ""

                # Normalize category (applies mappings and known categories)
                normalized = self._normalize_category(category)
                if normalized:
                    category = normalized

                validated[name] = LLMClassification(
                    category=category,
                    score=confidence,
                    reason=reason,
                )

            return validated

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            logger.debug(f"Response was: {content}")
            return {}

    def save_cache(self) -> int:
        """
        Save new classifications to database.

        Returns:
            Number of entries saved.
        """
        # Get entries that have classifications (skip unprocessed "hint:" entries)
        to_save = []
        for name, cat in self._pending_classifications.items():
            # Skip unprocessed entries (still have hint: prefix)
            if not cat or cat.startswith("hint:"):
                continue

            cache_entry = self._cache.get(name.lower(), CategoryResult("", "llm"))

            # Find source hint if it was stored
            source_hint = None
            for item in self.needs_review:
                if item["product_name"] == name:
                    source_hint = item["source_category"]
                    break

            to_save.append({
                "product_name": name,
                "category": cat,
                "confidence": cache_entry.confidence,
                "score": cache_entry.score,
                "reason": cache_entry.reason,
                "source_category": source_hint,
            })

        if not to_save:
            return 0

        try:
            # Upsert to handle duplicates
            self.client.table("product_category_cache").upsert(
                to_save, on_conflict="product_name"
            ).execute()

            logger.info(f"Saved {len(to_save)} category classifications to cache")

            # Also save items that need review to the review queue
            self._save_review_queue()

            return len(to_save)

        except Exception as e:
            logger.error(f"Failed to save category cache: {e}")
            return 0

    def _save_review_queue(self) -> None:
        """Save items needing review to the review queue table."""
        if not self.needs_review:
            return

        to_save = [
            {
                "product_name": item["product_name"],
                "source_category": item["source_category"],
                "llm_category": item["llm_category"],
                "confidence_score": item["confidence"],
                "reason": item["reason"],
                "status": "pending",
            }
            for item in self.needs_review
        ]

        try:
            self.client.table("category_review_queue").upsert(
                to_save, on_conflict="product_name"
            ).execute()
            logger.info(f"Saved {len(to_save)} items to review queue")
        except Exception as e:
            logger.error(f"Failed to save review queue: {e}")

    def get_cached_category(self, product_name: str) -> str | None:
        """
        Get the final cached category for a product.

        Args:
            product_name: Name of the product.

        Returns:
            Category string or None.
        """
        name_lower = product_name.lower()
        if name_lower in self._cache:
            return self._cache[name_lower].category

        # Check pending classifications, but only return if actually classified
        # (not still waiting with "hint:" prefix)
        pending = self._pending_classifications.get(product_name)
        if pending and not pending.startswith("hint:"):
            return pending
        return None


# =============================================================================
# PRODUCT NAME CLASSIFIER
# =============================================================================


@dataclass
class ProductNameResult:
    """Result of product name normalization."""

    canonical_name: str
    confidence: str  # 'exact', 'llm', 'llm_auto', 'reviewed', 'manual'
    score: float = 1.0
    reason: str = ""


@dataclass
class ProductNameStats:
    """Statistics about product name normalization."""

    total: int = 0
    from_cache: int = 0
    llm_normalized: int = 0


class ProductNameClassifier:
    """Normalize product names using LLM with caching.

    Maps variant names to canonical forms:
    - "Lg Coke" → "Coca-Cola"
    - "Griled Chiken" → "Grilled Chicken"
    - "fountain soda" → "Coca-Cola"
    - "Churros 12pcs" → "Churros"
    """

    def __init__(self, supabase_client: Client):
        """Initialize the classifier."""
        self.client = supabase_client
        self._cache: dict[str, ProductNameResult] = {}  # lowercase original → result
        self._pending: set[str] = set()  # Original names needing classification
        self.stats = ProductNameStats()

        # Initialize LLM provider
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ETLError("ANTHROPIC_API_KEY must be set for product name classification")

        self.model = os.environ.get("LLM_MODEL", DEFAULT_MODEL)
        self._provider = get_client(
            api_key=api_key,
            model=self.model,
            provider=os.environ.get("LLM_PROVIDER", "anthropic"),
        )

    def load_cache(self) -> int:
        """Load existing mappings from database."""
        try:
            result = self.client.table("product_name_cache").select("*").execute()

            for row in result.data or []:
                self._cache[row["original_name"].lower()] = ProductNameResult(
                    canonical_name=row["canonical_name"],
                    confidence=row["confidence"],
                    score=row.get("score", 1.0),
                    reason=row.get("reason", ""),
                )

            logger.info(f"Loaded {len(self._cache)} cached product name mappings")
            return len(self._cache)

        except Exception as e:
            logger.warning(f"Could not load product name cache: {e}")
            return 0

    def add_product(self, original_name: str) -> str | None:
        """
        Add a product name for normalization.

        Args:
            original_name: Original product name from source.

        Returns:
            Canonical name if found in cache, None if needs LLM classification.
        """
        if not original_name or not original_name.strip():
            return None

        original_name = original_name.strip()
        name_lower = original_name.lower()
        self.stats.total += 1

        # Check cache first
        if name_lower in self._cache:
            self.stats.from_cache += 1
            return self._cache[name_lower].canonical_name

        # Queue for LLM classification
        self._pending.add(original_name)
        return None

    def classify_pending(self, batch_size: int = 30) -> int:
        """
        Normalize all pending product names using LLM.

        Args:
            batch_size: Number of products to process per LLM call.

        Returns:
            Number of products normalized.
        """
        if not self._pending:
            logger.debug("No product names need LLM normalization")
            return 0

        pending_list = list(self._pending)
        logger.info(f"Normalizing {len(pending_list)} product names with LLM...")

        classified = 0

        for i in range(0, len(pending_list), batch_size):
            batch = pending_list[i : i + batch_size]

            try:
                results = self._normalize_batch(batch)

                for original, result in results.items():
                    name_lower = original.lower()
                    self._cache[name_lower] = result
                    self._pending.discard(original)
                    classified += 1
                    self.stats.llm_normalized += 1

            except Exception as e:
                logger.error(f"LLM product normalization failed for batch: {e}")
                # Continue with next batch

        logger.info(
            f"Normalized {classified} product names "
            f"(cache: {self.stats.from_cache}, llm: {self.stats.llm_normalized})"
        )
        return classified

    def _normalize_batch(self, products: list[str]) -> dict[str, ProductNameResult]:
        """
        Normalize a batch of product names using Claude.

        Args:
            products: List of original product names.

        Returns:
            Dict mapping original names to ProductNameResult.
        """
        prompt = f"""You are normalizing restaurant product names from multiple POS systems.

Given these product names, map each to a canonical (standard) product name.

RULES:
1. Fix typos: "Griled Chiken" → "Grilled Chicken"
2. Expand abbreviations: "Lg Coke" → "Coca-Cola", "Sm Fries" → "French Fries"
3. Recognize equivalents: "fountain soda", "Coke", "Coca-Cola" → "Coca-Cola"
4. Strip sizes/quantities from canonical name: "Churros 12pcs" → "Churros"
5. Normalize case: "NACHOS SUPREME" → "Nachos Supreme"
6. Keep canonical names clean and consistent

Product names to normalize:
{json.dumps(products, indent=2)}

Respond with a JSON object mapping each original name to its normalized form:
{{
  "original_name": {{
    "canonical": "Canonical Name",
    "confidence": 0.95,
    "reason": "brief explanation"
  }}
}}

Example:
{{
  "Lg Coke": {{"canonical": "Coca-Cola", "confidence": 0.95, "reason": "Lg=Large"}},
  "Griled Chiken": {{"canonical": "Grilled Chicken", "confidence": 1.0, "reason": "Typo"}},
  "fountain soda": {{"canonical": "Coca-Cola", "confidence": 0.8, "reason": "Generic soda"}},
  "Churros 12pcs": {{"canonical": "Churros", "confidence": 1.0, "reason": "Stripped qty"}}
}}"""

        response = self._provider.complete_sync(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
        )

        content = response.content.strip()

        # Handle markdown code blocks
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1])

        try:
            result = json.loads(content)
            validated: dict[str, ProductNameResult] = {}

            for original, data in result.items():
                if isinstance(data, dict):
                    canonical = data.get("canonical", original)
                    confidence = float(data.get("confidence", 0.8))
                    reason = data.get("reason", "")
                else:
                    # Simple format fallback
                    canonical = str(data)
                    confidence = 0.8
                    reason = ""

                # Clean up canonical name
                canonical = canonical.strip()
                if not canonical:
                    canonical = original

                validated[original] = ProductNameResult(
                    canonical_name=canonical,
                    confidence="llm",
                    score=confidence,
                    reason=reason,
                )

            return validated

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            logger.debug(f"Response was: {content}")
            return {}

    def get_canonical_name(self, original_name: str) -> str:
        """
        Get the canonical name for a product.

        Args:
            original_name: Original product name.

        Returns:
            Canonical name (or original if not found).
        """
        if not original_name:
            return original_name

        name_lower = original_name.lower()
        if name_lower in self._cache:
            return self._cache[name_lower].canonical_name

        # Not in cache, return original
        return original_name

    def save_cache(self) -> int:
        """Save new mappings to database."""
        to_save = []

        for original_lower, result in self._cache.items():
            # Find original casing from pending or use lowercase
            original = original_lower
            for pending in self._pending:
                if pending.lower() == original_lower:
                    original = pending
                    break

            to_save.append({
                "original_name": original,
                "canonical_name": result.canonical_name,
                "confidence": result.confidence,
                "score": result.score,
                "reason": result.reason,
            })

        if not to_save:
            return 0

        try:
            self.client.table("product_name_cache").upsert(
                to_save, on_conflict="original_name"
            ).execute()

            logger.info(f"Saved {len(to_save)} product name mappings to cache")
            return len(to_save)

        except Exception as e:
            logger.error(f"Failed to save product name cache: {e}")
            return 0
