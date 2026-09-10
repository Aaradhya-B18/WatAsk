"""
Scrape program requirements from the UW Academic Calendar Kuali API.
No auth required — uses the same public endpoint the SPA calls.

Outputs: scripts/program_requirements.json

Run from project root:
  python scripts/scrape_uw_programs.py
"""
import asyncio
import json
import re
import os
import time
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CATALOG_ID = "67e557ed6ed2fe2bd3a38956"
BASE = "https://uwaterloocm.kuali.co/api/v1/catalog"
HEADERS = {
    "Referer": "https://uwaterloocm.kuali.co/catalog/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}

# Programs we want — pid → slug key
TARGET_PROGRAMS = {
    # Math majors (Honours)
    "HkeH1JRCjh": "actuarial-science",
    "r1lByy00sh":  "applied-math",
    "ByBkJCRs2":   "applied-math-sci-comp",
    "SkUkJR0oh":   "biostatistics",
    "SyeD110Co2":  "combinatorics-opt",
    "rkDkJCAj2":   "comp-math",
    "HymD11R0j3":  "data-science-bmath",
    "ryAkJARjn":   "math-finance",
    "ByzRyy0Rih":  "math-physics-bmath",
    "H1z0kJR0in":  "math-studies",
    "S1eexkCAo2":  "pure-math",
    "H1XegyCAin":  "statistics",
    "Byl0k1ACin":  "math-teaching",
    "r1gAJJ0Cin":  "math-economics-bmath",
    # Math minors
    "rkGHJk0Ci2":  "applied-math-minor",
    "H1D1JR0s2":   "co-minor",
    "SkZPkyCAjh":  "comp-math-minor",
    "SyPykARoh":   "cs-minor",
    "S1eexkCAo2":  "pure-math-minor",   # same as major
    "rJbgx1RAs3":  "stats-minor",
    # CS programs
    "SJPJkCAih":   "cs-bcs",
    "HkxPJk0Cj3":  "cs-bmath",
    "rkgPyyC0o2":  "data-science-bcs",
    "H1z0kJR0in":  "math-studies",
    # SE
    "H1zle10Cs3":  "software-engineering",
}

MATH_SUBJECTS = {"CS", "MATH", "STAT", "PMATH", "ACTSC", "AMATH", "CO", "MATBUS"}

try:
    from html.parser import HTMLParser
except ImportError:
    pass


def strip_html(html: str) -> str:
    """Remove HTML tags, collapse whitespace."""
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html)).strip()


def parse_course_requirements(html: str) -> dict:
    """
    Parse courseRequirementsNoUnits HTML into structured groups.
    Returns:
      {
        "required": ["STAT 330", ...],          # must complete ALL
        "one_of": [["AMATH 231", ...], ...],    # complete N of each group
        "n_of": [{"n": 2, "courses": [...]}],   # complete exactly N
      }
    """
    required = []
    one_of = []
    n_of = []

    # Find all ruleView blocks
    rule_blocks = re.findall(
        r'<li data-test="ruleView-[^"]*">(.*?)</li>(?=\s*<li data-test|$)',
        html, re.DOTALL
    )

    for block in rule_blocks:
        text = strip_html(block)

        # Extract all course codes in this block
        codes = []
        for raw in re.findall(r'>[A-Z]{2,6}\d{3}[A-Z]?<', block):
            raw = raw.strip('><')
            m = re.match(r'^([A-Z]{2,6})(\d{3}[A-Z]?)$', raw)
            if m and m.group(1) in MATH_SUBJECTS:
                codes.append(f"{m.group(1)} {m.group(2)}")
        codes = list(dict.fromkeys(codes))

        if not codes:
            continue

        # "Complete all the following" → required
        if re.search(r'complete all', text, re.I):
            required.extend(codes)
        # "Complete N of the following"
        elif m2 := re.search(r'complete\s+(\d+)\s+of', text, re.I):
            n = int(m2.group(1))
            if n == 1:
                one_of.append(codes)
            else:
                n_of.append({"n": n, "courses": codes})
        else:
            # Default: treat as required
            required.extend(codes)

    return {
        "required": list(dict.fromkeys(required)),
        "one_of": one_of,
        "n_of": n_of,
    }


def parse_grad_requirements(html: str) -> dict:
    """Extract unit totals from graduationRequirements HTML."""
    text = strip_html(html)
    result = {}
    for m in re.finditer(r'minimum of ([\d.]+) units? of ([^.]+)', text, re.I):
        value = float(m.group(1))
        label = m.group(2).strip().lower()
        result[label] = value
    # Also grab total units if present
    for m in re.finditer(r'([\d.]+) units? total', text, re.I):
        result["total"] = float(m.group(1))
    return result


def extract_min_averages(html: str) -> list:
    """Extract minimum average requirements as plain strings."""
    text = strip_html(html)
    return [s.strip() for s in text.split(';') if 'average' in s.lower() or '%' in s]


def fetch_program(pid: str) -> dict:
    """Fetch full program data from Kuali (singular /program/ endpoint)."""
    url = f"{BASE}/program/{CATALOG_ID}/{pid}"
    r = requests.get(url, headers=HEADERS, timeout=30)
    if r.status_code == 200:
        return r.json()
    return {}


def main():
    results = {}

    for pid, slug in TARGET_PROGRAMS.items():
        print(f"Fetching {slug} ({pid})...", end=" ", flush=True)
        try:
            data = fetch_program(pid)
            if not data:
                print("NOT FOUND")
                continue

            name = data.get("title") or data.get("code") or slug

            # Parse course requirements
            req_html = data.get("courseRequirementsNoUnits") or ""
            course_reqs = parse_course_requirements(req_html)

            # Parse graduation unit requirements
            grad_html = data.get("graduationRequirements") or ""
            units = parse_grad_requirements(grad_html)

            # Minimum averages
            avg_html = data.get("minimumAverageSRequired") or ""
            min_avgs = extract_min_averages(avg_html)

            # Systems of study
            systems = data.get("systemsOfStudy") or {}

            results[slug] = {
                "pid": pid,
                "name": name,
                "coop": systems.get("coOperative", False),
                "regular": systems.get("regular", False),
                "required_courses": course_reqs["required"],
                "one_of_groups": course_reqs["one_of"],
                "n_of_groups": course_reqs["n_of"],
                "units": units,
                "min_averages": min_avgs,
                "declaration": strip_html(data.get("declarationRequirements") or ""),
            }
            total = len(course_reqs["required"]) + sum(len(g) for g in course_reqs["one_of"])
            print(f"→ {len(course_reqs['required'])} required, {len(course_reqs['one_of'])} option groups | units: {units}")
        except Exception as e:
            print(f"ERROR: {e}")
        time.sleep(0.3)

    out = os.path.join(ROOT, "scripts", "program_requirements.json")
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved {len(results)} programs to {out}")


if __name__ == "__main__":
    main()
