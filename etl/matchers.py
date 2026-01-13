"""Unified fuzzy matching for ETL pipeline.

All matchers follow the same pattern:
1. Exact match (normalized)
2. Phonetic match (sounds-like)
3. Fuzzy match (spelling similarity)
"""

import logging
import re
import unicodedata
from dataclasses import dataclass

from rapidfuzz import fuzz

from config import get_config
from models import Channel, Location

logger = logging.getLogger(__name__)


# =============================================================================
# UTILITIES
# =============================================================================


def normalize_text(text: str) -> str:
    """Normalize text: lowercase, strip, remove emojis, collapse whitespace."""
    if not text:
        return ""
    text = "".join(c for c in text if unicodedata.category(c) not in ("So", "Mn", "Cf"))
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def phonetic_key(text: str) -> str:
    """Generate phonetic key for sounds-like matching."""
    text = normalize_text(text)
    replacements = [
        (r"ph", "f"),
        (r"ck", "k"),
        (r"x", "ks"),
        (r"qu", "kw"),
        (r"c(?=[eiy])", "s"),
        (r"c", "k"),
        (r"gg", "g"),
        (r"ll", "l"),
        (r"ss", "s"),
        (r"tt", "t"),
        (r"wh", "w"),
        (r"wr", "r"),
        (r"kn", "n"),
        (r"gn", "n"),
        (r"mb$", "m"),
        (r"ie", "i"),
        (r"ei", "i"),
        (r"ee", "i"),
        (r"ea", "i"),
        (r"oo", "u"),
        (r"ou", "u"),
        (r"ow", "o"),
        (r"ay", "a"),
        (r"ey", "a"),
    ]
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)
    return text


# =============================================================================
# MATCH RESULTS
# =============================================================================


@dataclass(frozen=True)
class MatchResult:
    """Generic match result."""

    matched: str
    confidence: float
    method: str  # exact, phonetic, fuzzy, keyword, new, none


# =============================================================================
# PRODUCT MATCHER
# =============================================================================


class ProductMatcher:
    """Match product names to canonical forms."""

    def __init__(self, threshold: float | None = None):
        if threshold is None:
            threshold = get_config().matching.product_threshold
        self.threshold = threshold
        self._canonical: dict[str, str] = {}  # normalized -> canonical
        self._phonetic: dict[str, str] = {}  # phonetic -> canonical

    def add(self, name: str) -> None:
        """Add a canonical product name."""
        norm = normalize_text(name)
        self._canonical[norm] = name
        pkey = phonetic_key(name)
        if pkey:
            self._phonetic[pkey] = name

    def seed(self, names: list[str]) -> None:
        """Seed with existing product names."""
        for name in names:
            self.add(name)
        if names:
            logger.info(f"ProductMatcher seeded with {len(names)} products")

    def match(self, name: str) -> MatchResult:
        """Match a product name."""
        if not name:
            return MatchResult(matched=name, confidence=0.0, method="empty")

        norm = normalize_text(name)

        # Exact
        if norm in self._canonical:
            return MatchResult(matched=self._canonical[norm], confidence=1.0, method="exact")

        # Phonetic
        pkey = phonetic_key(name)
        if pkey in self._phonetic:
            return MatchResult(matched=self._phonetic[pkey], confidence=0.9, method="phonetic")

        # Fuzzy
        best, best_score = None, 0.0
        for canonical in self._canonical.values():
            score = max(
                fuzz.ratio(norm, normalize_text(canonical)) / 100,
                fuzz.partial_ratio(norm, normalize_text(canonical)) / 100,
                fuzz.token_sort_ratio(norm, normalize_text(canonical)) / 100,
            )
            if score > best_score:
                best_score, best = score, canonical

        if best and best_score >= self.threshold:
            return MatchResult(matched=best, confidence=best_score, method="fuzzy")

        # New product
        return MatchResult(matched=name, confidence=0.0, method="new")


# =============================================================================
# CATEGORY MATCHER
# =============================================================================


class CategoryMatcher:
    """Match and normalize category names."""

    def __init__(self, threshold: int | None = None):
        if threshold is None:
            threshold = get_config().matching.category_threshold
        self.threshold = threshold
        self._canonical: dict[str, str] = {}  # lowercase -> canonical
        self._phonetic: dict[str, str] = {}  # phonetic -> canonical

    def match(self, text: str) -> MatchResult:
        """Match a category name. Auto-registers new categories."""
        text = text.strip()
        if not text:
            return MatchResult(matched="", confidence=0.0, method="empty")

        text_lower = text.lower()

        # Exact
        if text_lower in self._canonical:
            return MatchResult(matched=self._canonical[text_lower], confidence=1.0, method="exact")

        # Phonetic
        pkey = phonetic_key(text_lower)
        if pkey and pkey in self._phonetic:
            return MatchResult(matched=self._phonetic[pkey], confidence=0.9, method="phonetic")

        # Fuzzy
        best, best_score = None, 0
        for known, canonical in self._canonical.items():
            score = fuzz.ratio(text_lower, known)
            if score > best_score and score >= self.threshold:
                best_score, best = score, canonical

        if best:
            return MatchResult(matched=best, confidence=best_score / 100, method="fuzzy")

        # New category - register and return
        canonical = text.title()
        self._canonical[text_lower] = canonical
        if pkey:
            self._phonetic[pkey] = canonical
        return MatchResult(matched=canonical, confidence=1.0, method="new")


# =============================================================================
# LOCATION MATCHER
# =============================================================================


class LocationMatcher:
    """Match strings to Location enum values."""

    def __init__(self, threshold: int | None = None):
        if threshold is None:
            threshold = get_config().matching.location_threshold
        self.threshold = threshold
        self._known: dict[str, Location] = {}
        self._phonetic: dict[str, Location] = {}
        self._seed_enum()

    def _seed_enum(self) -> None:
        """Seed with Location enum values."""
        for loc in Location:
            self._add(loc.value, loc)

    def _add(self, name: str, location: Location) -> None:
        norm = name.lower().strip()
        self._known[norm] = location
        pkey = phonetic_key(norm)
        if pkey:
            self._phonetic[pkey] = location

    def seed(self, names: list[str]) -> None:
        """Seed with database location names."""
        for name in names:
            name_lower = name.lower()
            for loc in Location:
                if loc.value.lower() == name_lower:
                    self._add(name, loc)
                    break
        if names:
            logger.info(f"LocationMatcher seeded with {len(names)} locations")

    def match(self, text: str) -> tuple[Location | None, str]:
        """Match text to Location. Returns (location, method)."""
        if not text:
            return None, "none"

        text_lower = text.lower().strip()

        # Exact
        if text_lower in self._known:
            return self._known[text_lower], "exact"

        # Phonetic
        pkey = phonetic_key(text_lower)
        if pkey and pkey in self._phonetic:
            return self._phonetic[pkey], "phonetic"

        # Keyword (substring)
        for known, loc in self._known.items():
            if known in text_lower or text_lower in known:
                return loc, "keyword"

        # Fuzzy
        best, best_score = None, 0
        for known, loc in self._known.items():
            score = fuzz.partial_ratio(text_lower, known)
            if score > best_score and score >= self.threshold:
                best_score, best = score, loc

        if best:
            return best, "fuzzy"

        logger.warning(f"Location not matched: '{text}'")
        return None, "none"


# =============================================================================
# CHANNEL MATCHER
# =============================================================================


class ChannelMatcher:
    """Match strings to Channel enum values."""

    KEYWORDS: dict[Channel, list[str]] = {
        Channel.DINE_IN: ["dine", "table", "eat in", "dine_in", "dine-in"],
        Channel.PICKUP: [
            "pickup",
            "pick up",
            "pick-up",
            "takeout",
            "take out",
            "take-out",
            "to go",
            "togo",
            "customer_pickup",
        ],
        Channel.DELIVERY: [
            "delivery",
            "deliver",
            "doordash",
            "uber",
            "grubhub",
            "merchant_delivery",
            "shipped",
        ],
    }

    def __init__(self, threshold: int | None = None):
        if threshold is None:
            threshold = get_config().matching.channel_threshold
        self.threshold = threshold

    def match(self, text: str) -> tuple[Channel, str]:
        """Match text to Channel. Returns (channel, method)."""
        if not text:
            return Channel.DINE_IN, "default"

        text_norm = text.lower().strip().replace("-", "_").replace(" ", "_")
        text_orig = text.lower().strip()

        # Exact enum match
        for channel in Channel:
            if text_norm == channel.value or text_orig == channel.value:
                return channel, "exact"

        # Keyword match
        for channel, keywords in self.KEYWORDS.items():
            for kw in keywords:
                kw_norm = kw.replace(" ", "_").replace("-", "_")
                if kw in text_orig or kw_norm in text_norm:
                    return channel, "keyword"

        # Fuzzy match
        best, best_score = Channel.DINE_IN, 0
        for channel, keywords in self.KEYWORDS.items():
            for kw in keywords:
                score = fuzz.ratio(text_norm, kw.replace(" ", "_"))
                if score > best_score and score >= self.threshold:
                    best_score, best = score, channel

        if best_score >= self.threshold:
            return best, "fuzzy"

        return Channel.DINE_IN, "default"


# =============================================================================
# MODULE-LEVEL INSTANCES (simple, no context object needed)
# =============================================================================

_product_matcher: ProductMatcher | None = None
_category_matcher: CategoryMatcher | None = None
_location_matcher: LocationMatcher | None = None
_channel_matcher: ChannelMatcher | None = None


def get_product_matcher() -> ProductMatcher:
    global _product_matcher
    if _product_matcher is None:
        _product_matcher = ProductMatcher()
    return _product_matcher


def get_category_matcher() -> CategoryMatcher:
    global _category_matcher
    if _category_matcher is None:
        _category_matcher = CategoryMatcher()
    return _category_matcher


def get_location_matcher() -> LocationMatcher:
    global _location_matcher
    if _location_matcher is None:
        _location_matcher = LocationMatcher()
    return _location_matcher


def get_channel_matcher() -> ChannelMatcher:
    global _channel_matcher
    if _channel_matcher is None:
        _channel_matcher = ChannelMatcher()
    return _channel_matcher


def reset_matchers() -> None:
    """Reset all matchers (for testing)."""
    global _product_matcher, _category_matcher, _location_matcher, _channel_matcher
    _product_matcher = None
    _category_matcher = None
    _location_matcher = None
    _channel_matcher = None
