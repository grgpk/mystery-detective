"""Hand-written cases, validated at startup. (M4 adds generated cases behind the same interface.)"""

import json
import random
from functools import cache
from pathlib import Path

from app.engine.validator import parse_case, validate_case
from app.models.case import CaseFile

CASES_DIR = Path(__file__).resolve().parent.parent / "cases"


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
    cases = library()
    if case_id:
        return cases[case_id]
    return (rng or random).choice(list(cases.values()))
