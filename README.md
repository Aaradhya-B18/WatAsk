# WatAsk — UW Course Planner & Advisor

A full-stack academic planning tool for University of Waterloo students. Combines a RAG-powered AI advisor with an interactive course scheduler covering 18 programs — every BMath major, the BCS program, and the BBA (Laurier) + Waterloo double-degree plans.

**Live:** [watask.onrender.com](https://watask.onrender.com)

---

## Features

- **AI Course Advisor** — Ask anything about UW courses (difficulty, workload, prereqs, comparisons). Powered by Gemini + semantic search over UWFlow reviews.
- **Interactive Course Planner** — Drag-and-drop grid for up to 10 study terms (double-degree plans run 5 years). Tracks prerequisites, detects conflicts, and color-codes course readiness.
- **Smart Plan Generator** — One-click plan generation that respects prereq chains, co-op sequences, and non-math elective budgets.
- **Grade-Aware Prereqs** — Enter your grades; the planner warns if a low grade blocks a downstream course (program-specific — e.g. MATH 136 at 56% warns BMath students about MATH 235 but not BCS students).
- **Retake Scheduling** — Mark a course for retake; it appears as a draggable card you can slot into any future term.
- **Transcript Upload** — Upload a PDF/image of your unofficial transcript and Gemini extracts your completed courses, terms, and grades into an editable review list before anything is added.
- **Single/Double Degree Support** — 16 single-degree BMath/BCS programs plus the BBA (Wilfrid Laurier) + Math or CS double-degree plans, with UW's real SEQ 5DD co-op sequence (all 3 official work-term variants).
- **18 Programs** — Statistics, CS (BCS), Applied Math, Pure Math, CO, Actuarial Science, Computational Math, Math Finance, Math Physics, Data Science, BBA+CS/BBA+Math double degree, and more.

---

## Architecture

```
┌─────────────────────────────────────┐
│           index.html                │  Single-page frontend (vanilla JS)
│  - Course planner grid              │
│  - Prereq sidebar                   │
│  - WatAsk chat UI                   │
└────────────────┬────────────────────┘
                 │ REST (FastAPI)
┌────────────────▼────────────────────┐
│           server.py                 │
│                                     │
│  GET  /prereqs           → prereqs.json     │
│  POST /plan              → greedy scheduler │
│  POST /ask               → RAG pipeline     │
│  GET  /courses           → catalog JSON     │
│  POST /parse-transcript  → transcript OCR   │
└────────┬────────────────┬───────────┘
         │                │
┌────────▼──────┐  ┌──────▼──────────┐
│  Gemini API   │  │    Supabase     │
│               │  │                 │
│ • Embeddings  │  │ • pgvector      │
│   (768-dim)   │  │ • match_courses │
│ • Generation  │  │   RPC (cosine   │
│   (flash-lite)│  │   similarity)   │
│ • Transcript  │  │                 │
│   OCR (multi- │  │                 │
│   modal)      │  │                 │
└───────────────┘  └─────────────────┘
```

### RAG Pipeline (`/ask`)

1. Normalize query → extract course codes
2. Embed query with `gemini-embedding-001` (768-dim, L2-normalized)
3. `match_courses` RPC → top-4 semantically similar UWFlow reviews
4. Exact-match lookup for any course codes mentioned
5. Build prompt with student profile + retrieved context + conversation history
6. Generate with `gemini-3.1-flash-lite` → return answer + source codes

### Plan Generator (`/plan`)

Deterministic greedy scheduler, 3 phases:

- **Phase 1** — Required courses, multi-pass prereq resolution. Each course placed at its typical term or later; retries until prereqs clear.
- **Phase 2** — Advanced/elective pool starting from 3A. Reserves 1 slot/term for non-math budget.
- **Phase 3** — Fills remaining slots with Non-Math Elective / Free Elective labels.

Prereq format in `data/prereqs.json`:
```
[[alt1, alt2], [alt3]]   →  (alt1 OR alt2) AND (alt3)
"MATH 136:60"            →  MATH 136 with minimum 60%
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Vanilla JS, HTML/CSS (no framework) |
| Backend | Python, FastAPI, Uvicorn/Gunicorn |
| AI | Google Gemini (embeddings + generation) |
| Vector DB | Supabase pgvector |
| Hosting | Render |

---

## Local Setup

### Prerequisites
- Python 3.12+
- A Gemini API key ([aistudio.google.com](https://aistudio.google.com))
- A Supabase project with the `courses` table and `match_courses` RPC

### Steps

```bash
git clone https://github.com/Aaradhya-B18/WatAsk.git
cd WatAsk
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file:
```
GEMINI_API_KEY=your_key_here
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_anon_key_here
```

Run the server:
```bash
uvicorn server:app --reload
```

Open [http://localhost:8000](http://localhost:8000).

### Supabase Schema

```sql
create table courses (
  id   bigint primary key generated always as identity,
  code text not null,
  text text not null,
  embedding vector(768)
);

create or replace function match_courses(query_embedding vector(768), match_count int)
returns table(code text, text text, similarity float)
language sql stable as $$
  select code, text, 1 - (embedding <=> query_embedding) as similarity
  from courses
  order by embedding <=> query_embedding
  limit match_count;
$$;
```

---

## Data

- `data/course_catalog.json` — 1,600+ courses across 25 subjects. Most are scraped from UWFlow's GraphQL API (no auth needed); the BU-prefix Laurier business courses (for the double-degree plans) are scraped directly from Laurier's own academic calendar, since UWFlow only covers Waterloo.
- `data/prereqs.json` — ~980 courses with prerequisite chains, parsed from each course's raw requirement text via Gemini (`scripts/parse_prereqs.py`). Format: `[[alt1, alt2], [alt3]]` = (alt1 OR alt2) AND (alt3); `"MATH 136:60"` = MATH 136 with minimum 60%.
- `data/ratings_raw.json` — Liked%/easy%/useful% ratings per course, scraped separately from UWFlow.
- Supabase `courses` table — Full UWFlow review text + Gemini embeddings, used only for RAG retrieval in `/ask`.

---

## Project Structure

```
WatAsk/
├── server.py                    # Thin router, delegates all the real thinking
├── index.html                    # The whole app, one big honest file
│
├── services/                    # Where the actual brains live — see services/README.md
│   ├── rag.py                    # Answers questions using real course reviews
│   ├── planner.py                 # Untangles prereqs into a real schedule
│   ├── embeddings.py               # One shared Gemini client, nothing fancy
│   └── transcript.py               # Reads your transcript so you don't have to
│
├── data/                        # The receipts — see data/README.md
│   ├── course_catalog.json        # Every course we could get our hands on
│   ├── prereqs.json                # The rulebook: what unlocks what
│   └── ratings_raw.json             # Raw UWFlow opinions, pre-merge
│
├── scripts/                     # The scrapers that feed data/ — see scripts/README.md
│   ├── fetch_extra_subjects.py     # Adds a new subject on demand
│   ├── fetch_wlu_courses.py         # Sneaks into Laurier's course catalog
│   ├── fetch_ratings.py              # Steals opinions from UWFlow
│   ├── parse_prereqs.py               # Gemini untangles prereq legalese
│   ├── index_courses.py                # Feeds Supabase for the RAG search
│   ├── scrape_uw_programs.py            # One-shot pull of official requirements
│   ├── program_requirements.json         # What the script above left behind
│   ├── fetch_uw_courses.py                # Retired, needed a key nobody has
│   ├── clean_planner.py                    # Retired sidekick to the script above
│   ├── build_catalog.py                     # Fossil from before Supabase existed
│   └── load_data.py                          # Retired, index_courses.py does it better
│
├── tests/                       # 37 tests keeping this honest — see tests/README.md
│   ├── test_planner.py            # Makes sure the scheduler doesn't lie
│   ├── test_api.py                 # Pokes the API, checks it behaves
│   └── test_helpers.py              # Boring fixtures, doing quiet work
│
├── requirements.txt              # What it takes to run this thing
├── requirements-dev.txt           # + pytest, for keeping it honest
└── runtime.txt                    # Tells Render which Python to use
```