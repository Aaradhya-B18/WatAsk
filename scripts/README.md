# scripts/

The scrapers and pipelines that feed `data/`. All safe to re-run.

**Active**
- **`fetch_extra_subjects.py`** — Adds a new subject on demand
- **`fetch_wlu_courses.py`** — Sneaks into Laurier's course catalog
- **`fetch_ratings.py`** — Steals opinions from UWFlow
- **`parse_prereqs.py`** — Gemini untangles prereq legalese
- **`index_courses.py`** — Feeds Supabase for the RAG search
- **`scrape_uw_programs.py`** — One-shot pull of official requirements
- **`program_requirements.json`** — What the script above left behind

**Retired**
- **`fetch_uw_courses.py`** — Needed an API key nobody has
- **`clean_planner.py`** — Sidekick to the script above
- **`build_catalog.py`** — Fossil from before Supabase existed
- **`load_data.py`** — index_courses.py does it better now
