"""
Parse UWFlow prerequisite text into structured JSON using Gemini.

For each course in data/course_catalog.json that has _prereq_text,
calls Gemini to convert the raw text into the format:
  { "CS 341": [["CS 240","CS 240E"], ["CS 245","CS 245E"], ["MATH 239","MATH 249"]] }

Where:
  - AND logic between groups (all groups must be satisfied)
  - OR logic within a group (at least one course in the group suffices)
  - Grade minimums as ":N" suffix (e.g. "MATH 138:60")

Output: data/prereqs.json

Run from project root:
  python scripts/parse_prereqs.py

Flags:
  --dry-run   Parse first 10 courses and print without saving
  --force     Re-parse all courses (default: skip courses already in prereqs.json)
"""
import os
import re
import sys
import json
import time
import argparse

from dotenv import load_dotenv
load_dotenv()

from google import genai

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_PATH = os.path.join(ROOT, "data", "course_catalog.json")
OUTPUT_PATH  = os.path.join(ROOT, "data", "prereqs.json")

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

BATCH_PROMPT = """\
You parse University of Waterloo course prerequisites into structured JSON.

Rules:
- For each course, output ONLY a JSON array of arrays
- Each inner array = alternatives (OR within group, AND between groups)
- Normalize codes: add space between letters and digits (CS135→"CS 135", AMATH231→"AMATH 231")
- Grade minimums: append ":N" (MATH138 with at least 60% → "MATH 138:60")
- Ignore: program restrictions, average requirements, high school courses
- If no university-course prereqs: use []
- "CS246/CS246E" or "CS246 or CS246E" → same group

Examples:
"One of CS136, CS146; MATH135 with at least 60%" → [["CS 136","CS 146"],["MATH 135:60"]]
"MATH237 or MATH247" → [["MATH 237","MATH 247"]]
"CS240; One of CS245,CS245E; MATH239 or MATH249" → [["CS 240"],["CS 245","CS 245E"],["MATH 239","MATH 249"]]
"(AMATH242/CS371 or CS370) and (One of AMATH250,AMATH251)" → [["AMATH 242","CS 371","CS 370"],["AMATH 250","AMATH 251"]]
"Honours Mathematics students only" → []
"4U Calculus and Vectors" → []

Now parse ALL of the following courses. Output a single JSON object mapping each course code to its parsed prereqs:

{batch_input}

Output only the JSON object, no explanation:"""


def parse_batch(batch: list) -> dict:
    """Parse a list of {code, prereq_text} dicts in one API call."""
    batch_input = "\n".join(
        f'{item["code"]}: "{item["prereq_text"]}"' for item in batch
    )
    prompt = BATCH_PROMPT.format(batch_input=batch_input)
    for attempt in range(4):
        try:
            r = client.models.generate_content(
                model="gemini-3.1-flash-lite",
                contents=prompt,
            )
            raw = r.text.strip().replace("```json", "").replace("```", "").strip()
            result = json.loads(raw)
            if isinstance(result, dict):
                return result
            return {}
        except Exception as e:
            msg = str(e)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                wait = 20 * (attempt + 1)
                print(f"\n  rate limited — waiting {wait}s...", end=" ", flush=True)
                time.sleep(wait)
            else:
                print(f"\n  ERROR: {e}")
                return {}
    return {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force",   action="store_true", help="Re-parse even if already in output")
    args = parser.parse_args()

    with open(CATALOG_PATH) as f:
        catalog = json.load(f)

    # Load existing output so we can skip already-parsed courses
    existing: dict = {}
    if not args.force and os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH) as f:
            existing = json.load(f)
        print(f"Loaded {len(existing)} existing parsed prereqs (use --force to re-parse all)")

    to_parse = [c for c in catalog if c.get("_prereq_text") and (args.force or c["code"] not in existing)]
    print(f"Courses with prereq text in catalog : {sum(1 for c in catalog if c.get('_prereq_text'))}")
    print(f"Need to parse                        : {len(to_parse)}")

    if args.dry_run:
        to_parse = to_parse[:10]
        print(f"[DRY RUN] Parsing first {len(to_parse)} courses\n")

    results: dict = dict(existing)
    BATCH_SIZE = 10
    batches = [to_parse[i:i+BATCH_SIZE] for i in range(0, len(to_parse), BATCH_SIZE)]
    total_added = 0

    for b_idx, batch in enumerate(batches, 1):
        codes = [c["code"] for c in batch]
        print(f"Batch {b_idx}/{len(batches)}: {', '.join(codes)} ...", flush=True)

        items = [{"code": c["code"], "prereq_text": c["_prereq_text"]} for c in batch]
        parsed = parse_batch(items)

        for code, prereq_list in parsed.items():
            # Normalise key format (Gemini may return "CS135" instead of "CS 135")
            m = re.match(r"([A-Za-z]+)\s*(\d+[A-Za-z]?)", code.strip())
            norm = f"{m.group(1).upper()} {m.group(2).upper()}" if m else code.upper()
            if prereq_list:
                results[norm] = prereq_list
                total_added += 1
                print(f"  ✓ {norm}: {prereq_list}")
            else:
                print(f"  - {norm}: (no university prereqs)")

        # Save after every batch so partial results aren't lost
        if not args.dry_run:
            sorted_results = dict(sorted(results.items()))
            with open(OUTPUT_PATH, "w") as f:
                json.dump(sorted_results, f, indent=2)

        time.sleep(5)    # 15 req/min free tier — 1 batch per 5s is safe

    print(f"\nDone. Added/updated: {total_added}  Total with prereqs: {len(results)}")

    if args.dry_run:
        print("\n[DRY RUN] Sample output (not saved):")
        sample = {k: results[k] for k in list(results.keys())[:5]}
        print(json.dumps(sample, indent=2))


if __name__ == "__main__":
    main()
