# services/

Backend logic called by `server.py`. No HTTP here — plain functions in, plain values out.

- **`rag.py`** — Powers `/ask`: embeds the question, retrieves matching UWFlow reviews from Supabase, generates a grounded answer with Gemini.
- **`planner.py`** — Powers `/plan`: the 3-phase greedy scheduler that places required courses, then electives, respecting prereqs and retakes.
- **`embeddings.py`** — Shared Gemini client and embedding helper, used by `rag.py` and `scripts/index_courses.py`.
- **`transcript.py`** — Powers `/parse-transcript`: sends an uploaded transcript to Gemini and returns `{code, term, grade}` rows.
