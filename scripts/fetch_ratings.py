"""
Scrape UWFlow for course ratings, descriptions, and prereq text.
Updates data/ratings_raw.json and merges fresh ratings into data/course_catalog.json.

Run from project root:
  python scripts/fetch_ratings.py

Flags:
  --json-only   Only write ratings_raw.json, skip course_catalog.json update
  --dry-run     Print summary without writing files
"""
import os
import re
import sys
import json
import time
import argparse

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")

UWFLOW_URL = "https://uwflow.com/graphql"
SUBJECTS = ["cs", "math", "stat", "amath", "co", "pmath", "actsc"]

QUERY = """
query GetBySubject($prefix: String!) {
  course(where: {code: {_like: $prefix}}, order_by: {code: asc}) {
    code
    name
    description
    prereqs
    antireqs
    rating {
      liked
      easy
      useful
      filled_count
      comment_count
    }
  }
}
"""


def normalize_code(raw: str) -> str:
    """'cs135' -> 'CS 135', 'amath231' -> 'AMATH 231'"""
    m = re.match(r"([a-z]+)(\d+.*)", raw.strip().lower())
    if not m:
        return raw.upper()
    return f"{m.group(1).upper()} {m.group(2).upper()}"


def fetch_subject(subject: str) -> list[dict]:
    payload = {
        "query": QUERY,
        "variables": {"prefix": f"{subject}%"},
    }
    r = requests.post(
        UWFLOW_URL,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=20,
    )
    r.raise_for_status()
    return r.json().get("data", {}).get("course", [])


def build_entry(raw: dict) -> dict:
    code = normalize_code(raw["code"])
    rating = raw.get("rating") or {}
    entry = {
        "code": code,
        "name": raw.get("name") or "",
        "description": (raw.get("description") or "").strip(),
        "prereqs": (raw.get("prereqs") or "").strip(),
        "antireqs": (raw.get("antireqs") or "").strip(),
    }
    if rating.get("filled_count"):
        entry["liked"] = rating.get("liked")
        entry["easy"] = rating.get("easy")
        entry["useful"] = rating.get("useful")
        entry["num_ratings"] = rating.get("filled_count", 0)
        entry["num_comments"] = rating.get("comment_count", 0)
    return entry


def is_undergrad(code: str) -> bool:
    m = re.search(r"(\d+)", code)
    return bool(m and int(m.group(1)) < 500)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    all_entries: list[dict] = []
    for subj in SUBJECTS:
        print(f"Fetching {subj.upper()}...", end=" ", flush=True)
        try:
            raw_list = fetch_subject(subj)
            entries = [build_entry(r) for r in raw_list]
            undergrad = [e for e in entries if is_undergrad(e["code"])]
            all_entries.extend(undergrad)
            print(f"{len(undergrad)} undergrad courses ({len(entries) - len(undergrad)} grad skipped)")
        except Exception as exc:
            print(f"ERROR: {exc}")
        time.sleep(0.3)

    print(f"\nTotal: {len(all_entries)} undergrad courses across {len(SUBJECTS)} subjects")

    if args.dry_run:
        print("\n[DRY RUN] Sample entry:")
        print(json.dumps(all_entries[0], indent=2))
        return

    # Write data/ratings_raw.json
    ratings_path = os.path.join(DATA_DIR, "ratings_raw.json")
    with open(ratings_path, "w") as f:
        json.dump(all_entries, f, indent=2)
    print(f"Wrote {ratings_path} ({len(all_entries)} entries)")

    if args.json_only:
        return

    # Merge ratings into data/course_catalog.json
    planner_path = os.path.join(DATA_DIR, "course_catalog.json")
    try:
        with open(planner_path) as f:
            planner = json.load(f)
    except FileNotFoundError:
        print(f"{planner_path} not found — skipping merge")
        return

    by_code = {e["code"]: e for e in all_entries}
    updated = 0
    for course in planner:
        fresh = by_code.get(course["code"])
        if not fresh:
            continue
        # Update ratings if UWFlow has data
        if "liked" in fresh:
            course["_liked"] = fresh["liked"]
            course["_easy"] = fresh["easy"]
            course["_useful"] = fresh.get("useful")
            course["_ratings"] = fresh["num_ratings"]
            updated += 1
        # Update description if blank
        if not course.get("description") and fresh.get("description"):
            course["description"] = fresh["description"]
        # Store raw prereq/antireq text for reference
        if fresh.get("prereqs"):
            course["_prereq_text"] = fresh["prereqs"]
        if fresh.get("antireqs"):
            course["_antireq_text"] = fresh["antireqs"]

    with open(planner_path, "w") as f:
        json.dump(planner, f, indent=2)
    print(f"Updated {updated} courses in data/course_catalog.json with fresh ratings")
    print("\nDone. Re-run scripts/index_courses.py with --force to re-embed updated descriptions.")


if __name__ == "__main__":
    main()
