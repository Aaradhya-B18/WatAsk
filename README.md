# WatAsk

[![demo](https://img.shields.io/badge/demo-live-brightgreen)](https://watask.onrender.com) [![python](https://img.shields.io/badge/python-3.12%2B-blue)](runtime.txt) [![fastapi](https://img.shields.io/badge/FastAPI-0.128-009688)](requirements.txt) [![license](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

A full-stack academic planning tool for University of Waterloo students. It combines a RAG-powered AI advisor with an interactive drag-and-drop course scheduler, covering all 18 undergrad Math/CS programs: every BMath major, the BCS program, and the BBA (Laurier) + Waterloo double-degree plans.

**Live at [watask.onrender.com](https://watask.onrender.com)**

---

## Features

- **AI Course Advisor** — ask anything about a course (difficulty, workload, comparisons, prereqs) and get an answer grounded in real UWFlow review text via RAG, not a static FAQ
- **Interactive Course Planner** — drag-and-drop grid for up to 10 study terms (double-degree plans run 5 years). Tracks prerequisites live and won't let you schedule something you're not eligible for yet
- **Smart Plan Generator** — one click builds a full schedule that resolves prereq chains across multiple passes, respects co-op sequencing, and budgets non-math electives per term
- **Grade-Aware Prereqs** — enter your grades and the planner flags when a low one silently blocks a specific downstream course; this is program-specific (e.g. MATH 136 at 56% warns BMath students about MATH 235, but not BCS students, since BCS doesn't require it)
- **Retake Scheduling** — mark a course for retake and it becomes a draggable card you can slot into any future term
- **Transcript Upload** — upload a photo or PDF of an unofficial transcript and Gemini's multimodal API extracts completed courses, terms, and grades into an editable list before anything is added
- **Single/Double Degree Support** — 16 single-degree BMath/BCS programs plus BBA (Laurier) + Math/CS double degrees, using UW's real SEQ 5DD co-op sequence (all 3 official work-term variants)

Programs covered: Statistics, Computer Science (BCS), Applied Math, Pure Math, Combinatorics & Optimization, Actuarial Science, Computational Math, Math/Finance, Math/Physics, Data Science, and the BBA+CS / BBA+Math double degrees, among others.

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
├── server.py                    # FastAPI routes
├── index.html                   # Frontend (single page, vanilla JS)
│
├── services/
│   ├── rag.py                   # /ask pipeline
│   ├── planner.py                # /plan scheduler
│   ├── embeddings.py              # Gemini client
│   └── transcript.py               # /parse-transcript OCR
│
├── data/
│   ├── course_catalog.json      # Full course catalog
│   ├── prereqs.json              # Prerequisite chains
│   └── ratings_raw.json           # UWFlow ratings
│
├── scripts/                     # Data collection/build scripts
│   ├── fetch_extra_subjects.py
│   ├── fetch_wlu_courses.py
│   ├── fetch_ratings.py
│   ├── parse_prereqs.py
│   ├── index_courses.py
│   ├── scrape_uw_programs.py
│   ├── program_requirements.json
│   ├── fetch_uw_courses.py       # unused (needs an API key that's no longer available)
│   ├── clean_planner.py          # unused (paired with fetch_uw_courses.py)
│   ├── build_catalog.py          # unused (predates the current Supabase pipeline)
│   └── load_data.py              # unused (superseded by index_courses.py)
│
├── tests/                       # 37 tests
│   ├── test_planner.py
│   ├── test_api.py
│   └── test_helpers.py
│
├── requirements.txt
├── requirements-dev.txt
└── runtime.txt
```