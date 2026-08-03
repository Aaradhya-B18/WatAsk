# WatAsk — UW Course Planner & Advisor

A full-stack academic planning tool for University of Waterloo students. Combines a RAG-powered AI advisor with an interactive course scheduler covering all 16 BMath majors and the BCS program.

**Live:** [watask.onrender.com](https://watask.onrender.com)

---

## Features

- **AI Course Advisor** — Ask anything about UW courses (difficulty, workload, prereqs, comparisons). Powered by Gemini + semantic search over UWFlow reviews.
- **Interactive Course Planner** — Drag-and-drop grid for all 8 study terms. Tracks prerequisites, detects conflicts, and color-codes course readiness.
- **Smart Plan Generator** — One-click plan generation that respects prereq chains, co-op sequences, and non-math elective budgets.
- **Grade-Aware Prereqs** — Enter your grades; the planner warns if a low grade blocks a downstream course (program-specific — e.g. MATH 136 at 56% warns BMath students about MATH 235 but not BCS students).
- **Retake Scheduling** — Mark a course for retake; it appears as a draggable card you can slot into any future term.
- **17 Programs** — Statistics, CS (BCS), Applied Math, Pure Math, CO, Actuarial Science, Computational Math, Math Finance, Math Physics, Data Science, SE, and more.

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
│  GET  /prereqs   → prereqs.json     │
│  POST /plan      → greedy scheduler │
│  POST /ask       → RAG pipeline     │
│  GET  /courses   → catalog JSON     │
└────────┬────────────────┬───────────┘
         │                │
┌────────▼──────┐  ┌──────▼──────────┐
│  Gemini API   │  │    Supabase     │
│               │  │                 │
│ • Embeddings  │  │ • pgvector      │
│   (768-dim)   │  │ • match_courses │
│ • Generation  │  │   RPC (cosine   │
│   (flash-lite)│  │   similarity)   │
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

- `data/prereqs.json` — 280+ UW courses with parsed prerequisite chains (scraped from UWFlow)
- `data/course_catalog.json` — Course names, liked%, easy% ratings from UWFlow
- Supabase `courses` table — Full UWFlow review text + Gemini embeddings for RAG

---

## Project Structure

```
WatAsk/
├── server.py          # FastAPI backend (RAG + plan scheduler)
├── index.html         # Full frontend SPA
├── requirements.txt
├── runtime.txt        # Python 3.12 for Render
├── data/
│   ├── prereqs.json       # Prereq chains for 280+ courses
│   └── course_catalog.json
└── scripts/           # Data scraping utilities
```
