"""
Pull UWFlow ratings for all courses in planner_courses.json.
Writes uwflow_ratings.json to the project root.
Run after clean_planner.py.
"""
import os
import json
import time
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

UWFLOW_GQL = "https://uwflow.com/graphql"
QUERY = """
query getCourse($code: String) {
  course(where: {code: {_eq: $code}}) {
    code name description prereqs antireqs
    rating { liked easy useful filled_count comment_count }
  }
}
"""
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) AppleWebKit/537.36",
}


def to_uwflow_code(code):
    return code.replace(" ", "").lower()


def fetch_course(code, retries=3):
    for attempt in range(retries):
        try:
            resp = requests.post(
                UWFLOW_GQL,
                headers=HEADERS,
                json={"query": QUERY, "variables": {"code": code}},
                timeout=20,
            )
            resp.raise_for_status()
            courses = resp.json().get("data", {}).get("course", [])
            return courses[0] if courses else None
        except Exception:
            if attempt < retries - 1:
                time.sleep(2)
                continue
            raise
    return None


def main():
    with open(os.path.join(ROOT, "planner_courses.json")) as f:
        all_codes = [c["code"] for c in json.load(f)]

    print(f"Attempting {len(all_codes)} courses...\n")

    results, misses, errors = [], 0, 0
    for original_code in all_codes:
        try:
            c = fetch_course(to_uwflow_code(original_code))
            if c and c.get("rating") and c["rating"].get("filled_count"):
                r = c["rating"]
                results.append({
                    "code": original_code,
                    "name": c.get("name"),
                    "description": c.get("description"),
                    "prereqs": c.get("prereqs"),
                    "antireqs": c.get("antireqs"),
                    "liked": r.get("liked"),
                    "easy": r.get("easy"),
                    "useful": r.get("useful"),
                    "num_ratings": r.get("filled_count"),
                    "num_comments": r.get("comment_count"),
                })
                print(f"OK   {original_code}: n={r.get('filled_count')}")
            else:
                misses += 1
        except Exception as e:
            errors += 1
            print(f"ERR  {original_code}: {e}")
        time.sleep(0.8)

    out = os.path.join(ROOT, "uwflow_ratings.json")
    with open(out, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n--- DONE ---")
    print(f"Saved: {len(results)} | Skipped (no ratings): {misses} | Errors: {errors}")
    print(f"Output: {out}")


if __name__ == "__main__":
    main()
