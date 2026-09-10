# data/

Static data, rebuilt by scripts in `../scripts/`.

- **`course_catalog.json`** — 1,600+ courses across 25 subjects: title, description, ratings, raw prereq text.
- **`prereqs.json`** — ~980 parsed prerequisite chains, keyed by course code. `[[a,b],[c]]` = (a OR b) AND c; `"X:60"` = min grade 60%.
- **`ratings_raw.json`** — Unmerged UWFlow ratings scrape, folded into `course_catalog.json` by `fetch_ratings.py`.
