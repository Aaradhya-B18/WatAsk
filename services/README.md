# services/

The backend brains behind `/ask`, `/plan`, and `/parse-transcript`. No HTTP, just logic.

- **`rag.py`** — Answers questions using real course reviews
- **`planner.py`** — Untangles prereqs into a real schedule
- **`embeddings.py`** — One shared Gemini client, nothing fancy
- **`transcript.py`** — Reads your transcript so you don't have to
