import os
import re
from typing import List, Optional
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from google import genai
from supabase import create_client
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import json


load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

# Load prereqs once at startup — 280 courses, all parsed from UWFlow
with open("data/prereqs.json") as f:
    PREREQS: dict = json.load(f)


def embed(text: str):
    r = client.models.embed_content(
        model="gemini-embedding-001",
        contents=text,
        config={"output_dimensionality": 768},
    )
    values = list(r.embeddings[0].values)
    norm = sum(v * v for v in values) ** 0.5
    return [v / norm for v in values]


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request body: the new question plus the conversation so far.
class Turn(BaseModel):
    question: str
    answer: str


class AskRequest(BaseModel):
    question: str
    history: Optional[List[Turn]] = None
    student_context: Optional[str] = None

class PlanRequest(BaseModel):
    program: str
    terms: List[str]
    taken: List[str]
    groups: List[dict]          # [{name, courses, typical}]
    placed: Optional[dict] = None  # {termId: [codes]} already in the grid
    current_term: Optional[str] = None


GREETING_TRIGGERS = [
    "hi", "hello", "hey", "yo", "help",
    "what can you do", "what can i ask", "who are you", "what is this",
    "what are you", "what do you do", "what subjects", "what courses",
    "im a uw student", "i am a uw student", "im a student", "i am a student",
]

# Words that signal a real course question even when no code is typed.
COURSE_WORDS = re.compile(
    r'\b(course|courses|class|classes|hard|easy|harder|easier|difficult|difficulty|'
    r'take|taking|took|prereq|prerequisite|prof|professor|exam|exams|midterm|final|'
    r'assignment|workload|enroll|stream|advanced|enriched|recommend|worth|'
    r'plan|schedule|sequence|next|skip|avoid|instead|option|alternative|'
    r'math|cs|stat|stats|calc|calculus|algebra|combinatorics|probability|logic|'
    r'linear|compiler|proof|proofs|generate|suggest|advice)\b',
    re.IGNORECASE
)


def is_greeting(q: str) -> bool:
    ql = q.lower().strip("?!. ")
    return any(ql == t or ql.startswith(t + " ") for t in GREETING_TRIGGERS)


def normalize_query(q: str) -> str:
    q = q.replace("-", " ")
    q = re.sub(r'([A-Za-z]+)\s*(\d+)', r'\1 \2', q)
    q = re.sub(r'\s+', ' ', q)
    return q.strip()


def find_codes(q: str):
    matches = re.findall(r'([A-Za-z]{2,4})\s*(\d{3}[A-Za-z]?)', q)
    return [f"{subj.upper()} {num.upper()}" for subj, num in matches]


def looks_like_course_question(q: str) -> bool:
    return bool(find_codes(normalize_query(q)) or COURSE_WORDS.search(q))


@app.get("/prereqs")
def get_prereqs():
    return PREREQS


@app.post("/plan")
def suggest_plan(req: PlanRequest):
    all_required: list[str] = []
    advanced_pool: list[str] = []
    for g in req.groups:
        if g["name"].startswith("Advanced"):
            advanced_pool.extend(g["courses"])
        else:
            all_required.extend(g["courses"])

    typical: dict[str, str] = {}
    for g in req.groups:
        for code, term in (g.get("typical") or {}).items():
            typical[code] = term

    placed_flat: set[str] = set()
    if req.placed:
        for codes in req.placed.values():
            placed_flat.update(codes)
    already_done = set(req.taken) | placed_flat
    to_schedule = [c for c in all_required if c not in already_done]

    study_terms = [t for t in req.terms if t != "COOP"]
    if not study_terms:
        return {"answer": "No study terms found."}

    # Full-load schedule: 5 courses per term = 40 courses across 8 terms = 20.0 units
    MAX_PER_TERM = 5
    term_index = {t: i for i, t in enumerate(study_terms)}
    prereqs = PREREQS

    schedule: dict[str, list[str]] = {t: [] for t in study_terms}

    def placed_before(term_idx: int) -> set[str]:
        """All courses committed to terms 0..term_idx-1, plus taken courses."""
        result = set(req.taken)
        for j in range(term_idx):
            for c in schedule[study_terms[j]]:
                result.add(c.replace("[suggested]", "").strip())
        return result

    def prereqs_ok(code: str, term_idx: int) -> bool:
        if code not in prereqs:
            return True
        done = placed_before(term_idx)
        for group in prereqs[code]:
            # Strip grade-minimum suffixes (e.g. "MATH 138:60" → "MATH 138")
            if not any(c.split(":")[0] in done for c in group):
                return False
        return True

    def sort_key(code: str):
        t = typical.get(code, study_terms[-1])
        return (term_index.get(t, len(study_terms)), code)

    # Phase 1 — required courses with prereq checking (multi-pass to resolve dependencies)
    unplaced = sorted(to_schedule, key=sort_key)
    for _ in range(len(study_terms) + 2):
        if not unplaced:
            break
        still_unplaced: list[str] = []
        for code in unplaced:
            target = typical.get(code, study_terms[-1])
            start_idx = term_index.get(target, 0)
            placed = False
            for i in range(start_idx, len(study_terms)):
                if prereqs_ok(code, i) and len(schedule[study_terms[i]]) < MAX_PER_TERM:
                    schedule[study_terms[i]].append(code)
                    placed = True
                    break
            if not placed:
                still_unplaced.append(code)
        unplaced = still_unplaced

    # Phase 2 — suggest Advanced Options spread across 3A → 3B → 4A → 4B
    # Cap at 2 per term so suggestions appear in every upper-year term, not piled in 3A
    ADV_PER_TERM = 2
    adv_start_idx = term_index.get("3A", len(study_terms) // 2)
    adv_per_term: dict[str, int] = {t: 0 for t in study_terms}

    for code in [c for c in advanced_pool if c not in already_done]:
        for i in range(adv_start_idx, len(study_terms)):
            t = study_terms[i]
            if (prereqs_ok(code, i)
                    and len(schedule[t]) < MAX_PER_TERM
                    and adv_per_term[t] < ADV_PER_TERM):
                schedule[t].append(code + "[suggested]")
                adv_per_term[t] += 1
                break

    # Phase 3 — fill remaining slots: 5 Non-Math Elective slots then Free Elective
    # BMath requires ≥5 non-math (non-Math-faculty) credits; rest are free electives
    non_math_left = 5
    lines = []
    for term in study_terms:
        parts = list(schedule[term])
        for _ in range(MAX_PER_TERM - len(parts)):
            if non_math_left > 0:
                parts.append("Non-Math Elective")
                non_math_left -= 1
            else:
                parts.append("Free Elective")
        lines.append(f"{term}: {', '.join(parts)}")

    return {"answer": "\n".join(lines)}


@app.get("/courses")
def get_courses():
    with open("data/course_catalog.json") as f:
        return json.load(f)
    
    
@app.get("/")
def home():
    return FileResponse("index.html")

@app.post("/ask")
def ask(req: AskRequest):
    question = req.question
    history = req.history or []

    if is_greeting(question):
        intro = (
            "Hey there, Warrior! \U0001FAE1 I'm WatAsk \u2014 your UW course advisor. "
            "I can answer questions about any CS, MATH, STAT, PMATH, AMATH, ACTSC, or CO course \u2014 "
            "difficulty, prereqs, what students say, and how it fits your plan.\n\n"
            "I also know your current program, completed courses, and term sequence, "
            "so ask me things like:\n"
            "\u2022 \"Should I take CS 245 or 245E?\"\n"
            "\u2022 \"I'm skipping CS 136 \u2014 what are my options?\"\n"
            "\u2022 \"Generate a plan for my remaining terms\"\n"
            "\u2022 \"Is STAT 330 hard after STAT 231?\""
        )
        return {"question": question, "answer": intro, "source_codes": [], "sources": []}

    if not history and not looks_like_course_question(question):
        return {
            "question": question,
            "answer": (
                "Appreciate it! \U0001F60A I'm best at course questions though \u2014 "
                "try asking me about a specific Waterloo course, like \"is MATH 239 hard?\" "
                "or \"should I take CS 245 or 245E?\""
            ),
            "source_codes": [],
            "sources": [],
        }

    clean_question = normalize_query(question)

    if history:
        search_text = normalize_query(history[-1].question) + " " + clean_question
    else:
        search_text = clean_question

    question_vector = embed(search_text)
    result = supabase.rpc("match_courses", {
        "query_embedding": question_vector,
        "match_count": 4
    }).execute()

    sources = []
    seen_codes = set()
    for row in result.data:
        code = row.get("code")
        if code and code not in seen_codes:
            sources.append({"code": code, "text": row["text"]})
            seen_codes.add(code)

    codes = find_codes(clean_question)
    for code in codes:
        exact = supabase.table("courses").select("code,text").eq("code", code).execute()
        for row in exact.data:
            if row["code"] not in seen_codes:
                sources.insert(0, {"code": row["code"], "text": row["text"]})
                seen_codes.add(row["code"])

    context = "\n\n".join(s["text"] for s in sources)

    convo = ""
    for turn in history:
        convo += f"Student: {turn.question}\nWatAsk: {turn.answer}\n\n"

    student_section = f"\nStudent profile: {req.student_context}" if req.student_context else ""

    prompt = f"""You are WatAsk, a knowledgeable UW academic advisor chatbot.
You know this student's program, completed courses, and current plan — use that context to give tailored advice.{student_section}

IMPORTANT — reading the student profile:
- "required courses" = what the degree actually mandates
- "plan so far" = courses the student placed in their schedule (mix of required + optional electives they chose)
- NEVER call a course "required" just because it appears in "plan so far". Only call something required if it's in the "required courses" list.

Primary source: use the course information retrieved below.
If the retrieved info doesn't fully cover the question (e.g. a planning question, an edge case, or a course comparison), draw on your general knowledge of UW programs to give a helpful answer — but flag if you're less certain.

When you mention difficulty ratings, translate them into plain language:
- ~30% easy → "most students found it quite hard"
- ~45-55% easy → "students were split on difficulty"
- ~70%+ easy → "most students found it manageable"
Same for "liked" and "useful" ratings.

For planning questions ("generate a plan", "what should I take next"), produce a concrete term-by-term suggestion based on the student's profile above and prereqs — don't refuse or deflect.

Keep answers to 2-5 sentences, direct and conversational like a senior student. Use the conversation history to understand follow-up context.

Retrieved course information:
{context if context else "(no specific course data retrieved — use general knowledge)"}

Conversation so far:
{convo if convo else "(none yet)"}
Current question: {clean_question}
"""

    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=prompt
        )
        answer_text = response.text
    except Exception as e:
        return {"question": question, "answer": f"API error: {e}", "source_codes": [], "sources": []}

    answer_upper = answer_text.upper()
    mentioned = [s["code"] for s in sources if s["code"].upper() in answer_upper]
    source_codes = mentioned if mentioned else [s["code"] for s in sources]

    return {
        "question": question,
        "answer": answer_text,
        "source_codes": source_codes,
        "sources": sources,
    }