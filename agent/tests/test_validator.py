import copy

import pytest

from app.engine.case_library import library
from app.engine.validator import minimum_actions, parse_case, validate_case

NEUTRAL_CLUES = ("c4", "c6", "c7", "c11", "c13", "c16")


def errors_for(raw: dict) -> list[str]:
    case, errors = parse_case(raw)
    return errors if case is None else validate_case(case)


def test_golden_cases_pass():
    for case in library().values():
        assert validate_case(case) == []


def test_golden_case_budget(case):
    assert minimum_actions(case) == 4  # 2 examines, 1 interrogation, 1 confront


def test_schema_failure(raw_case):
    del raw_case["culprit"]
    assert any(e.startswith("schema") for e in errors_for(raw_case))


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda r: r.update(culprit="nobody"), "not a suspect"),
        (lambda r: r["solution"]["requiredEvidence"].append("c99"), "does not exist"),
        (
            lambda r: r.__setitem__("contradictions", [c for c in r["contradictions"] if c["a"] != "s2_lie_will"]),
            "s2_lie_will has no contradiction",
        ),
        (lambda r: [c.update(pointsTo=[]) for c in r["clues"] if c["id"] in ("c5", "c8", "c15")], "non-herring clues"),
        (
            lambda r: [c.update(pointsTo=["s4"], isRedHerring=False) for c in r["clues"] if c["id"] in NEUTRAL_CLUES],
            "innocent s4",
        ),
        (
            lambda r: [e.update(location="library") for e in r["truthTimeline"] if e["location"] == "study"],
            "crime scene",
        ),
        (lambda r: r.update(maxTurns=6), "budget"),
        (lambda r: r["solution"]["acceptableMotives"].append("greed"), "not offered"),
    ],
)
def test_broken_cases_are_rejected(raw_case, mutate, expected):
    raw = copy.deepcopy(raw_case)
    mutate(raw)
    errors = errors_for(raw)
    assert any(expected in e for e in errors), errors


def test_confront_only_clue_must_be_revealable(raw_case):
    raw = copy.deepcopy(raw_case)
    for c in raw["contradictions"]:
        if c["effect"].get("reveals") == "c9":
            c["effect"]["reveals"] = None
    assert any("confront-only" in e for e in errors_for(raw))
