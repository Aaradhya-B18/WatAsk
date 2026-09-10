# services/

Backend business logic for WatAsk, called from `server.py`'s route handlers. Nothing here
touches HTTP directly — each module takes plain Python values in and returns plain Python
values out, so it can be tested without spinning up FastAPI (see `../tests/`).

## Files

- **`rag.py`** — Powers `POST /ask`. Normalizes the question, extracts any course codes
  mentioned, embeds the query and retrieves the top-4 semantically similar UWFlow reviews via
  Supabase's `match_courses` RPC, then generates an answer with Gemini grounded in that
  retrieved context (plus the student's program/term/taken-courses profile). Wraps every
  external call (embedding, Supabase, generation) in error handling that logs to Sentry and
  falls back to a generic "try again" message rather than leaking a stack trace to the user.

- **`planner.py`** — Powers `POST /plan`. A deterministic, 3-phase greedy scheduler:
  Phase 1 places required courses via multi-pass prerequisite resolution (a course lands at
  its "typical" term or the earliest later term where its prereqs and grade minimums are
  satisfied); Phase 2 spreads an "Advanced" elective pool from 3A onward; Phase 3 fills
  remaining slots with generic Non-Math/Math elective placeholders. Also handles retakes
  (a failed course must be rescheduled after its original attempt, and a retake's old grade
  never counts against a prereq check) and reports *why* a course couldn't be scheduled
  (a specific unmet prereq vs. a plain capacity/packing issue) rather than failing silently.

- **`embeddings.py`** — Thin, shared wrapper around the Gemini client used by both `rag.py`
  (query embeddings) and `scripts/index_courses.py` (bulk course embeddings), so there's one
  place that knows the embedding model name and dimensionality (768, L2-normalized).

- **`transcript.py`** — Powers `POST /parse-transcript`. Sends an uploaded PDF/image straight
  to Gemini (multimodal input, JSON response mode) with a prompt describing UW's unofficial
  transcript format, and returns a cleaned `{code, term, grade}` list per completed course.
  The frontend treats this as a *suggestion* to review and edit, never as ground truth applied
  directly — see the onboarding step 3 review UI in `../index.html`.
