from app.engine import difficulty
from app.models.case import CaseFile
from app.models.public import Accusation, Progress, ScoreBreakdown

CULPRIT_POINTS = 50
MOTIVE_POINTS = 25
EVIDENCE_POINTS = 5
MAX_EVIDENCE = 3
MAX_TURN_POINTS = 10

RANKS = [(90, "Legendary Detective"), (70, "Chief Inspector"), (40, "Inspector"), (0, "Rookie")]


def rank_for(total: int) -> str:
    return next(name for threshold, name in RANKS if total >= threshold)


def is_valid_evidence(case: CaseFile, progress: Progress, clue_id: str) -> bool:
    """Evidence counts if the player found it and it genuinely implicates the culprit."""
    if clue_id not in progress.revealed_clues:
        return False
    if clue_id in case.solution.required_evidence:
        return True
    clue = case.clue(clue_id)
    return not clue.is_red_herring and case.culprit in clue.points_to


def score(case: CaseFile, progress: Progress, accusation: Accusation) -> ScoreBreakdown:
    culprit_correct = accusation.suspect_id == case.culprit
    motive_correct = culprit_correct and accusation.motive_id in case.solution.acceptable_motives
    valid = [c for c in dict.fromkeys(accusation.evidence) if is_valid_evidence(case, progress, c)][:MAX_EVIDENCE]
    # Evidence and spare turns only count when the right person is named.
    evidence_points = EVIDENCE_POINTS * len(valid) if culprit_correct else 0
    # Turns an easier level adds earn nothing, so Easy can't outscore Normal on spare turns.
    spare = max(0, progress.turns_left - difficulty.settings(progress.difficulty).unscored_turns)
    turn_points = min(spare, MAX_TURN_POINTS) if culprit_correct else 0
    culprit_points = CULPRIT_POINTS if culprit_correct else 0
    motive_points = MOTIVE_POINTS if motive_correct else 0
    total = culprit_points + motive_points + evidence_points + turn_points
    return ScoreBreakdown(
        culprit_correct=culprit_correct,
        motive_correct=motive_correct,
        valid_evidence=valid,
        culprit_points=culprit_points,
        motive_points=motive_points,
        evidence_points=evidence_points,
        turn_points=turn_points,
        total=total,
        rank=rank_for(total),
    )
