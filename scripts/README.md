# scripts/

Data pipeline. Run from the project root, e.g. `python scripts/fetch_ratings.py`. All are safe to re-run.

**Active**
- **`fetch_extra_subjects.py`** — Pulls a new subject's courses from UWFlow's GraphQL API.
- **`fetch_wlu_courses.py`** — Scrapes Laurier's academic calendar for BU business courses.
- **`fetch_ratings.py`** — Pulls liked/easy/useful % and prereq text into `data/course_catalog.json`.
- **`parse_prereqs.py`** — Gemini parses raw prereq text into structured `data/prereqs.json`.
- **`index_courses.py`** — Embeds each course's review text into Supabase pgvector.
- **`scrape_uw_programs.py`** — One-time pull of official program requirements.
- **`program_requirements.json`** — Snapshot written by the script above.

**Legacy** (superseded, kept for reference)
- **`fetch_uw_courses.py`** — Older UWFlow scraper; needed a `UW_API_KEY` the current one doesn't.
- **`clean_planner.py`** — Cleanup step downstream of `fetch_uw_courses.py`.
- **`build_catalog.py`** — Predates Supabase pgvector entirely.
- **`load_data.py`** — Superseded by `index_courses.py`.
