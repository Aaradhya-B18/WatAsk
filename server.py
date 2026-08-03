import os
import json
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from supabase import create_client

from services.rag import answer
from services.planner import generate_plan

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

with open("data/prereqs.json") as f:
    PREREQS: dict = json.load(f)

app = FastAPI()
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


@app.get("/")
def home():
    return FileResponse("index.html")


@app.get("/prereqs")
def get_prereqs():
    return PREREQS


@app.get("/courses")
def get_courses():
    with open("data/course_catalog.json") as f:
        return json.load(f)


@app.post("/ask")
def ask(req: AskRequest):
    return answer(
        question=req.question,
        history=req.history or [],
        student_context=req.student_context,
        supabase=supabase,
    )


@app.post("/plan")
def suggest_plan(req: PlanRequest):
    result = generate_plan(
        program=req.program,
        terms=req.terms,
        taken=req.taken,
        groups=req.groups,
        placed=req.placed,
        prereqs=PREREQS,
    )
    return {"answer": result}
