import json
import logging

import sentry_sdk
from google.genai import types

from services.embeddings import get_client

logger = logging.getLogger(__name__)

MAX_FILE_BYTES = 8 * 1024 * 1024  # 8MB — plenty for a text-based PDF transcript
ALLOWED_MIME_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/webp"}

PROMPT = """You are reading a University of Waterloo unofficial transcript (from Quest).

Extract every completed course into a JSON array. For each course return:
- "code": the course code, normalized as "SUBJECT NUMBER" (e.g. "CS 135", "MATH 137") - uppercase subject, single space, no leading zeros.
- "term": the study-sequence term as UW labels it, e.g. "1A", "1B", "2A", "2B", "3A", "3B", "4A", "4B", "5A", "5B".
  Transcripts usually group courses under headers like "Fall 2023" or "1A" directly. If only calendar
  terms are shown, infer the sequence term from chronological order and the student's level.
  If you genuinely cannot determine it, use null.
- "grade": the numeric percentage grade if shown (integer, no % sign). If only a letter grade or
  "CR"/"DROP"/"WD" is shown with no percentage, use null. Do not guess a number that isn't printed.

Skip: in-progress/current courses with no final grade yet, withdrawn/dropped courses, and non-academic
items (like PD seminars) unless they have a real course code and grade.

Return ONLY a JSON object of the shape {"courses": [{"code": "...", "term": "...", "grade": ...}, ...]}.
No prose, no markdown fences.
"""


def parse_transcript(file_bytes: bytes, mime_type: str) -> dict:
    """Extract {code, term, grade} rows from a transcript PDF/image via Gemini.
    Returns {"courses": [...]} on success, {"courses": [], "error": "..."} on failure.
    """
    if mime_type not in ALLOWED_MIME_TYPES:
        return {"courses": [], "error": "Unsupported file type. Upload a PDF or image of your transcript."}
    if len(file_bytes) > MAX_FILE_BYTES:
        return {"courses": [], "error": "File too large — please upload a file under 8MB."}

    try:
        client = get_client()
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=[
                types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
                PROMPT,
            ],
            config={"response_mime_type": "application/json"},
        )
        data = json.loads(response.text)
        courses = data.get("courses", []) if isinstance(data, dict) else []

        cleaned = []
        for c in courses:
            code = (c.get("code") or "").strip().upper()
            if not code:
                continue
            term = c.get("term")
            term = term.strip().upper() if isinstance(term, str) and term.strip() else None
            grade = c.get("grade")
            grade = int(grade) if isinstance(grade, (int, float)) else None
            cleaned.append({"code": code, "term": term, "grade": grade})
        return {"courses": cleaned}
    except Exception:
        logger.exception("Transcript parsing failed")
        sentry_sdk.capture_exception()
        return {"courses": [], "error": "Couldn't read that transcript — please try again or add courses manually."}
