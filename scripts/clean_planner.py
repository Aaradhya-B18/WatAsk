"""
Clean waterloo_data.json into planner_courses.json.
Deduplicates by course code and collects terms offered.
Run after fetch_uw_courses.py.
"""
import os
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

with open(os.path.join(ROOT, "waterloo_data.json")) as f:
    data = json.load(f)

courses = {}
for c in data["courses"]:
    key = f"{c['subjectCode']} {c['catalogNumber']}"
    if key not in courses:
        courses[key] = {
            "code": key,
            "title": c["title"],
            "description": c["description"],
            "requirements": c.get("requirementsDescription", ""),
            "subject": c["subjectCode"],
            "catalogNumber": c["catalogNumber"],
            "termsOffered": [],
        }
    t = c["_termCode"]
    if t not in courses[key]["termsOffered"]:
        courses[key]["termsOffered"].append(t)

clean = sorted(courses.values(), key=lambda x: x["code"])
out = os.path.join(ROOT, "planner_courses.json")
with open(out, "w") as f:
    json.dump(clean, f, indent=2)

print(f"Cleaned: {len(clean)} unique courses → {out}")
print("Example:", json.dumps(clean[0], indent=2))
