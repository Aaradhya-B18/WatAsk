# data/

Static data checked into the repo. Everything here is built by scripts in `../scripts/` — see
that folder's README for how each file gets produced or refreshed. Nothing here is hand-edited
in bulk; small one-off corrections (a wrong prereq, a bad grade threshold) do sometimes get
hand-fixed directly, with the reasoning left in the git commit message.

## Files

- **`course_catalog.json`** (1,600+ entries) — One object per course:
  `code`, `title`, `description`, `requirements` (raw prereq text as written), `subject`,
  `catalogNumber`, `termsOffered`, plus rating fields (`_liked`, `_easy`, `_useful`,
  `_ratings`) and the raw `_prereq_text`/`_antireq_text` that `parse_prereqs.py` consumes.
  Covers 25 subjects: every UW Math-faculty subject plus the cross-listed subjects needed for
  CS specializations (BIOL, CHEM, ECE, GENE, FINE, GSJ), business specializations (AFM, COMM,
  ECON, MATBUS, DATSC, MTHEL, MGMT, HRM), and Wilfrid Laurier's BU-prefix business courses
  (for the double-degree programs — the only non-UWFlow-sourced entries, scraped from
  Laurier's own academic calendar).

- **`prereqs.json`** (~980 entries) — `{ "CS 341": [["CS 240","CS 240E"], ["MATH 239"]] }`.
  AND between the outer groups, OR within a group; `"MATH 138:60"` means MATH 138 with a
  minimum grade of 60%. Parsed from each course's `_prereq_text` by Gemini
  (`scripts/parse_prereqs.py`), then spot-checked against the real UW/Laurier calendar text
  for every program actually modeled in `index.html`'s `PROGRAMS` object — a course existing
  here doesn't guarantee its prereq chain has been manually verified unless it's required by
  a program WatAsk schedules.

- **`ratings_raw.json`** — The unmerged UWFlow scrape output (liked/easy/useful percentages,
  rating/comment counts) that `fetch_ratings.py` folds into `course_catalog.json`. Kept
  separately so a ratings refresh doesn't require re-deriving everything else about a course.
