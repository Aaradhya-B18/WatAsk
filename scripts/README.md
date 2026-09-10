# scripts/

Data pipeline scripts for building `data/course_catalog.json` and `data/prereqs.json`, and for
embedding courses into Supabase. All are safe to re-run (incremental — they skip work that's
already done) unless noted otherwise. Run from the project root, e.g. `python scripts/fetch_ratings.py`.

## Active pipeline

This is the pipeline actually in use today, in the order you'd run it for a new subject:

1. **`fetch_extra_subjects.py`** — Fetches a new subject's courses from UWFlow's GraphQL API
   (`uwflow.com/graphql`, no key required). This is the primary course-discovery script now —
   every subject added this project (PHYS, AFM, COMM, ECON, MATBUS, DATSC, BIOL, CHEM, ECE,
   GENE, FINE, GSJ, MTHEL, MGMT, HRM, and more) went through this or `fetch_ratings.py` below.
2. **`fetch_wlu_courses.py`** — The one exception: Wilfrid Laurier isn't covered by UWFlow (a
   Waterloo-only tool), so this scrapes Laurier's own academic calendar directly for the
   BU-prefix business courses used by the double-degree programs.
3. **`fetch_ratings.py`** — Pulls liked%/easy%/useful% ratings, descriptions, and raw
   prerequisite text from UWFlow for a list of subjects, merging the results straight into
   `data/course_catalog.json` and `data/ratings_raw.json`. Update the `SUBJECTS` list here
   when a new subject needs its ratings refreshed.
4. **`parse_prereqs.py`** — Sends every course's raw `_prereq_text` to Gemini in batches,
   converting natural-language prerequisite text into the structured AND-of-OR format used by
   `services/planner.py`, writing `data/prereqs.json`. Skips courses already parsed unless
   run with `--force`.
5. **`index_courses.py`** — Embeds each course's review text into Supabase pgvector (for
   `/ask`'s RAG retrieval). Skips courses that already have an embedding, so a partial run
   (e.g. hitting Gemini's free-tier rate limit mid-batch) is safe to just re-run later.

## Other files

- **`scrape_uw_programs.py`** — One-time scrape of official program requirements from UW's
  Academic Calendar Kuali API. Output snapshot: `program_requirements.json`.
- **`program_requirements.json`** — Static snapshot written by the script above.

## Legacy (superseded, kept for reference)

These predate the UWFlow-based pipeline above and aren't part of the current data flow —
`fetch_uw_courses.py` in particular needs a `UW_API_KEY` that the active pipeline doesn't:

- **`fetch_uw_courses.py`** — Fetched MATH/CS/STAT courses from UW's official Open Data API
  (requires an API key) into a root-level `waterloo_data.json`. Superseded by
  `fetch_extra_subjects.py`'s no-key UWFlow approach.
- **`clean_planner.py`** — Deduplicated `waterloo_data.json` into `planner_courses.json`.
  Downstream of the script above, so equally superseded.
- **`build_catalog.py`** — Converted an even earlier `uwflow_ratings.json` into text blobs for
  a root-level `data_generated.py` module. Predates Supabase pgvector entirely.
- **`load_data.py`** — Embedded courses from a top-level `data.py` module (via `from data
  import courses`) directly into Supabase. Superseded by `index_courses.py`, which reads from
  `data/course_catalog.json` instead of a hardcoded Python module.
