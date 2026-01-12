"""LLM-based product category classification with caching."""

import json
import logging
import os
from dataclasses import dataclass

from anthropic import Anthropic
from supabase import Client

from .exceptions import ETLError

logger = logging.getLogger(__name__)

# Valid categories matching the schema
VALID_CATEGORIES = [
    "Appetizers",
    "Breakfast",
    "Desserts",
    "Drinks",
    "Entrees",
    "Sides",
]

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
    """Classify products into categories using LLM with caching."""

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

        # Initialize Anthropic client
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ETLError("ANTHROPIC_API_KEY must be set for category classification")

        self.anthropic = Anthropic(api_key=api_key)
        self.model = os.environ.get("LLM_MODEL", DEFAULT_MODEL)

    def load_cache(self) -> int:
        """
        Load existing classifications from database.

        Returns:
            Number of cached entries loaded.
        """
        try:
            result = self.client.table("product_category_cache").select("*").execute()

            for row in result.data or []:
                self._cache[row["product_name"].lower()] = CategoryResult(
                    category=row["category"],
                    confidence=row["confidence"],
                )

            logger.info(f"Loaded {len(self._cache)} cached category classifications")
            return len(self._cache)

        except Exception as e:
            logger.warning(f"Could not load category cache: {e}")
            return 0

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
        Normalize a category string to a valid category.

        Args:
            category: Raw category string.

        Returns:
            Normalized category or None if invalid.
        """
        if not category:
            return None

        # Remove emojis and clean
        import unicodedata

        cleaned = "".join(c for c in category if unicodedata.category(c) not in ("So", "Mn", "Cf"))
        cleaned = cleaned.strip()

        if not cleaned:
            return None

        # Check for exact match (case-insensitive)
        for valid in VALID_CATEGORIES:
            if cleaned.lower() == valid.lower():
                return valid

        # Check for partial match
        for valid in VALID_CATEGORIES:
            if valid.lower() in cleaned.lower():
                return valid

        return None

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

        prompt = f"""Classify these restaurant menu items into categories.

Valid categories (use EXACTLY these):
{json.dumps(VALID_CATEGORIES)}

Products to classify:
{json.dumps(products_info)}

Rules:
- Burgers, sandwiches, steaks, pasta, main dishes → Entrees
- Wings, nachos, dips, small plates → Appetizers
- Fries, coleslaw, sides → Sides
- Coffee, soda, beer, wine, cocktails → Drinks
- Pancakes, eggs, waffles, breakfast items → Breakfast
- Cake, ice cream, churros, sweet items → Desserts

NOTE: Some items include "(source says: X)" hints from POS data.
Use these as context but trust your judgment - the source may be wrong.

Respond with a JSON object. For each product, provide:
- category: the category name
- confidence: 0.0-1.0 (1.0 = certain, 0.5 = ambiguous/could be multiple)
- reason: brief explanation, especially if overriding source or uncertain

Example:
{{
  "House Wine": {{"category": "Drinks", "confidence": 1.0, "reason": "Wine is a drink"}},
  "Chicken Wings": {{"category": "Appetizers", "confidence": 0.7, "reason": "Could be entree"}}
}}"""

        response = self.anthropic.messages.create(
            model=self.model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        # Parse response
        content = response.content[0].text.strip()

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

                # Validate category
                if category not in VALID_CATEGORIES:
                    normalized = self._normalize_category(category)
                    category = normalized or "Entrees"

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
        # Get entries that have classifications
        to_save = []
        for name, cat in self._pending_classifications.items():
            if cat:  # Only save if category is set
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
        return self._pending_classifications.get(product_name) or None
