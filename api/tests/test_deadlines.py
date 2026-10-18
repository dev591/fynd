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


@pytest.mark.parametrize("phrase,days", [
    ("within two weeks", 14), ("in three days", 3), ("one week", 7), ("ek hafte mein", 7), ("do din mein", 2),
    ("कल तक", 1), ("परसों तक", 2), ("3 हफ्ते में", 21), ("पांच दिन में", 5), ("शुक्रवार तक", 5), ("अगले हफ्ते", 7),
])
def test_number_words_and_devanagari_deadlines(phrase, days):
    assert resolve_need_days(phrase, TODAY) == days


def test_a_deadline_the_buyer_said_but_we_cannot_read_gets_an_honest_warning_not_a_false_accusation():
    from app.intake import build_draft
    raw = {"item": "M10 bolt", "quantity": 50, "need_in_days": 9, "need_by_phrase": "whenever the truck is free", "priority": None}
    out = build_draft("I need 50 M10 bolts whenever the truck is free", raw, {"m10 bolt": "M10 bolt"}, TODAY)
    assert out["draft"]["need_in_days"] is None and "need_in_days" in out["missing"]
    assert not any("did not say" in w for w in out["warnings"])
    assert any("whenever the truck is free" in w and "number of days" in w for w in out["warnings"])


def test_a_number_of_days_the_model_invented_is_still_dropped_and_not_blamed_on_the_buyer():
    from app.intake import build_draft
    raw = {"item": "M10 bolt", "quantity": 50, "need_in_days": 9, "need_by_phrase": None, "priority": None}
    out = build_draft("I need 50 M10 bolts", raw, {"m10 bolt": "M10 bolt"}, TODAY)
    assert out["draft"]["need_in_days"] is None
