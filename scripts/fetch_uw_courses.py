"""
Fetch MATH, CS, and STAT courses from UW Open Data API.
Writes waterloo_data.json to the project root.
Requires UW_API_KEY in .env.
"""
import os
import json
import time
import requests
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))

BASE = "https://openapi.data.uwaterloo.ca/v3"
HEADERS = {"x-api-key": os.environ["UW_API_KEY"]}
TARGET_SUBJECTS = ["MATH", "CS", "STAT"]
TERMS = ["1265", "1269", "1271", "1275"]

subjects = requests.get(f"{BASE}/Subjects", headers=HEADERS).json()
print(f"Subjects fetched: {len(subjects)}")

all_courses = []
for term_code in TERMS:
    print(f"\nTerm {term_code}:")
    for subj in TARGET_SUBJECTS:
        r = requests.get(f"{BASE}/Courses/{term_code}/{subj}", headers=HEADERS)
        if r.status_code == 200:
            courses = r.json()
            for c in courses:
                c["_termCode"] = term_code
            all_courses.extend(courses)
            print(f"  {subj}: {len(courses)}")
        else:
            print(f"  {subj}: ERROR {r.status_code}")
        time.sleep(1)

out = os.path.join(ROOT, "waterloo_data.json")
with open(out, "w") as f:
    json.dump({"subjects": subjects, "courses": all_courses}, f, indent=2)
print(f"\nSaved {len(all_courses)} records to {out}")
