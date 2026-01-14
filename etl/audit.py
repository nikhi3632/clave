"""Post-ETL audit for data quality and category normalization.

Finds similar categories and creates merge suggestions for human review.
"""

import logging
from dataclasses import dataclass

from rapidfuzz import fuzz
from supabase import Client

logger = logging.getLogger(__name__)


@dataclass
class CategoryCluster:
    """A cluster of similar categories."""

    categories: list[str]
    product_counts: list[int]


def find_similar_categories(
    categories_with_counts: list[tuple[str, int]],
    threshold: int = 70,
) -> list[CategoryCluster]:
    """
    Find clusters of similar category names.

    Uses multiple similarity checks:
    1. Fuzzy string similarity (threshold)
    2. Substring containment (one category contains another)
    3. Common prefix detection

    Args:
        categories_with_counts: List of (category, product_count) tuples.
        threshold: Fuzzy match threshold (0-100).

    Returns:
        List of CategoryCluster objects representing similar groups.
    """
    if not categories_with_counts:
        return []

    def are_similar(cat1: str, cat2: str) -> bool:
        """Check if two categories are similar using multiple methods."""
        c1, c2 = cat1.lower(), cat2.lower()

        # 1. Fuzzy string similarity
        if fuzz.ratio(c1, c2) >= threshold:
            return True

        # 2. One contains the other (e.g., "Beer & Wine" and "Wine")
        if c1 in c2 or c2 in c1:
            return True

        # 3. Partial ratio for substring matching
        if fuzz.partial_ratio(c1, c2) >= 90:
            return True

        # 4. Token sort ratio (handles word order differences)
        if fuzz.token_sort_ratio(c1, c2) >= 85:
            return True

        return False

    # Track which categories have been clustered
    clustered: set[str] = set()
    clusters: list[CategoryCluster] = []

    for i, (cat1, count1) in enumerate(categories_with_counts):
        if cat1 in clustered:
            continue

        # Start a new cluster with this category
        cluster_cats = [cat1]
        cluster_counts = [count1]
        clustered.add(cat1)

        # Find all similar categories
        for j, (cat2, count2) in enumerate(categories_with_counts):
            if i == j or cat2 in clustered:
                continue

            if are_similar(cat1, cat2):
                cluster_cats.append(cat2)
                cluster_counts.append(count2)
                clustered.add(cat2)

        # Only create cluster if there are multiple similar categories
        if len(cluster_cats) > 1:
            clusters.append(
                CategoryCluster(categories=cluster_cats, product_counts=cluster_counts)
            )

    return clusters


def get_categories_with_counts(client: Client) -> list[tuple[str, int]]:
    """Get all distinct categories with their product counts."""
    result = client.table("products").select("category").execute()

    # Count products per category
    counts: dict[str, int] = {}
    for row in result.data or []:
        cat = row.get("category")
        if cat:
            counts[cat] = counts.get(cat, 0) + 1

    return [(cat, count) for cat, count in counts.items()]


def get_existing_mappings(client: Client) -> dict[str, str]:
    """Load existing category mappings from database."""
    result = client.table("category_mappings").select("*").execute()

    mappings = {}
    for row in result.data or []:
        mappings[row["source_category"]] = row["canonical_category"]

    return mappings


def get_pending_merges(client: Client) -> list[list[str]]:
    """Get category variants that are already pending review."""
    result = (
        client.table("category_merge_queue")
        .select("category_variants")
        .eq("status", "pending")
        .execute()
    )

    pending = []
    for row in result.data or []:
        pending.append(row["category_variants"])

    return pending


def run_category_audit(client: Client, threshold: int = 80) -> int:
    """
    Run category audit and create merge suggestions.

    Args:
        client: Supabase client.
        threshold: Fuzzy match threshold (0-100).

    Returns:
        Number of new merge suggestions created.
    """
    logger.info("Running category audit...")

    # Get current categories
    categories_with_counts = get_categories_with_counts(client)
    logger.info(f"Found {len(categories_with_counts)} distinct categories")

    if not categories_with_counts:
        return 0

    # Get existing mappings - exclude already-mapped categories
    existing_mappings = get_existing_mappings(client)
    unmapped = [
        (cat, count)
        for cat, count in categories_with_counts
        if cat not in existing_mappings
    ]
    logger.info(
        f"After excluding mapped categories: {len(unmapped)} categories to check"
    )

    # Find similar category clusters
    clusters = find_similar_categories(unmapped, threshold=threshold)
    logger.info(f"Found {len(clusters)} clusters of similar categories")

    if not clusters:
        logger.info("No similar categories found - all categories are distinct")
        return 0

    # Get pending merges to avoid duplicates
    pending_merges = get_pending_merges(client)
    pending_sets = [set(variants) for variants in pending_merges]

    # Insert new merge suggestions
    new_count = 0
    for cluster in clusters:
        cluster_set = set(cluster.categories)

        # Skip if this cluster is already pending
        if any(cluster_set == pending for pending in pending_sets):
            logger.debug(f"Skipping already-pending cluster: {cluster.categories}")
            continue

        # Insert merge suggestion
        client.table("category_merge_queue").insert(
            {
                "category_variants": cluster.categories,
                "product_counts": cluster.product_counts,
                "status": "pending",
            }
        ).execute()

        new_count += 1
        logger.info(
            f"Created merge suggestion: {cluster.categories} "
            f"(products: {cluster.product_counts})"
        )

    logger.info(f"Category audit complete: {new_count} new merge suggestions")
    return new_count
