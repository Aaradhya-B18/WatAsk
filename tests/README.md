# tests/

37-test pytest suite: `python -m pytest tests/ -q`

- **`test_planner.py`** — Scheduler correctness: prereqs, retakes, term capacity.
- **`test_api.py`** — FastAPI endpoints: response shapes, rate limits, no leaked errors.
- **`test_helpers.py`** — Shared fixtures used by the other two files.
