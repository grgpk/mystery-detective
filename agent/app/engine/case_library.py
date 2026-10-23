"""Hand-written cases, validated at startup. (M4 adds generated cases behind the same interface.)"""

import json
import random
from datetime import date
from functools import cache
from pathlib import Path

from app.engine.validator import parse_case, validate_case
from app.models.case import CaseFile

CASES_DIR = Path(__file__).resolve().parent.parent / "cases"
NEW_CASE_ID = "new"  # asks for a freshly generated case from the pool
DAILY_CASE_ID = "daily"  # asks for today's shared case


class InvalidCaseError(Exception):
    pass


def load_case_file(path: Path) -> CaseFile:
    case, errors = parse_case(json.loads(path.read_text()))
    if case is not None:
        errors = validate_case(case)
    if errors or case is None:
        raise InvalidCaseError(f"{path.name}: " + "; ".join(errors))
    return case


@cache
def library() -> dict[str, CaseFile]:
    cases = {}
    for path in sorted(CASES_DIR.glob("*.json")):
        case = load_case_file(path)
        cases[case.case_id] = case
    if not cases:
        raise InvalidCaseError("no playable cases found")
    return cases


def pick_case(case_id: str | None = None, rng: random.Random | None = None) -> CaseFile:
    """The requested case, or a random one if none (or an unknown id) is asked for."""
    cases = library()
    if case_id in cases:
        return cases[case_id]
    return (rng or random).choice(list(cases.values()))


def catalogue() -> list[dict]:
    """Spoiler-free summaries for the case picker: setting only, nothing about the crime's solution."""
    return [
        {
            "caseId": case.case_id,
            "title": case.setting.title,
            "place": case.setting.place,
            "blurb": case.setting.era_note,
            "suspects": len(case.suspects),
        }
        for case in library().values()
    ]


def daily_case(day: date) -> CaseFile:
    """The same archive case for everyone on a given UTC day. Each cycle through the archive is shuffled
    differently, and no case repeats within a cycle."""
    cases = library()
    ids = sorted(cases)
    cycle, position = divmod(day.toordinal(), len(ids))
    random.Random(cycle).shuffle(ids)
    return cases[ids[position]]
