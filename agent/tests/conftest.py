import json
from pathlib import Path

import pytest

from app.engine import clue_engine
from app.models.case import CaseFile

CASES = Path(__file__).resolve().parent.parent / "app" / "cases"


def load_raw(name: str = "ashford_manor") -> dict:
    return json.loads((CASES / f"{name}.json").read_text())


@pytest.fixture
def raw_case() -> dict:
    return load_raw()


@pytest.fixture
def case(raw_case) -> CaseFile:
    return CaseFile.model_validate(raw_case)


@pytest.fixture
def progress(case):
    p = clue_engine.new_progress(case)
    p.phase = "investigating"
    return p
