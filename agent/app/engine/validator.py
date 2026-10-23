"""Fair-play checks run on every case file before it is played (plan section 6)."""

import math
import re
from collections import Counter

from pydantic import ValidationError

from app.engine import solver
from app.engine.clue_engine import IMPLICIT_FIRST_TOPIC, QUESTIONS_PER_TURN
from app.models.case import CaseFile, ConfrontUnlock, ExamineUnlock, InterrogateUnlock

BUDGET_RATIO = 0.6
_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _minutes(hhmm: str) -> int:
    hours, minutes = hhmm.strip().split(":")
    return int(hours) * 60 + int(minutes)


def parse_case(raw: dict) -> tuple[CaseFile | None, list[str]]:
    """Rule 1: schema check."""
    try:
        return CaseFile.model_validate(raw), []
    except ValidationError as exc:
        return None, [f"schema: {err['loc']}: {err['msg']}" for err in exc.errors()]


def _referential_errors(case: CaseFile) -> list[str]:
    errors = []
    suspect_ids = {s.id for s in case.suspects}
    clue_ids = {c.id for c in case.clues}
    lie_ids = {lie.id for s in case.suspects for lie in s.lies}
    topic_ids = {t.id for t in case.topics}
    if case.culprit not in suspect_ids:
        errors.append(f"culprit {case.culprit} is not a suspect")
    if case.victim.crime_scene not in case.location_ids():
        errors.append("crime scene is not a location")
    for c in case.contradictions:
        for ref in (c.a, c.b):
            if ref not in clue_ids | lie_ids:
                errors.append(f"contradiction refers to unknown id {ref}")
        if c.effect.reveals and c.effect.reveals not in clue_ids:
            errors.append(f"contradiction reveals unknown clue {c.effect.reveals}")
    for s in case.suspects:
        for lie in s.lies:
            for topic in lie.topics:
                if topic not in topic_ids:
                    errors.append(f"lie {lie.id} uses unknown topic {topic}")
    for motive in case.solution.acceptable_motives:
        if motive not in {m.id for m in case.motive_options}:
            errors.append(f"acceptable motive {motive} is not offered to the player")
    if len(case.suspects) < 3:
        errors.append("need at least 3 suspects")
    return errors


def _integrity_errors(case: CaseFile) -> list[str]:
    """Ids are unique and every reference anywhere resolves (generated cases get this wrong most often)."""
    errors = []
    suspect_ids = {s.id for s in case.suspects}
    location_ids = case.location_ids()
    topic_ids = {t.id for t in case.topics}

    def unique(kind: str, ids: list[str]) -> None:
        for dup in sorted({i for i in ids if ids.count(i) > 1}):
            errors.append(f"duplicate {kind} id {dup}")

    unique("suspect", [s.id for s in case.suspects])
    unique("clue", [c.id for c in case.clues])
    unique("location", [loc.id for loc in case.setting.locations])
    unique("topic", [t.id for t in case.topics])
    unique("lie/secret", [x.id for s in case.suspects for x in (*s.lies, *s.secrets)])
    if IMPLICIT_FIRST_TOPIC not in topic_ids:
        errors.append(f"topics must include '{IMPLICIT_FIRST_TOPIC}'")

    for clue in case.clues:
        unlock = clue.unlock
        if clue.location is not None and clue.location not in location_ids:
            errors.append(f"clue {clue.id} is at unknown location {clue.location}")
        if isinstance(unlock, ExamineUnlock) and unlock.target not in location_ids:
            errors.append(f"clue {clue.id} unlocks at unknown location {unlock.target}")
        if isinstance(unlock, InterrogateUnlock) and (
            unlock.suspect not in suspect_ids or unlock.topic not in topic_ids
        ):
            errors.append(f"clue {clue.id} unlocks via unknown suspect {unlock.suspect} or topic {unlock.topic}")
        for s in clue.points_to:
            if s not in suspect_ids:
                errors.append(f"clue {clue.id} points to unknown suspect {s}")
        if clue.is_red_herring and case.culprit in clue.points_to:
            errors.append(f"red herring {clue.id} points at the culprit")
        if clue.timeline_event and (
            clue.timeline_event.suspect not in suspect_ids or not _HHMM.match(clue.timeline_event.time)
        ):
            errors.append(f"clue {clue.id} has a bad timeline event")

    for event in case.truth_timeline:
        if event.suspect not in suspect_ids or not _HHMM.match(event.time):
            errors.append(f"truth timeline event at {event.time} has a bad suspect or time")
        if event.location is not None and event.location not in location_ids:
            errors.append(f"truth timeline event at {event.time} is at unknown location {event.location}")
    window = case.victim.time_of_death.split("-")
    if len(window) != 2 or not all(_HHMM.match(t) for t in window):
        errors.append("time of death must look like HH:MM-HH:MM")

    for c in case.contradictions:
        if c.effect.suspect not in suspect_ids:
            errors.append(f"contradiction {c.a}/{c.b} affects unknown suspect {c.effect.suspect}")
        elif c.effect.composure >= 0:
            errors.append(f"contradiction {c.a}/{c.b} must lower composure")
        for ref in (c.a, c.b):
            owner = case.lie(ref)
            if owner and owner[0].id != c.effect.suspect:
                errors.append(f"contradiction {c.a}/{c.b} must affect {owner[0].id}, who told lie {ref}")
    for s in case.suspects:
        if not s.secrets:
            errors.append(f"suspect {s.id} has no secret")
        for lie in s.lies:
            if not lie.topics:
                errors.append(f"lie {lie.id} has no topics, so it can never be told")
        for claim in s.claimed_timeline:
            if not _HHMM.match(claim.time):
                errors.append(f"suspect {s.id} has a bad claimed time {claim.time}")
    examinable = {c.unlock.target for c in case.clues if isinstance(c.unlock, ExamineUnlock)}
    for loc in sorted(location_ids - examinable):
        errors.append(f"location {loc} has nothing to find")
    return errors


def _reachability_errors(case: CaseFile) -> list[str]:
    """Rule 2: every required clue has a trigger that refers to something real."""
    errors = []
    suspect_ids = {s.id for s in case.suspects}
    revealed_by_contradiction = {c.effect.reveals for c in case.contradictions if c.effect.reveals}
    topic_ids = {t.id for t in case.topics}
    for clue_id in case.solution.required_evidence:
        try:
            clue = case.clue(clue_id)
        except StopIteration:
            errors.append(f"required evidence {clue_id} does not exist")
            continue
        unlock = clue.unlock
        if isinstance(unlock, ExamineUnlock) and unlock.target not in case.location_ids():
            errors.append(f"{clue_id} unlocks at unknown location {unlock.target}")
        elif isinstance(unlock, InterrogateUnlock) and (
            unlock.suspect not in suspect_ids or unlock.topic not in topic_ids
        ):
            errors.append(f"{clue_id} unlocks via unknown suspect/topic")
        elif isinstance(unlock, ConfrontUnlock) and clue_id not in revealed_by_contradiction:
            errors.append(f"{clue_id} is confront-only but no contradiction reveals it")
    return errors


def _coverage_errors(case: CaseFile) -> list[str]:
    """Rule 3: every culprit lie is breakable."""
    covered = {c.a for c in case.contradictions} | {c.b for c in case.contradictions}
    return [
        f"culprit lie {lie.id} has no contradiction" for lie in case.suspect(case.culprit).lies if lie.id not in covered
    ]


def _pointing_errors(case: CaseFile) -> list[str]:
    """Rules 4 and 5: the culprit is the most strongly indicated suspect."""
    counts = Counter(s for c in case.clues if not c.is_red_herring for s in c.points_to)
    culprit_count = counts[case.culprit]
    errors = []
    if culprit_count < 3:
        errors.append(f"only {culprit_count} non-herring clues point to the culprit (need 3)")
    for suspect_id, count in counts.items():
        if suspect_id != case.culprit and count >= culprit_count:
            errors.append(f"innocent {suspect_id} has {count} non-herring clues, culprit has {culprit_count}")
    return errors


def _timeline_errors(case: CaseFile) -> list[str]:
    """Rule 6: the culprit is at the scene during the time-of-death window."""
    start, end = (_minutes(t) for t in case.victim.time_of_death.split("-"))
    day = 24 * 60

    def in_window(hhmm: str) -> bool:
        # Windows may cross midnight (e.g. 23:30-00:15): measure everything from the window's start.
        return (_minutes(hhmm) - start) % day <= (end - start) % day

    at_scene = [
        e
        for e in case.truth_timeline
        if e.suspect == case.culprit and e.location == case.victim.crime_scene and in_window(e.time)
    ]
    return [] if at_scene else ["culprit is never at the crime scene inside the time-of-death window"]


def minimum_actions(case: CaseFile) -> int:
    """A lower bound on the turns needed to reveal every required clue."""
    examine_locations: set[str] = set()
    questions: dict[str, set[str]] = {}
    confronts = 0

    def need_clue(clue_id: str, depth: int = 0) -> None:
        nonlocal confronts
        if depth > 5:
            return
        clue = next((c for c in case.clues if c.id == clue_id), None)
        if clue is None:
            return
        unlock = clue.unlock
        if isinstance(unlock, ExamineUnlock):
            examine_locations.add(unlock.target)
        elif isinstance(unlock, InterrogateUnlock):
            questions.setdefault(unlock.suspect, set()).add(unlock.topic)
        else:
            # Cheapest contradiction that reveals it: one confront plus both of its ingredients.
            entry = next((c for c in case.contradictions if c.effect.reveals == clue_id), None)
            if entry is None:
                return
            confronts += 1
            for ref in (entry.a, entry.b):
                lie = case.lie(ref)
                if lie:
                    suspect, the_lie = lie
                    if IMPLICIT_FIRST_TOPIC not in the_lie.topics:
                        questions.setdefault(suspect.id, set()).add(the_lie.topics[0])
                    else:
                        questions.setdefault(suspect.id, set())
                else:
                    need_clue(ref, depth + 1)

    for clue_id in case.solution.required_evidence:
        need_clue(clue_id)
    interrogation_turns = sum(max(1, math.ceil(len(topics) / QUESTIONS_PER_TURN)) for topics in questions.values())
    return len(examine_locations) + interrogation_turns + confronts


def _budget_errors(case: CaseFile) -> list[str]:
    """Rule 7: the required evidence is findable with room to spare."""
    needed = minimum_actions(case)
    budget = math.floor(case.max_turns * BUDGET_RATIO)
    return [] if needed <= budget else [f"needs {needed} actions, budget is {budget}"]


def _simulation_errors(case: CaseFile) -> list[str]:
    """Rule 8: play it. The required evidence is reachable through the real engine within budget, and every
    contradiction can actually be set off by a player."""
    errors = []
    try:
        progress = solver.solve(case)
        used = case.max_turns - progress.turns_left
        budget = math.floor(case.max_turns * BUDGET_RATIO)
        if used > budget:
            errors.append(f"simulated solve used {used} turns, budget is {budget}")
    except solver.Unsolvable as err:
        errors.append(f"simulated solve failed: {err}")
    for index in range(len(case.contradictions)):
        try:
            solver.trigger_contradiction(case, index)
        except solver.Unsolvable as err:
            errors.append(str(err))
    return errors


def validate_case(case: CaseFile) -> list[str]:
    errors = _referential_errors(case) + _integrity_errors(case)
    if errors:
        return errors  # later rules assume ids resolve
    for rule in (_reachability_errors, _coverage_errors, _pointing_errors, _timeline_errors, _budget_errors):
        errors.extend(rule(case))
    if not errors:
        errors.extend(_simulation_errors(case))  # only meaningful once the structure is sound
    return errors
