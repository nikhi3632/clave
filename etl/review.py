"""CLI tool for reviewing category classifications and merges."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client


def get_client():
    """Get Supabase client."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        print("Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
        sys.exit(1)
    return create_client(url, key)


def show_pending(client) -> list[dict]:
    """Show items pending review."""
    result = client.table("category_review_queue").select("*").eq(
        "status", "pending"
    ).order("confidence_score").execute()

    items = result.data or []

    if not items:
        print("\n✓ No items pending review!")
        return []

    print(f"\n{'='*60}")
    print(f"PENDING REVIEW: {len(items)} items")
    print(f"{'='*60}\n")

    for i, item in enumerate(items, 1):
        conf = item["confidence_score"]
        print(f"{i}. {item['product_name']}")
        print(f"   Source: {item['source_category'] or '(none)'}")
        print(f"   LLM:    {item['llm_category']} ({conf:.0%} confidence)")
        if item["reason"]:
            print(f"   Reason: {item['reason']}")
        print()

    return items


def get_known_categories(client) -> list[str]:
    """Get list of known categories from products."""
    result = client.table("products").select("category").execute()
    categories = set()
    for row in result.data or []:
        cat = row.get("category")
        if cat:
            categories.add(cat)
    return sorted(categories)


def review_item(client, item: dict) -> bool:
    """
    Review a single item interactively.

    Returns True if reviewed, False if skipped, None to quit.
    """
    # Get known categories dynamically
    known_categories = get_known_categories(client)

    print(f"\n{'─'*50}")
    print(f"Product: {item['product_name']}")
    print(f"Source said: {item['source_category'] or '(none)'}")
    print(f"LLM says: {item['llm_category']} ({item['confidence_score']:.0%})")
    if item["reason"]:
        print(f"Reason: {item['reason']}")
    print(f"{'─'*50}")

    print("\nOptions:")
    print("  [a] Approve LLM category")
    print("  [r] Revert to source category")
    if known_categories:
        print(f"  [1-{len(known_categories)}] Set to known category:")
        for i, cat in enumerate(known_categories, 1):
            print(f"      {i}. {cat}")
    print("  [c] Enter custom category")
    print("  [s] Skip")
    print("  [q] Quit")

    while True:
        choice = input("\nChoice: ").strip().lower()

        if choice == "q":
            return None  # Signal to quit

        if choice == "s":
            return False

        if choice == "a":
            # Approve LLM
            apply_review(client, item, item["llm_category"], "approved")
            print(f"  ✓ Approved: {item['llm_category']}")
            return True

        if choice == "r":
            if item["source_category"]:
                apply_review(client, item, item["source_category"], "rejected")
                print(f"  ✓ Reverted to: {item['source_category']}")
                return True
            else:
                print("  No source category to revert to!")
                continue

        if choice == "c":
            custom = input("  Enter category name: ").strip()
            if custom:
                apply_review(client, item, custom, "custom")
                print(f"  ✓ Set to: {custom}")
                return True
            print("  Category cannot be empty!")
            continue

        if choice.isdigit() and known_categories:
            idx = int(choice)
            if 1 <= idx <= len(known_categories):
                cat = known_categories[idx - 1]
                apply_review(client, item, cat, "custom")
                print(f"  ✓ Set to: {cat}")
                return True

        print("  Invalid choice, try again.")


def apply_review(client, item: dict, final_category: str, status: str) -> None:
    """Apply a review decision."""
    # Update review queue
    client.table("category_review_queue").update({
        "status": status,
        "final_category": final_category,
        "reviewed_at": "now()",
    }).eq("product_name", item["product_name"]).execute()

    # Update cache with reviewed category
    client.table("product_category_cache").update({
        "category": final_category,
        "confidence": "reviewed",
    }).eq("product_name", item["product_name"]).execute()

    # Update products table
    client.table("products").update({
        "category": final_category,
    }).eq("canonical_name", item["product_name"]).execute()


def show_pending_merges(client) -> list[dict]:
    """Show category merge suggestions pending review."""
    result = (
        client.table("category_merge_queue")
        .select("*")
        .eq("status", "pending")
        .execute()
    )

    items = result.data or []

    if not items:
        return []

    print(f"\n{'='*60}")
    print(f"CATEGORY MERGES: {len(items)} pending")
    print(f"{'='*60}\n")

    for i, item in enumerate(items, 1):
        variants = item["category_variants"]
        counts = item["product_counts"]
        print(f"{i}. Similar categories found:")
        for j, (var, count) in enumerate(zip(variants, counts), 1):
            print(f"      {j}. {var} ({count} products)")
        print()

    return items


def review_merge(client, item: dict) -> bool:
    """
    Review a category merge interactively.

    Returns True if merged, False if skipped, None to quit.
    """
    variants = item["category_variants"]
    counts = item["product_counts"]

    print(f"\n{'─'*50}")
    print("CATEGORY MERGE")
    print("These categories appear to be similar:")
    for i, (var, count) in enumerate(zip(variants, counts), 1):
        print(f"  {i}. {var} ({count} products)")
    print(f"{'─'*50}")

    print("\nOptions:")
    for i, var in enumerate(variants, 1):
        print(f"  [{i}] Use '{var}' as canonical")
    print("  [c] Enter custom canonical name")
    print("  [s] Skip (keep separate)")
    print("  [q] Quit")

    while True:
        choice = input("\nChoice: ").strip().lower()

        if choice == "q":
            return None

        if choice == "s":
            # Mark as skipped
            client.table("category_merge_queue").update({
                "status": "skipped",
                "reviewed_at": "now()",
            }).eq("id", item["id"]).execute()
            print("  ✓ Skipped - categories kept separate")
            return False

        if choice == "c":
            canonical = input("  Enter canonical category name: ").strip()
            if canonical:
                apply_merge(client, item, canonical)
                print(f"  ✓ Merged all to: {canonical}")
                return True
            print("  Category cannot be empty!")
            continue

        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(variants):
                canonical = variants[idx - 1]
                apply_merge(client, item, canonical)
                print(f"  ✓ Merged all to: {canonical}")
                return True

        print("  Invalid choice, try again.")


def apply_merge(client, item: dict, canonical: str) -> None:
    """Apply a category merge decision."""
    variants = item["category_variants"]

    # Create mappings for all non-canonical variants
    for variant in variants:
        if variant.lower() != canonical.lower():
            # Insert mapping (source -> canonical)
            client.table("category_mappings").upsert({
                "source_category": variant,
                "canonical_category": canonical,
                "created_by": "review",
            }, on_conflict="source_category").execute()

    # Update all products with variant categories to use canonical
    for variant in variants:
        if variant != canonical:
            client.table("products").update({
                "category": canonical,
            }).eq("category", variant).execute()

            # Also update cache
            client.table("product_category_cache").update({
                "category": canonical,
            }).eq("category", variant).execute()

    # Mark merge as complete
    client.table("category_merge_queue").update({
        "status": "merged",
        "canonical_category": canonical,
        "reviewed_at": "now()",
    }).eq("id", item["id"]).execute()


def show_stats(client) -> None:
    """Show review statistics."""
    # Get product review counts by status
    result = client.table("category_review_queue").select("status").execute()
    items = result.data or []

    stats = {"pending": 0, "approved": 0, "rejected": 0, "custom": 0}
    for item in items:
        stats[item["status"]] = stats.get(item["status"], 0) + 1

    # Get category merge counts
    merge_result = client.table("category_merge_queue").select("status").execute()
    merge_items = merge_result.data or []

    merge_stats = {"pending": 0, "merged": 0, "skipped": 0}
    for item in merge_items:
        merge_stats[item["status"]] = merge_stats.get(item["status"], 0) + 1

    # Get mapping count
    mapping_result = client.table("category_mappings").select("id", count="exact").execute()
    mapping_count = mapping_result.count or 0

    # Get cache stats
    cache_result = client.table("product_category_cache").select("confidence").execute()
    cache_items = cache_result.data or []

    cache_stats = {}
    for item in cache_items:
        conf = item["confidence"]
        cache_stats[conf] = cache_stats.get(conf, 0) + 1

    print(f"\n{'='*40}")
    print("CATEGORY REVIEW STATS")
    print(f"{'='*40}")

    print("\nProduct Reviews:")
    print(f"  Pending:  {stats['pending']}")
    print(f"  Approved: {stats['approved']}")
    print(f"  Rejected: {stats['rejected']}")
    print(f"  Custom:   {stats['custom']}")

    print("\nCategory Merges:")
    print(f"  Pending:  {merge_stats['pending']}")
    print(f"  Merged:   {merge_stats['merged']}")
    print(f"  Skipped:  {merge_stats['skipped']}")
    print(f"  Mappings: {mapping_count}")

    print("\nCache by Confidence:")
    for conf, count in sorted(cache_stats.items()):
        print(f"  {conf}: {count}")


def main():
    """CLI entry point."""
    # Try to load .env if running locally (not in Docker)
    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file)

    client = get_client()

    if len(sys.argv) > 1 and sys.argv[1] == "--stats":
        show_stats(client)
        return

    # Check for category merges first
    merges = show_pending_merges(client)
    products = show_pending(client)

    if not merges and not products:
        show_stats(client)
        return

    total_reviewed = 0

    # Review category merges first (affects product categories)
    if merges:
        print("\nReview category merges first? [y/n]: ", end="")
        if input().strip().lower() == "y":
            for item in merges:
                result = review_merge(client, item)
                if result is None:  # Quit
                    print(f"\n{'='*40}")
                    print(f"Reviewed {total_reviewed} items total")
                    show_stats(client)
                    return
                if result:
                    total_reviewed += 1

    # Then review product categories
    if products:
        print("\nReview product categories? [y/n]: ", end="")
        if input().strip().lower() == "y":
            for item in products:
                result = review_item(client, item)
                if result is None:  # Quit
                    break
                if result:
                    total_reviewed += 1

    print(f"\n{'='*40}")
    print(f"Reviewed {total_reviewed} items total")
    show_stats(client)


if __name__ == "__main__":
    main()
