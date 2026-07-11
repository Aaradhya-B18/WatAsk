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
    groups: List[dict]          # [{name, courses}]
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

@app.post("/plan")
def suggest_plan(req: PlanRequest):
    taken_str = ", ".join(req.taken) if req.taken else "none yet"

    # Flatten all required courses across groups
    all_required = []
    for g in req.groups:
        if not g["name"].startswith("Advanced"):
            all_required.extend(g["courses"])
    # Remove already taken or placed
    placed_flat = set()
    if req.placed:
        for codes in req.placed.values():
            placed_flat.update(codes)
    already_done = set(req.taken) | placed_flat
    to_schedule = [c for c in all_required if c not in already_done]

    terms_str = ", ".join(req.terms)

    placed_str = ""
    if req.placed:
        placed_str = "; ".join(
            f"{t}: {', '.join(codes)}" for t, codes in req.placed.items() if codes
        ) or "none"
    else:
        placed_str = "none"

    prompt = f"""You are a UW academic advisor generating a term-by-term course plan.

STUDENT: {req.program}
Already completed: {taken_str}
Already placed in grid: {placed_str}
Study terms in order: {terms_str}
Required courses still to schedule: {', '.join(to_schedule) if to_schedule else 'none — all done!'}

STRICT RULES (follow every one):
1. CO-REQUISITES — these MUST appear in the exact same term:
   - CS 136 and CS 136L always together
2. PREREQUISITES — determine the CS path from the required course list, then respect ordering:
   PATH A (non-CS programs): CS 115 in 1A → CS 116 in 1B → CS 234 in 2A (if in required list)
   PATH B (CS-heavy programs): CS 135 or CS 145 in 1A → CS 136 + CS 136L in 1B
   Do NOT mix paths. Use whichever path appears in the required course list.
   - MATH 135, MATH 137 (or MATH 145/147) go in 1A; MATH 136, MATH 138 go in 1B
   - MATH 235 and MATH 239 require MATH 136 → earliest 2A
   - STAT 230 before STAT 231; STAT 240 before STAT 241
   - AMATH 231, AMATH 250 require MATH 138 → earliest 2A
   - AMATH 271 requires MATH 138 → earliest 2B or 3A
   - AMATH 331 requires MATH 237 → earliest 3A
   - AMATH 342, AMATH 353 require AMATH 231 and AMATH 250 → earliest 3B/4A
   - ACTSC 231 requires MATH 128/138 → earliest 2A
   - CO 250 requires MATH 136 → earliest 2A
   - CS 240, CS 241, CS 245, CS 246 require CS 136 (PATH B) → earliest 2A or 2B
   - 300-level courses require their 200-level prereqs done first
   - 400-level courses require their 300-level prereqs done first
3. COURSE LOAD — list only required courses per term (students fill with electives to reach 5/term)
4. DISTRIBUTION — spread required courses across ALL study terms given above, working in order
   - 4A and 4B are normal study terms; include them whenever required courses remain
   - Max 4 required courses per study term
   - Output all terms that have at least 1 required course; skip only genuinely empty terms

Output format — ONLY the schedule, one term per line, no preamble:
[term]: [code1], [code2], ..."""

    try:
        response = client.models.generate_content(model="gemini-3.1-flash-lite", contents=prompt)
        return {"answer": response.text}
    except Exception as e:
        return {"answer": f"Error generating plan: {e}", "error": True}


@app.get("/courses")
def get_courses():
    with open("planner_courses.json") as f:
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