"""Scene narration and the judge's closing reveal. Both see only what they are handed."""

from app.models.case import CaseFile
from app.models.public import Accusation, Progress, ScoreBreakdown

NARRATOR_SYSTEM = """You are the NARRATOR of a 1920s fair-play murder mystery, in the dry, observant voice of a \
golden-age detective novel. Write 2-3 sentences of present-tense scene description. Mention ONLY the findings you \
are given; never invent clues, names, or conclusions. PG-13, no gore."""

JUDGE_SYSTEM = """You are the narrator delivering the final chapter of a golden-age whodunit, the moment the \
detective gathers everyone in the drawing room. Write 150-250 words. Reveal the true culprit, motive and method, \
walk through the key moments of the true timeline, credit the evidence the detective actually cited, and name \
the clues the detective missed (if any) as things a \
sharper eye would have caught. If the detective accused the wrong person, be gracious but clear. PG-13, no gore. \
Plain prose, no headings."""


def examine_prompt(case: CaseFile, location_id: str, clue_ids: list[str]) -> str:
    location = next(loc for loc in case.setting.locations if loc.id == location_id)
    findings = "\n".join(f"- {case.clue(c).title}: {case.clue(c).text}" for c in clue_ids)
    return (
        f"Setting: {case.setting.place}. The inspector searches {location.label}: {location.description}\n"
        f"Findings:\n{findings or '- nothing of note'}\n"
        f"Describe the search.\n{location.label}: {location.description}"
    )


def judge_prompt(case: CaseFile, progress: Progress, accusation: Accusation, score: ScoreBreakdown) -> str:
    accused = case.suspect(accusation.suspect_id).name
    motive = next((m.label for m in case.motive_options if m.id == accusation.motive_id), accusation.motive_id)
    timeline = "\n".join(
        f"- {e.time}: {(case.suspect(e.suspect).name if e.suspect in {s.id for s in case.suspects} else e.suspect)} "
        f"{e.event}"
        for e in case.truth_timeline
    )
    found = [case.clue(c).title for c in progress.revealed_clues]
    cited = [case.clue(c).title for c in accusation.evidence]
    missed = [c.title for c in case.clues if c.id not in progress.revealed_clues and not c.is_red_herring]
    return f"""Case: {case.setting.title}, {case.setting.place}
Victim: {case.victim.name}, {case.victim.cause_of_death}
True culprit: {case.suspect(case.culprit).name}
True motive: {case.motive.text}
True timeline:
{timeline}

The detective accused: {accused}, motive "{motive}" ({"correct" if score.culprit_correct else "WRONG"} culprit, \
{"correct" if score.motive_correct else "wrong"} motive).
Evidence the detective cited in the accusation: {", ".join(cited) or "none"}
Other clues the detective found but did not cite: {", ".join(c for c in found if c not in cited) or "none"}
Clues missed: {", ".join(missed) or "none"}
Final rank: {score.rank} ({score.total}/100)"""
