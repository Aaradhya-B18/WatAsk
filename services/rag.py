import re
from typing import Optional
from supabase import Client

from services.embeddings import embed, get_client

GREETING_TRIGGERS = [
    "hi", "hello", "hey", "yo", "help",
    "what can you do", "what can i ask", "who are you", "what is this",
    "what are you", "what do you do", "what subjects", "what courses",
    "im a uw student", "i am a uw student", "im a student", "i am a student",
]

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


def find_codes(q: str) -> list[str]:
    matches = re.findall(r'([A-Za-z]{2,4})\s*(\d{3}[A-Za-z]?)', q)
    return [f"{subj.upper()} {num.upper()}" for subj, num in matches]


def looks_like_course_question(q: str) -> bool:
    return bool(find_codes(normalize_query(q)) or COURSE_WORDS.search(q))


GREETING_RESPONSE = (
    "Hey there, Warrior! \U0001FAE1 I'm WatAsk — your UW course advisor. "
    "I can answer questions about any CS, MATH, STAT, PMATH, AMATH, ACTSC, or CO course — "
    "difficulty, prereqs, what students say, and how it fits your plan.\n\n"
    "I also know your current program, completed courses, and term sequence, "
    "so ask me things like:\n"
    "• \"Should I take CS 245 or 245E?\"\n"
    "• \"I'm skipping CS 136 — what are my options?\"\n"
    "• \"Generate a plan for my remaining terms\"\n"
    "• \"Is STAT 330 hard after STAT 231?\""
)

OFF_TOPIC_RESPONSE = (
    "Appreciate it! \U0001F60A I'm best at course questions though — "
    "try asking me about a specific Waterloo course, like \"is MATH 239 hard?\" "
    "or \"should I take CS 245 or 245E?\""
)

SYSTEM_PROMPT = """You are WatAsk, a knowledgeable UW academic advisor chatbot.
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
{context}

Conversation so far:
{convo}
Current question: {question}
"""


def answer(
    question: str,
    history: list,
    student_context: Optional[str],
    supabase: Client,
) -> dict:
    if is_greeting(question):
        return {"question": question, "answer": GREETING_RESPONSE, "source_codes": [], "sources": []}

    if not history and not looks_like_course_question(question):
        return {"question": question, "answer": OFF_TOPIC_RESPONSE, "source_codes": [], "sources": []}

    clean_question = normalize_query(question)
    search_text = (normalize_query(history[-1].question) + " " + clean_question) if history else clean_question

    question_vector = embed(search_text)
    result = supabase.rpc("match_courses", {"query_embedding": question_vector, "match_count": 4}).execute()

    sources = []
    seen_codes: set[str] = set()
    for row in result.data:
        code = row.get("code")
        if code and code not in seen_codes:
            sources.append({"code": code, "text": row["text"]})
            seen_codes.add(code)

    for code in find_codes(clean_question):
        exact = supabase.table("courses").select("code,text").eq("code", code).execute()
        for row in exact.data:
            if row["code"] not in seen_codes:
                sources.insert(0, {"code": row["code"], "text": row["text"]})
                seen_codes.add(row["code"])

    context = "\n\n".join(s["text"] for s in sources)
    convo = "".join(f"Student: {t.question}\nWatAsk: {t.answer}\n\n" for t in history)
    student_section = f"\nStudent profile: {student_context}" if student_context else ""

    prompt = SYSTEM_PROMPT.format(
        student_section=student_section,
        context=context or "(no specific course data retrieved — use general knowledge)",
        convo=convo or "(none yet)",
        question=clean_question,
    )

    try:
        gemini = get_client()
        response = gemini.models.generate_content(model="gemini-3.1-flash-lite", contents=prompt)
        answer_text = response.text
    except Exception as e:
        return {"question": question, "answer": f"API error: {e}", "source_codes": [], "sources": []}

    answer_upper = answer_text.upper()
    mentioned = [s["code"] for s in sources if s["code"].upper() in answer_upper]
    return {
        "question": question,
        "answer": answer_text,
        "source_codes": mentioned or [s["code"] for s in sources],
        "sources": sources,
    }
