"""Difficulty levels: the same case, with a different budget and harder or softer suspects.

Every case is validated to be solvable in at most 60% of a Normal budget (9 of 15 turns), so Hard's budget
always leaves room to solve it.
"""

from dataclasses import dataclass
from typing import Literal

Difficulty = Literal["easy", "normal", "hard"]
DEFAULT: Difficulty = "normal"


@dataclass(frozen=True)
class Settings:
    turn_delta: int  # added to the case's turn budget
    hint_cost: int
    composure_multiplier: float  # applied to composure lost when a lie is broken
    # Extra turns that earn no score, so an easier game can't outscore a harder one on spare turns.
    unscored_turns: int


SETTINGS: dict[str, Settings] = {
    "easy": Settings(turn_delta=5, hint_cost=1, composure_multiplier=1.3, unscored_turns=5),
    "normal": Settings(turn_delta=0, hint_cost=2, composure_multiplier=1.0, unscored_turns=0),
    "hard": Settings(turn_delta=-4, hint_cost=3, composure_multiplier=0.75, unscored_turns=0),
}


def settings(difficulty: str) -> Settings:
    return SETTINGS.get(difficulty, SETTINGS[DEFAULT])
