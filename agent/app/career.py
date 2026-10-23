"""A player's detective career, derived from their stored games (identity is the anonymous session).

Career titles follow the British police ladder by cases solved. They are deliberately different words from the
per-case score ranks (Rookie ... Legendary Detective), so the two never get confused.
"""

from datetime import date, timedelta

from app.analytics import GameRecord
from app.engine.scoring import RANKS

TITLES = [
    (0, "Constable"),
    (1, "Detective Constable"),
    (3, "Detective Sergeant"),
    (6, "Detective Inspector"),
    (10, "Detective Chief Inspector"),
    (20, "Detective Superintendent"),
    (35, "Commissioner"),
]
CASEBOOK_SIZE = 20
_RANK_ORDER = {name: i for i, (_, name) in enumerate(reversed(RANKS))}  # Rookie=0 ... Legendary Detective=3


def title_for(solved: int) -> str:
    return next(name for threshold, name in reversed(TITLES) if solved >= threshold)


def next_title(solved: int) -> tuple[str, int] | None:
    """The next title and how many more solves it takes, or None at the top."""
    for threshold, name in TITLES:
        if threshold > solved:
            return name, threshold - solved
    return None


def promotion(solved_before: int, solved_now: bool) -> str | None:
    """The new title if solving this case earns one."""
    if not solved_now:
        return None
    before, after = title_for(solved_before), title_for(solved_before + 1)
    return after if after != before else None


def _runs(flags: list[bool]) -> tuple[int, int]:
    """(current trailing run of True, best run of True)."""
    best = current = 0
    for flag in flags:
        current = current + 1 if flag else 0
        best = max(best, current)
    return current, best


def _daily_streaks(days: set[date], today: date) -> tuple[int, int]:
    best = 0
    for day in days:
        if day - timedelta(days=1) not in days:  # start of a run
            length = 1
            while day + timedelta(days=length) in days:
                length += 1
            best = max(best, length)
    # The current streak survives until today's case is missed: count back from today, or from yesterday.
    anchor = today if today in days else today - timedelta(days=1)
    current = 0
    while anchor - timedelta(days=current) in days:
        current += 1
    return current, best


def summarize(records: list[GameRecord], today: date) -> dict:
    closed = sorted((r for r in records if r.ended), key=lambda r: r.updated_at)
    solved_flags = [r.progress.score.culprit_correct for r in closed]  # type: ignore[union-attr]
    solved = sum(solved_flags)
    current_streak, best_streak = _runs(solved_flags)
    daily_days = {date.fromisoformat(r.progress.daily_date) for r in closed if r.progress.daily_date}
    daily_current, daily_best = _daily_streaks(daily_days, today)
    upcoming = next_title(solved)

    by_level = {}
    for level in ("easy", "normal", "hard"):
        group = [r for r in closed if r.progress.difficulty == level]
        if group:
            by_level[level] = {
                "closed": len(group),
                "solved": sum(r.progress.score.culprit_correct for r in group),  # type: ignore[union-attr]
            }

    best = max(closed, key=lambda r: r.progress.score.total, default=None)  # type: ignore[union-attr]
    return {
        "title": title_for(solved),
        "next": {"title": upcoming[0], "solvesNeeded": upcoming[1]} if upcoming else None,
        "closed": len(closed),
        "solved": solved,
        "solveRate": round(solved / len(closed), 3) if closed else None,
        "bestScore": best.progress.score.total if best else None,  # type: ignore[union-attr]
        "bestRank": max(
            (r.progress.score.rank for r in closed),  # type: ignore[union-attr]
            key=lambda rank: _RANK_ORDER.get(rank, -1),
            default=None,
        ),
        "hintsUsed": sum(len(r.progress.hints) for r in closed),
        "streak": {"current": current_streak, "best": best_streak},
        "dailyStreak": {"current": daily_current, "best": daily_best, "playedToday": today in daily_days},
        "byDifficulty": by_level,
        "casebook": [
            {
                "title": r.case.setting.title,
                "closedOn": r.updated_at.date().isoformat(),
                "difficulty": r.progress.difficulty,
                "daily": r.progress.daily_date is not None,
                "solved": r.progress.score.culprit_correct,  # type: ignore[union-attr]
                "score": r.progress.score.total,  # type: ignore[union-attr]
                "rank": r.progress.score.rank,  # type: ignore[union-attr]
            }
            for r in reversed(closed[-CASEBOOK_SIZE:])
        ],
    }
