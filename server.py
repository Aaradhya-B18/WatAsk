import os
import json
from typing import List, Optional

import sentry_sdk
from dotenv import load_dotenv
from fastapi import FastAPI, File, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from supabase import create_client

from services.rag import answer
from services.planner import generate_plan
from services.transcript import parse_transcript

ROOT = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(ROOT, ".env"))

# No-ops safely if SENTRY_DSN isn't set (e.g. local dev)
sentry_sdk.init(dsn=os.getenv("SENTRY_DSN"), traces_sample_rate=0.1, send_default_pii=False)

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

with open(os.path.join(ROOT, "data", "prereqs.json")) as f:
    PREREQS: dict = json.load(f)

limiter = Limiter(key_func=get_remote_address)

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    groups: List[dict]
    placed: Optional[dict] = None
    current_term: Optional[str] = None
    specialization: Optional[List[str]] = None
    overload: Optional[bool] = False
    retaking: Optional[List[str]] = []
    taken_terms: Optional[dict] = {}
    taken_grades: Optional[dict] = {}


@app.get("/")
def home():
    return FileResponse(os.path.join(ROOT, "index.html"))


@app.get("/prereqs")
def get_prereqs():
    return PREREQS


@app.get("/courses")
def get_courses():
    with open(os.path.join(ROOT, "data", "course_catalog.json")) as f:
        return json.load(f)


@app.post("/parse-transcript")
@limiter.limit("5/minute")
async def parse_transcript_endpoint(request: Request, file: UploadFile = File(...)):
    file_bytes = await file.read()
    result = parse_transcript(file_bytes, file.content_type)
    return JSONResponse(result)


@app.post("/ask")
@limiter.limit("15/minute")
def ask(request: Request, req: AskRequest):
    return answer(
        question=req.question,
        history=req.history or [],
        student_context=req.student_context,
        supabase=supabase,
    )


@app.post("/plan")
@limiter.limit("30/minute")
def suggest_plan(request: Request, req: PlanRequest):
    result = generate_plan(
        program=req.program,
        terms=req.terms,
        taken=req.taken,
        groups=req.groups,
        placed=req.placed,
        prereqs=PREREQS,
        specialization=req.specialization,
        current_term=req.current_term,
        max_per_term=6 if req.overload else 5,
        extra_slots=len(req.retaking or []) if req.overload else 0,
        retaking=req.retaking or [],
        taken_grades={k: float(v) for k, v in (req.taken_grades or {}).items()},
        taken_terms=req.taken_terms or {},
    )
    return {"answer": result}
