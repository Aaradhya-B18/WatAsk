import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from google import genai
from supabase import create_client
from data import courses

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

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


supabase.table("courses").delete().neq("id", 0).execute()

for course in courses:
    embedding = embed(course["text"])
    supabase.table("courses").insert({
        "code": course["code"],
        "text": course["text"],
        "embedding": embedding
    }).execute()
    print("Inserted", course["code"])

print("All courses loaded successfully")