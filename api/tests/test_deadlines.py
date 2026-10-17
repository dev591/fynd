from datetime import date

import pytest

from app.intake import resolve_need_days

TODAY = date(2026, 10, 18)          # a Sunday

CASES = [
    ("by Friday", 5), ("tomorrow", 1), ("day after tomorrow", 2), ("kal tak", 1), ("parso", 2), ("next week", 7),
    ("within a week", 7), ("in 2 weeks", 14), ("2 hafte", 14), ("in 5 days", 5), ("5 din mein", 5),
    ("25 October", 7), ("25th Oct", 7), ("October 25", 7), ("oct 25th", 7), ("by 25/10", 7), ("1st November", 14),
    ("by the 30th", 12), ("by the 10th", 23), ("end of the month", 13),
]


@pytest.mark.parametrize("phrase,days", CASES)
def test_deadline_phrases_resolve_in_code(phrase, days):
    assert resolve_need_days(phrase, TODAY) == days


@pytest.mark.parametrize("phrase", ["whenever", "market 5", "5 marketing", "", "soon"])
def test_unclear_deadlines_are_left_blank_not_guessed(phrase):
    assert resolve_need_days(phrase, TODAY) is None
