# tests/

37-test pytest suite. Run from the project root:

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -q
```

## Files

- **`test_planner.py`** — Tests `services/planner.py`'s scheduler directly (no HTTP layer),
  covering prereq resolution across multi-pass placement, retake scheduling (a failed course
  must land after its original attempt, and its old grade must not count against a downstream
  prereq check), and term-capacity handling.
- **`test_api.py`** — Tests the FastAPI endpoints via `TestClient`: response shapes for
  `/courses` and `/prereqs`, rate-limit enforcement on `/ask` and `/plan`, and that error
  responses never leak an internal stack trace or exception message to the client.
- **`test_helpers.py`** — Shared fixtures (sample programs, course groups, prereq data) used
  across the other two files, so each test file doesn't redefine the same test data.

This suite is the fast, cheap check to run after any change to `services/` or `server.py`.
It does **not** validate that a specific program's course data matches the real UW/Laurier
calendar — that's a separate, manual cross-reference against official sources done whenever a
program's requirements are added or audited (see commit history on `index.html`'s `PROGRAMS`
object for the reasoning behind each program's course list).
