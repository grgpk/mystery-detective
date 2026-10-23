"""Game analytics, computed from stored sessions (plan section 1 success metrics, section 12 playtest data).

Every game's full progress is already persisted, so these are derived on demand rather than logged as events.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.models.case import GENERATED_PREFIX, CaseFile
from app.models.public import Progress

ABANDONED_AFTER = timedelta(hours=1)  # a begun, unfinished game idle this long counts as abandoned

TARGETS = {
    "accusation_rate": (0.70, None),  # at least 70% of begun games reach an accusation
    "solve_rate": (0.40, 0.70),  # between 40% and 70%: lower is unfair, higher is too easy
}


@dataclass
class GameRecord:
    case: CaseFile
    progress: Progress
    created_at: datetime
    updated_at: datetime

    @property
    def begun(self) -> bool:
        return self.progress.phase != "briefing"

    @property
    def ended(self) -> bool:
        return self.progress.phase == "ended" and self.progress.score is not None

    @property
    def turns_used(self) -> int:
        return self.case.max_turns - self.progress.turns_left


def _rate(part: int, whole: int) -> float | None:
    return round(part / whole, 3) if whole else None


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


def _stall_reason(record: GameRecord) -> str:
    """Where an abandoned game got stuck, by the furthest thing the player managed."""
    progress, case = record.progress, record.case
    found_key = len(set(case.solution.required_evidence) & set(progress.revealed_clues))
    if not progress.interrogated and not progress.examined_locations:
        return "never acted"
    if not progress.examined_locations:
        return "never searched a room"
    if not progress.interrogated:
        return "never questioned anyone"
    if not progress.contradictions_found:
        return f"never broke a lie ({found_key}/{len(case.solution.required_evidence)} key evidence)"
    return f"broke a lie but did not accuse ({found_key}/{len(case.solution.required_evidence)} key evidence)"


def summarize(records: list[GameRecord], now: datetime) -> dict:
    begun = [r for r in records if r.begun]
    ended = [r for r in begun if r.ended]
    solved = [r for r in ended if r.progress.score.culprit_correct]  # type: ignore[union-attr]
    abandoned = [r for r in begun if not r.ended and now - r.updated_at >= ABANDONED_AFTER]

    metrics = {
        "accusation_rate": _rate(len(ended), len(begun)),
        "solve_rate": _rate(len(solved), len(ended)),
    }
    per_case: dict[str, dict] = defaultdict(
        lambda: {"title": "", "generated": False, "opened": 0, "begun": 0, "accused": 0, "solved": 0, "scores": []}
    )
    for r in records:
        row = per_case[r.case.case_id]
        row["title"] = r.case.setting.title
        row["generated"] = r.case.case_id.startswith(GENERATED_PREFIX)
        row["opened"] += 1
        row["begun"] += r.begun
        if r.ended:
            row["accused"] += 1
            row["solved"] += r.progress.score.culprit_correct  # type: ignore[union-attr]
            row["scores"].append(r.progress.score.total)  # type: ignore[union-attr]

    return {
        "games": {
            "opened": len(records),
            "begun": len(begun),
            "accused": len(ended),
            "solved": len(solved),
            "abandoned": len(abandoned),
        },
        "metrics": metrics,
        "targets": {
            name: {
                "value": metrics[name],
                "min": low,
                "max": high,
                "met": None
                if metrics[name] is None
                else (low is None or metrics[name] >= low) and (high is None or metrics[name] <= high),
            }
            for name, (low, high) in TARGETS.items()
        },
        "accused_games": {
            "avg_turns_used": _mean([r.turns_used for r in ended]),
            "avg_hints": _mean([len(r.progress.hints) for r in ended]),
            "avg_minutes_to_accuse": _mean([(r.updated_at - r.created_at).total_seconds() / 60 for r in ended]),
            "avg_score": _mean([r.progress.score.total for r in ended]),  # type: ignore[union-attr]
            "ranks": dict(Counter(r.progress.score.rank for r in ended)),  # type: ignore[union-attr]
        },
        "stalls": dict(Counter(_stall_reason(r) for r in abandoned).most_common()),
        "cases": sorted(
            (
                {
                    "caseId": case_id,
                    "title": row["title"],
                    "generated": row["generated"],
                    "opened": row["opened"],
                    "begun": row["begun"],
                    "accused": row["accused"],
                    "solveRate": _rate(row["solved"], row["accused"]),
                    "avgScore": _mean(row["scores"]),
                }
                for case_id, row in per_case.items()
            ),
            key=lambda c: -c["opened"],
        ),
    }
