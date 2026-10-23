"""The daily case: one shared case per UTC day, one scored attempt per player, and a leaderboard.

The leaderboard is derived from stored games (no separate score table), ranked by score, then fewer turns,
then less time.
"""

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime

from app.agents.moderation import normalize, refusal_for
from app.analytics import GameRecord

ANONYMOUS = "Anonymous Inspector"
LEADERBOARD_SIZE = 20
_NAME = re.compile(r"^[\w .'\-]{2,24}$")


def today() -> date:
    return datetime.now(UTC).date()


@dataclass
class DailyGame:
    thread_id: str
    owner: str
    record: GameRecord


@dataclass
class Entry:
    rank: int
    name: str
    score: int
    turns: int
    minutes: float
    owner: str
    thread_id: str

    def public(self) -> dict:
        return {"rank": self.rank, "name": self.name, "score": self.score, "turns": self.turns, "minutes": self.minutes}


def clean_name(raw: str) -> tuple[str | None, str | None]:
    """(name, None) if acceptable, else (None, reason)."""
    name = " ".join(normalize(raw).split())
    if not _NAME.match(name):
        return None, "A leaderboard name needs 2-24 letters, numbers, spaces or . ' -"
    if refusal_for(name):
        return None, "The Yard won't print that name on the leaderboard. Try another."
    return name, None


def leaderboard(games: list[DailyGame]) -> list[Entry]:
    finished = [g for g in games if g.record.ended]
    finished.sort(
        key=lambda g: (
            -g.record.progress.score.total,  # type: ignore[union-attr]
            g.record.turns_used,
            g.record.updated_at - g.record.created_at,
        )
    )
    return [
        Entry(
            rank=i + 1,
            name=g.record.progress.leaderboard_name or ANONYMOUS,
            score=g.record.progress.score.total,  # type: ignore[union-attr]
            turns=g.record.turns_used,
            minutes=round((g.record.updated_at - g.record.created_at).total_seconds() / 60, 1),
            owner=g.owner,
            thread_id=g.thread_id,
        )
        for i, g in enumerate(finished)
    ]
