"""
Embed all courses from planner_courses.json into Supabase pgvector.
Skips courses that already have embeddings in the DB (safe to re-run).

Run from project root:
  python scripts/embed_all_courses.py

Flags:
  --force    Re-embed and overwrite ALL courses (even ones already in DB)
  --dry-run  Print what would be embedded without hitting any API
"""
import os
import sys
import json
import time
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from google import genai
from supabase import create_client

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))


def embed(text: str) -> list[float]:
    r = client.models.embed_content(
        model="gemini-embedding-001",
        contents=text,
        config={"output_dimensionality": 768},
    )
    values = list(r.embeddings[0].values)
    norm = sum(v * v for v in values) ** 0.5
    return [v / norm for v in values]


def build_text(c: dict) -> str:
    """Build the text blob we embed for a course."""
    parts = [f"{c['code']} — {c.get('title') or c.get('name', '')}"]

    desc = (c.get("description") or "").strip()
    if desc:
        parts.append(desc)

    req = (c.get("requirements") or "").strip()
    if req:
        parts.append(req)

    # UWFlow rating hints
    liked = c.get("_liked")
    easy = c.get("_easy")
    ratings = c.get("_ratings", 0)
    if liked is not None and ratings and ratings > 5:
        hints = []
        if liked is not None:
            hints.append(f"{round(liked * 100)}% liked")
        if easy is not None:
            hints.append(f"{round(easy * 100)}% found it easy")
        parts.append("UWFlow: " + ", ".join(hints) + f" ({ratings} ratings)")

    text = " ".join(parts)
    # Truncate to ~1800 chars to stay safely under the 2048-token embedding limit
    return text[:1800]


def fetch_existing_codes() -> set[str]:
    """Fetch all course codes already in Supabase."""
    rows = supabase.table("courses").select("code").execute()
    return {r["code"] for r in (rows.data or [])}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Re-embed all, overwrite existing")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without calling APIs")
    args = parser.parse_args()

    with open(os.path.join(ROOT, "planner_courses.json")) as f:
        all_courses = json.load(f)

    print(f"Loaded {len(all_courses)} courses from planner_courses.json")

    if args.dry_run:
        print("\n[DRY RUN] Would embed:")
        for c in all_courses[:5]:
            print(f"  {c['code']}: {build_text(c)[:80]}...")
        print(f"  ... and {len(all_courses) - 5} more")
        return

    if args.force:
        print("--force: deleting all existing embeddings...")
        supabase.table("courses").delete().neq("id", 0).execute()
        existing = set()
    else:
        existing = fetch_existing_codes()
    print(f"Already in Supabase: {len(existing)} courses")

    to_embed = [c for c in all_courses if c["code"] not in existing]
    print(f"Need to embed: {len(to_embed)} courses\n")

    if not to_embed:
        print("Nothing to do — all courses already embedded.")
        return

    ok = 0
    errors = []
    for i, c in enumerate(to_embed, 1):
        text = build_text(c)
        try:
            vec = embed(text)
            supabase.table("courses").insert(
                {"code": c["code"], "text": text, "embedding": vec}
            ).execute()
            ok += 1
            print(f"[{i}/{len(to_embed)}] ✓ {c['code']}")
        except Exception as e:
            print(f"[{i}/{len(to_embed)}] ✗ {c['code']}: {e}")
            errors.append(c["code"])
            time.sleep(2)
        # ~10 req/s is safe for Gemini embedding free tier
        time.sleep(0.12)

    print(f"\nDone. Embedded: {ok}  Errors: {len(errors)}")
    if errors:
        print("Failed codes:", errors)


if __name__ == "__main__":
    main()
