"""
Scrape Wilfrid Laurier University's Business (BU) course catalog for the
BBA + Waterloo double-degree programs.

Laurier isn't covered by UWFlow (a Waterloo-only tool), so this hits
Laurier's own academic calendar directly instead of the usual UWFlow
GraphQL pipeline used for every other subject in this project.

Appends new entries to data/course_catalog.json in the same shape as
every other scraped subject (code, title, description, requirements,
subject, catalogNumber, termsOffered, _prereq_text, _antireq_text) so
the existing scripts/parse_prereqs.py and scripts/index_courses.py
pipelines pick them up automatically - no separate parsing logic needed.

Run from project root:
  python scripts/fetch_wlu_courses.py
"""
from __future__ import annotations

import os
import re
import json
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_PATH = os.path.join(ROOT, "data", "course_catalog.json")

BASE = "https://academic-calendar.wlu.ca/"
DEPT_URL = BASE + "department.php?cal=1&d=3155&s=1154&y=92"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; WatAskCourseBot/1.0)"}


def strip_html(s: str) -> str:
    # Drop glossary popup script blobs (onMouseOver="...") before stripping tags
    s = re.sub(r'onMouseOver="[^"]*"', "", s)
    s = re.sub(r'onMouseOut="[^"]*"', "", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = s.replace("&amp;", "&").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", s).strip()


def normalize_code(raw: str) -> str:
    m = re.match(r"([A-Za-z]+)\s*(\d+[A-Za-z]?)", raw.strip())
    return f"{m.group(1).upper()} {m.group(2).upper()}" if m else raw.strip()


def fetch_course_list() -> list[tuple[str, str]]:
    """Returns [(course_id, code), ...] for every BU course on the department page."""
    html = requests.get(DEPT_URL, headers=HEADERS, timeout=20).text
    pairs = re.findall(r'course\.php\?c=(\d+)[^"]*">\s*(BU\d+[A-Za-z]?)\s*<', html)
    seen = set()
    out = []
    for cid, code in pairs:
        if cid not in seen:
            seen.add(cid)
            out.append((cid, code))
    return out


def fetch_course_detail(course_id: str) -> dict | None:
    url = f"{BASE}course.php?c={course_id}&cal=1&d=3155&s=1154&y=92"
    html = requests.get(url, headers=HEADERS, timeout=20).text

    # The page has a "Contact Us:" h1 in the sidebar too - anchor to the one
    # that actually starts with a course code
    h1 = re.search(r"<h1>(BU\d+[A-Za-z]?<br/>.*?)</h1>", html, re.S)
    if not h1:
        return None
    h1_parts = [strip_html(p) for p in h1.group(1).split("<br/>")]
    code_raw = h1_parts[0] if h1_parts else ""
    title = h1_parts[1] if len(h1_parts) > 1 else ""
    if not code_raw or not title:
        return None

    # Description: the free-text block between the "hours" div and the "reqs" div
    desc_match = re.search(r'class="hours">.*?</div>(.*?)<div class="reqs">', html, re.S)
    description = strip_html(desc_match.group(1)) if desc_match else ""

    # Requirement dt/dd pairs inside the "reqs" block (Prerequisites, Corequisites, Exclusions, etc.)
    reqs_match = re.search(r'<div class="reqs">(.*?)<div class="clear">', html, re.S)
    prereq_text, coreq_text, antireq_text = "", "", ""
    if reqs_match:
        reqs_html = reqs_match.group(1)
        for dt_html, dd_html in re.findall(r"<dt>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>", reqs_html, re.S):
            label = strip_html(dt_html).lower()
            value = strip_html(dd_html)
            if not value:
                continue
            value = value.strip(" .")
            if "prerequisite" in label:
                prereq_text = value
            elif "corequisite" in label:
                coreq_text = value
            elif "exclusion" in label or "antirequisite" in label:
                antireq_text = value

    full_prereq_text = "; ".join(t for t in [prereq_text, coreq_text and f"Coreq: {coreq_text}"] if t)

    return {
        "code": normalize_code(code_raw),
        "title": title,
        "description": description,
        "requirements": full_prereq_text or None,
        "subject": "BU",
        "catalogNumber": normalize_code(code_raw).split()[-1],
        "termsOffered": [],
        "_source": "wlu-academic-calendar",
        "_prereq_text": full_prereq_text or None,
        "_antireq_text": antireq_text or None,
    }


def main():
    with open(CATALOG_PATH) as f:
        catalog = json.load(f)
    existing_codes = {c["code"] for c in catalog}

    course_list = fetch_course_list()
    print(f"Found {len(course_list)} BU courses on the WLU calendar")

    added = 0
    for cid, code_raw in course_list:
        code = normalize_code(code_raw)
        if code in existing_codes:
            continue
        try:
            entry = fetch_course_detail(cid)
        except Exception as e:
            print(f"  {code}: ERROR {e}")
            continue
        if not entry:
            print(f"  {code}: could not parse detail page")
            continue
        catalog.append(entry)
        existing_codes.add(code)
        added += 1
        print(f"  + {entry['code']}: {entry['title']}")
        time.sleep(0.3)

    with open(CATALOG_PATH, "w") as f:
        json.dump(catalog, f, indent=2)
    print(f"\nAdded {added} new BU courses. Catalog now has {len(catalog)} total.")
    print("Next: python scripts/parse_prereqs.py   (to parse the new _prereq_text fields)")


if __name__ == "__main__":
    main()
