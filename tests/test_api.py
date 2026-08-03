"""API-level tests using FastAPI TestClient. External calls (Gemini, Supabase) are mocked."""
import json
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    # Patch external services before importing server so env vars aren't needed
    with patch("services.embeddings.genai"), \
         patch("server.create_client", return_value=MagicMock()):
        from server import app
        yield TestClient(app)


class TestPrereqsEndpoint:
    def test_returns_dict(self, client):
        r = client.get("/prereqs")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)

    def test_contains_known_course(self, client):
        r = client.get("/prereqs")
        data = r.json()
        assert "MATH 136" in data or len(data) > 50  # at least 50 courses loaded

    def test_prereq_format(self, client):
        r = client.get("/prereqs")
        data = r.json()
        for code, groups in list(data.items())[:5]:
            assert isinstance(groups, list)
            for group in groups:
                assert isinstance(group, list)


class TestPlanEndpoint:
    PAYLOAD = {
        "program": "stat",
        "terms": ["1A", "1B", "COOP", "2A", "COOP", "2B", "3A", "3B", "4A", "4B"],
        "taken": [],
        "groups": [
            {
                "name": "Core Math",
                "courses": ["MATH 135", "MATH 136", "MATH 137", "MATH 138"],
                "typical": {"MATH 135": "1A", "MATH 137": "1A", "MATH 136": "1B", "MATH 138": "1B"},
            },
            {
                "name": "Advanced Options",
                "courses": ["STAT 330"],
                "typical": {},
            },
        ],
        "placed": None,
    }

    def test_returns_200(self, client):
        r = client.post("/plan", json=self.PAYLOAD)
        assert r.status_code == 200

    def test_answer_field_present(self, client):
        r = client.post("/plan", json=self.PAYLOAD)
        assert "answer" in r.json()

    def test_plan_contains_required_courses(self, client):
        r = client.post("/plan", json=self.PAYLOAD)
        answer = r.json()["answer"]
        for code in ["MATH 135", "MATH 136", "MATH 137", "MATH 138"]:
            assert code in answer, f"{code} missing from plan"

    def test_taken_courses_excluded(self, client):
        payload = {**self.PAYLOAD, "taken": ["MATH 135", "MATH 137"]}
        r = client.post("/plan", json=payload)
        answer = r.json()["answer"]
        # Taken courses should not appear as scheduled
        lines = {line.split(":")[0].strip(): line for line in answer.splitlines() if ":" in line}
        all_courses = [c.strip() for line in lines.values() for c in line.split(":", 1)[1].split(",")]
        assert "MATH 135" not in all_courses
        assert "MATH 137" not in all_courses

    def test_no_coop_in_output(self, client):
        r = client.post("/plan", json=self.PAYLOAD)
        assert "COOP" not in r.json()["answer"]


class TestAskEndpoint:
    def _mock_supabase(self):
        mock = MagicMock()
        mock.rpc.return_value.execute.return_value.data = [
            {"code": "CS 246", "text": "CS 246 is an OOP course. Students find it moderately difficult."}
        ]
        mock.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        return mock

    def test_greeting_returns_intro(self, client):
        r = client.post("/ask", json={"question": "hello", "history": []})
        assert r.status_code == 200
        data = r.json()
        assert "WatAsk" in data["answer"] or "UW" in data["answer"]
        assert data["source_codes"] == []

    def test_off_topic_deflects(self, client):
        r = client.post("/ask", json={"question": "you are great", "history": []})
        assert r.status_code == 200
        data = r.json()
        assert "course" in data["answer"].lower() or "waterloo" in data["answer"].lower()

    def test_course_question_hits_rag(self, client):
        mock_sb = self._mock_supabase()
        mock_embed = MagicMock(return_value=[0.1] * 768)

        with patch("services.rag.embed", mock_embed), \
             patch("services.rag.get_client") as mock_genai:
            mock_genai.return_value.models.generate_content.return_value.text = (
                "CS 246 covers object-oriented programming in C++."
            )
            # Inject mock supabase via the server module
            import server
            original = server.supabase
            server.supabase = mock_sb
            try:
                r = client.post("/ask", json={"question": "tell me about CS 246", "history": []})
            finally:
                server.supabase = original

        assert r.status_code == 200
        data = r.json()
        assert len(data["answer"]) > 10
        assert "source_codes" in data

    def test_response_structure(self, client):
        r = client.post("/ask", json={"question": "hi", "history": []})
        data = r.json()
        assert all(k in data for k in ["question", "answer", "source_codes", "sources"])
