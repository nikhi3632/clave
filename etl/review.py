"""CLI tool for reviewing category classifications."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

# Valid categories
VALID_CATEGORIES = ["Appetizers", "Breakfast", "Desserts", "Drinks", "Entrees", "Sides"]


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


def review_item(client, item: dict) -> bool:
    """
    Review a single item interactively.

    Returns True if reviewed, False if skipped.
    """
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
    print("  [1-6] Set custom category:")
    for i, cat in enumerate(VALID_CATEGORIES, 1):
        print(f"      {i}. {cat}")
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

        if choice.isdigit() and 1 <= int(choice) <= 6:
            cat = VALID_CATEGORIES[int(choice) - 1]
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


def show_stats(client) -> None:
    """Show review statistics."""
    # Get counts by status
    result = client.table("category_review_queue").select("status").execute()
    items = result.data or []

    stats = {"pending": 0, "approved": 0, "rejected": 0, "custom": 0}
    for item in items:
        stats[item["status"]] = stats.get(item["status"], 0) + 1

    # Get cache stats
    cache_result = client.table("product_category_cache").select("confidence").execute()
    cache_items = cache_result.data or []

    cache_stats = {}
    for item in cache_items:
        conf = item["confidence"]
        cache_stats[conf] = cache_stats.get(conf, 0) + 1

    print(f"\n{'='*40}")
    print("CATEGORY CLASSIFICATION STATS")
    print(f"{'='*40}")
    print("\nReview Queue:")
    print(f"  Pending:  {stats['pending']}")
    print(f"  Approved: {stats['approved']}")
    print(f"  Rejected: {stats['rejected']}")
    print(f"  Custom:   {stats['custom']}")

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

    items = show_pending(client)

    if not items:
        show_stats(client)
        return

    print("\nStart reviewing? [y/n]: ", end="")
    if input().strip().lower() != "y":
        return

    reviewed = 0
    for item in items:
        result = review_item(client, item)
        if result is None:  # Quit
            break
        if result:
            reviewed += 1

    print(f"\n{'='*40}")
    print(f"Reviewed {reviewed} items")
    show_stats(client)


if __name__ == "__main__":
    main()
