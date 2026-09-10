"""
Fetch courses for additional subjects from UWFlow GraphQL API.
No API key required. Merges results into planner_courses.json.

Subjects fetched:
  PMATH  - Pure Mathematics
  ACTSC  - Actuarial Science
  AMATH  - Applied Mathematics
  CO     - Combinatorics & Optimization

Run from the project root:
  python scripts/fetch_extra_subjects.py
"""
import os
import re
import json
import time
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

UWFLOW_GQL = "https://uwflow.com/graphql"
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) AppleWebKit/537.36",
}

QUERY = """
query getCoursesBySubject($prefix: String) {
  course(
    where: {code: {_like: $prefix}}
    order_by: {code: asc}
    limit: 300
  ) {
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
    }
  }
}
"""

SUBJECTS = ["pmath", "actsc", "amath", "co"]
# Exact subject codes we actually want (guards against prefix collisions like co→comm)
EXACT_SUBJECTS = {"PMATH", "ACTSC", "AMATH", "CO"}


def uwflow_to_uw_code(code: str) -> str:
    """Convert 'pmath340' → 'PMATH 340'"""
    m = re.match(r"^([a-z]+)(\d+[a-z]*)$", code.lower())
    if not m:
        return None
    subj, num = m.group(1).upper(), m.group(2).upper()
    # Skip transfer credit placeholders like PMATH2XX
    if re.search(r"X", num, re.I):
        return None
    return f"{subj} {num}"


def fetch_subject(prefix: str) -> list:
    resp = requests.post(
        UWFLOW_GQL,
        headers=HEADERS,
        json={"query": QUERY, "variables": {"prefix": f"{prefix}%"}},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("data", {}).get("course", [])


def main():
    planner_path = os.path.join(ROOT, "planner_courses.json")
    with open(planner_path) as f:
        existing = json.load(f)

    existing_codes = {c["code"] for c in existing}
    print(f"Existing courses: {len(existing)}")

    new_courses = []

    for subj in SUBJECTS:
        print(f"\nFetching {subj.upper()}...", flush=True)
        try:
            courses = fetch_subject(subj)
        except Exception as e:
            print(f"  ERROR: {e}")
            time.sleep(2)
            continue

        added = 0
        for c in courses:
            uw_code = uwflow_to_uw_code(c["code"])
            if not uw_code:
                continue
            if uw_code.split()[0] not in EXACT_SUBJECTS:
                continue  # prefix collision (e.g. co% → COMM)
            if uw_code in existing_codes:
                continue  # already in DB

            # Build requirements string in the same format as UW API data
            req_parts = []
            if c.get("prereqs"):
                req_parts.append(f"Prereq: {c['prereqs']}")
            if c.get("antireqs"):
                req_parts.append(f"Antireq: {c['antireqs']}")

            subject_part, num_part = uw_code.split(" ", 1)

            new_courses.append({
                "code": uw_code,
                "title": c.get("name") or uw_code,
                "description": c.get("description") or "",
                "requirements": ". ".join(req_parts),
                "subject": subject_part,
                "catalogNumber": num_part,
                "termsOffered": [],
                "_source": "uwflow",
                "_liked": c["rating"].get("liked") if c.get("rating") else None,
                "_easy": c["rating"].get("easy") if c.get("rating") else None,
                "_ratings": c["rating"].get("filled_count", 0) if c.get("rating") else 0,
            })
            existing_codes.add(uw_code)
            added += 1

        print(f"  {subj.upper()}: {added} new courses added")
        time.sleep(0.5)

    merged = sorted(existing + new_courses, key=lambda x: x["code"])
    with open(planner_path, "w") as f:
        json.dump(merged, f, indent=2)

    print(f"\nDone. Total courses: {len(merged)} (+{len(new_courses)} new)")

    # Print subject breakdown
    by_subj = {}
    for c in merged:
        s = c["code"].split()[0]
        by_subj[s] = by_subj.get(s, 0) + 1
    for s, n in sorted(by_subj.items()):
        print(f"  {s}: {n}")


if __name__ == "__main__":
    main()
