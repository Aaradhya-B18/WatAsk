"""
Convert uwflow_ratings.json into text blobs for embedding.
Filters low-rating courses, writes data_generated.py to project root.
Run after scrape_uwflow.py.
"""
import os
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIN_RATINGS = 10


def describe(label, value):
    if value is None:
        return None
    p = value * 100
    if label == "easy":
        if p < 35:  return f"most students found it hard ({round(p)}% rated it easy)"
        if p < 55:  return f"students were split on difficulty ({round(p)}% rated it easy)"
        return f"most students found it manageable ({round(p)}% rated it easy)"
    if label == "liked":
        if p < 40:  return f"it's not well-liked ({round(p)}% of students liked it)"
        if p < 65:  return f"reception is mixed ({round(p)}% liked it)"
        return f"it's well-liked ({round(p)}% of students liked it)"
    if label == "useful":
        if p < 40:  return f"many found it not very useful ({round(p)}% found it useful)"
        if p < 65:  return f"usefulness is mixed ({round(p)}% found it useful)"
        return f"most found it useful ({round(p)}% found it useful)"


def main():
    with open(os.path.join(ROOT, "uwflow_ratings.json")) as f:
        courses = json.load(f)

    entries = []
    for c in courses:
        if not c.get("num_ratings") or c["num_ratings"] < MIN_RATINGS:
            continue

        parts = [f"{c['code']} — {c['name']}."]
        if c.get("description"):
            parts.append(c["description"])

        sentiment = [describe(l, c.get(l)) for l in ("easy", "liked", "useful")]
        sentiment = [s for s in sentiment if s]
        if sentiment:
            parts.append(
                "Student sentiment: " + "; ".join(sentiment) +
                f", based on {c['num_ratings']} ratings."
            )

        if c.get("prereqs"):
            parts.append(f"Prerequisites: {c['prereqs']}")
        if c.get("antireqs"):
            parts.append(f"Antirequisites: {c['antireqs']}")

        entries.append({"code": c["code"], "text": " ".join(parts)})

    out = os.path.join(ROOT, "data_generated.py")
    with open(out, "w") as f:
        f.write("# Auto-generated from uwflow_ratings.json — do not edit by hand\n")
        f.write("courses = [\n")
        for e in entries:
            code = e["code"].replace('"', '\\"')
            text = e["text"].replace("\\", "\\\\").replace('"', '\\"')
            f.write(f'    {{"code": "{code}", "text": "{text}"}},\n')
        f.write("]\n")

    print(f"Kept {len(entries)} courses (>= {MIN_RATINGS} ratings) → {out}")
    if entries:
        print("Example:", entries[0]["code"], "->", entries[0]["text"][:200], "...")


if __name__ == "__main__":
    main()
