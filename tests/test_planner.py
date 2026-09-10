"""Integration tests for the plan generator — no external API calls needed."""
import json
import pytest
from services.planner import generate_plan

with open("data/prereqs.json") as f:
    PREREQS = json.load(f)

STAT_GROUPS = [
    {
        "name": "Core Math",
        "courses": ["MATH 135", "MATH 136", "MATH 137", "MATH 138", "MATH 235", "MATH 237", "MATH 239"],
        "typical": {
            "MATH 135": "1A", "MATH 137": "1A",
            "MATH 136": "1B", "MATH 138": "1B",
            "MATH 235": "2A", "MATH 237": "2A", "MATH 239": "2B",
        },
    },
    {
        "name": "Core Statistics",
        "courses": ["STAT 230", "STAT 231"],
        "typical": {"STAT 230": "2A", "STAT 231": "2B"},
    },
    {
        "name": "CS Requirement",
        "courses": ["CS 115", "CS 116"],
        "typical": {"CS 115": "1A", "CS 116": "1B"},
    },
    {
        "name": "Advanced Options",
        "courses": ["STAT 330", "STAT 331", "STAT 333"],
        "typical": {},
    },
]

STUDY_TERMS = ["1A", "1B", "2A", "2B", "3A", "3B", "4A", "4B"]
ALL_TERMS   = ["1A", "1B", "COOP", "2A", "COOP", "2B", "COOP", "3A", "COOP", "3B", "COOP", "4A", "COOP", "4B"]


def parse_plan(result: str) -> dict[str, list[str]]:
    plan = {}
    for line in result.strip().splitlines():
        if ":" not in line:
            continue
        term, rest = line.split(":", 1)
        plan[term.strip()] = [c.strip() for c in rest.split(",") if c.strip()]
    return plan


class TestGeneratePlan:
    def test_returns_string(self):
        result = generate_plan("stat", ALL_TERMS, [], STAT_GROUPS, None, PREREQS)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_covers_all_study_terms(self):
        result = generate_plan("stat", ALL_TERMS, [], STAT_GROUPS, None, PREREQS)
        plan = parse_plan(result)
        for t in STUDY_TERMS:
            assert t in plan, f"Term {t} missing from plan"

    def test_each_term_has_5_courses(self):
        result = generate_plan("stat", ALL_TERMS, [], STAT_GROUPS, None, PREREQS)
        plan = parse_plan(result)
        for term, courses in plan.items():
            assert len(courses) == 5, f"{term} has {len(courses)} courses, expected 5"

    def test_required_courses_all_scheduled(self):
        required = [c for g in STAT_GROUPS if not g["name"].startswith("Advanced") for c in g["courses"]]
        result = generate_plan("stat", ALL_TERMS, [], STAT_GROUPS, None, PREREQS)
        plan = parse_plan(result)
        all_scheduled = [c for courses in plan.values() for c in courses]
        for code in required:
            assert code in all_scheduled, f"{code} not scheduled"

    def test_taken_courses_excluded(self):
        taken = ["MATH 135", "MATH 137", "CS 115"]
        result = generate_plan("stat", ALL_TERMS, taken, STAT_GROUPS, None, PREREQS)
        plan = parse_plan(result)
        all_scheduled = [c for courses in plan.values() for c in courses]
        for code in taken:
            assert code not in all_scheduled, f"Taken course {code} should not be re-scheduled"

    def test_prereqs_respected(self):
        """STAT 230 requires MATH 137; they should not be in the same or wrong order."""
        result = generate_plan("stat", ALL_TERMS, [], STAT_GROUPS, None, PREREQS)
        plan = parse_plan(result)
        flat_terms = [t for t in STUDY_TERMS if t in plan]
        stat230_term = next((t for t in flat_terms if "STAT 230" in plan[t]), None)
        math137_term = next((t for t in flat_terms if "MATH 137" in plan[t]), None)
        if stat230_term and math137_term:
            assert flat_terms.index(math137_term) < flat_terms.index(stat230_term), \
                "MATH 137 must come before STAT 230"

    def test_no_coop_terms_in_output(self):
        result = generate_plan("stat", ALL_TERMS, [], STAT_GROUPS, None, PREREQS)
        plan = parse_plan(result)
        assert "COOP" not in plan

    def test_empty_terms_returns_error(self):
        result = generate_plan("stat", ["COOP", "COOP"], [], STAT_GROUPS, None, PREREQS)
        assert "No study terms" in result
