import os 
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from supabase import create_client
from data import courses

load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

model = SentenceTransformer("all-MiniLM-L6-v2")


for course in courses:
    embedding = model.encode(course["text"]).tolist()
    supabase.table("courses").insert({
        "code":course["code"],
        "text":course["text"],
        "embedding":embedding
    }).execute()
    print("Inserted", course["code"])

print("All courses loaded successfully")



