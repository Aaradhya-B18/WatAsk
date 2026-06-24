import os
from dotenv import load_dotenv
from fastapi import FastAPI
from google import genai
from sentence_transformers import SentenceTransformer, util
from supabase import create_client

load_dotenv()
client=genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
model = SentenceTransformer("all-MiniLM-L6-v2")

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

app = FastAPI()

@app.post("/ask")
def ask(question: str):
    question_vector = model.encode(question).tolist()
    result = supabase.rpc("match_courses", {
        "query_embedding" : question_vector,
        "match_count":2
    }).execute()

    retrieved = [row["text"] for row in result.data]

    context = "\n".join(retrieved)
    prompt = f"""use the following information to answer the student's question.
Only use the information, and if it doesen't contain the answer,say so.

Information:
{context}

Question: {question}
"""
    response = client.models.generate_content(
        model = "gemini-2.5-flash",
        contents = prompt
    )
    return {"question": question, "answer": response.text, "sources":retrieved}
