"""Unit tests for query-parsing helpers in services/rag.py."""
import pytest
from services.rag import is_greeting, normalize_query, find_codes, looks_like_course_question


class TestIsGreeting:
    def test_hi(self):
        assert is_greeting("hi") is True

    def test_hello_with_punctuation(self):
        assert is_greeting("hello!") is True

    def test_what_can_you_do(self):
        assert is_greeting("what can you do") is True

    def test_course_question_not_greeting(self):
        assert is_greeting("is MATH 135 hard") is False

    def test_empty_string(self):
        assert is_greeting("") is False


class TestNormalizeQuery:
    def test_removes_extra_spaces(self):
        assert normalize_query("CS  135") == "CS 135"

    def test_inserts_space_between_letters_and_digits(self):
        assert normalize_query("CS135") == "CS 135"

    def test_replaces_hyphens(self):
        assert normalize_query("well-known course") == "well known course"

    def test_mixed(self):
        assert normalize_query("MATH237 and CS246") == "MATH 237 and CS 246"


class TestFindCodes:
    def test_single_code(self):
        assert find_codes("is MATH 135 hard") == ["MATH 135"]

    def test_multiple_codes(self):
        codes = find_codes("should I take CS 246 or CS 246E")
        assert "CS 246" in codes
        assert "CS 246E" in codes

    def test_no_codes(self):
        assert find_codes("what courses are hard") == []

    def test_adjacent_letters_and_digits(self):
        assert find_codes("CS135") == ["CS 135"]


class TestLooksLikeCourseQuestion:
    def test_with_code(self):
        assert looks_like_course_question("tell me about CS 246") is True

    def test_with_keyword(self):
        assert looks_like_course_question("which courses are easy") is True

    def test_irrelevant_message(self):
        assert looks_like_course_question("you are awesome") is False

    def test_planning_keyword(self):
        assert looks_like_course_question("help me plan my schedule") is True
