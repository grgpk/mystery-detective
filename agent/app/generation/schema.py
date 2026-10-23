"""The shape Claude writes when generating a case, and conversion to/from the engine's CaseFile.

Kept flat, fully required and free of nullable fields (an empty string means "none") so its structured-output
grammar stays small enough to compile; the engine's richer model (discriminated unions, defaults) is rebuilt from it.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models.case import CaseFile


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GLocation(_Strict):
    id: str
    label: str
    description: str


class GSetting(_Strict):
    title: str
    place: str
    era_note: str
    locations: list[GLocation]


class GVictim(_Strict):
    name: str
    cause_of_death: str
    time_of_death: str
    crime_scene: str


class GOption(_Strict):
    id: str
    label: str


class GMotive(_Strict):
    id: str
    text: str


class GTimelineEvent(_Strict):
    time: str
    suspect: str
    event: str
    location: str


class GClaim(_Strict):
    time: str
    event: str


class GSecret(_Strict):
    id: str
    text: str
    confession: str
    reveal_at_composure: int


class GLie(_Strict):
    id: str
    text: str
    statement: str
    topics: list[str]
    contradicted_by: list[str]


class GSuspect(_Strict):
    id: str
    name: str
    role: str
    personality: str
    appearance: str
    alibi_claim: str
    claimed_timeline: list[GClaim]
    knows: list[str]
    motive_hint: str
    secrets: list[GSecret]
    lies: list[GLie]


class GClue(_Strict):
    id: str
    title: str
    text: str
    location: str
    unlock_type: Literal["examine", "interrogate", "confront"]
    unlock_location: str
    unlock_suspect: str
    unlock_topic: str
    points_to: list[str]
    is_red_herring: bool
    event_time: str
    event_suspect: str
    event_text: str


class GContradiction(_Strict):
    lie_id: str
    evidence_id: str
    suspect: str
    composure_change: int
    reveals: str


class GTopic(_Strict):
    id: str
    label: str
    keywords: list[str]


class GSolution(_Strict):
    required_evidence: list[str]
    acceptable_motives: list[str]


class GeneratedCase(_Strict):
    setting: GSetting
    victim: GVictim
    briefing: str
    culprit: str
    motive: GMotive
    motive_options: list[GOption]
    truth_timeline: list[GTimelineEvent]
    suspects: list[GSuspect]
    clues: list[GClue]
    contradictions: list[GContradiction]
    topics: list[GTopic]
    solution: GSolution


def _unlock(clue: GClue) -> dict:
    match clue.unlock_type:
        case "examine":
            return {"type": "examine", "target": clue.unlock_location or clue.location or ""}
        case "interrogate":
            return {"type": "interrogate", "suspect": clue.unlock_suspect or "", "topic": clue.unlock_topic or ""}
        case "confront":
            return {"type": "confront"}


def to_case_file(generated: GeneratedCase, case_id: str, max_turns: int = 15) -> CaseFile:
    g = generated
    return CaseFile.model_validate(
        {
            "case_id": case_id,
            "setting": g.setting.model_dump(),
            "victim": g.victim.model_dump(),
            "briefing": g.briefing,
            "culprit": g.culprit,
            "motive": g.motive.model_dump(),
            "motive_options": [o.model_dump() for o in g.motive_options],
            "truth_timeline": [e.model_dump() for e in g.truth_timeline],
            "suspects": [{**s.model_dump(), "starting_composure": 100} for s in g.suspects],
            "clues": [
                {
                    "id": c.id,
                    "title": c.title,
                    "text": c.text,
                    "location": c.location or None,
                    "unlock": _unlock(c),
                    "points_to": c.points_to,
                    "is_red_herring": c.is_red_herring,
                    "timeline_event": (
                        {"time": c.event_time, "suspect": c.event_suspect, "event": c.event_text}
                        if c.event_text
                        else None
                    ),
                }
                for c in g.clues
            ],
            "contradictions": [
                {
                    "a": c.lie_id,
                    "b": c.evidence_id,
                    "effect": {"suspect": c.suspect, "composure": c.composure_change, "reveals": c.reveals or None},
                }
                for c in g.contradictions
            ],
            "topics": [t.model_dump() for t in g.topics],
            "solution": g.solution.model_dump(),
            "max_turns": max_turns,
        }
    )


def from_case_file(case: CaseFile) -> GeneratedCase:
    """The inverse, used to show Claude a worked example in the generation format."""
    data = case.model_dump()
    clues = []
    for clue in case.clues:
        unlock = clue.unlock.model_dump()
        event = clue.timeline_event
        clues.append(
            {
                "id": clue.id,
                "title": clue.title,
                "text": clue.text,
                "location": clue.location or "",
                "unlock_type": unlock["type"],
                "unlock_location": unlock.get("target", ""),
                "unlock_suspect": unlock.get("suspect", ""),
                "unlock_topic": unlock.get("topic", ""),
                "points_to": clue.points_to,
                "is_red_herring": clue.is_red_herring,
                "event_time": event.time if event else "",
                "event_suspect": event.suspect if event else "",
                "event_text": event.event if event else "",
            }
        )
    return GeneratedCase.model_validate(
        {
            "setting": data["setting"],
            "victim": data["victim"],
            "briefing": data["briefing"],
            "culprit": data["culprit"],
            "motive": data["motive"],
            "motive_options": data["motive_options"],
            "truth_timeline": [{**e, "location": e["location"] or ""} for e in data["truth_timeline"]],
            "suspects": [{k: v for k, v in s.items() if k != "starting_composure"} for s in data["suspects"]],
            "clues": clues,
            "contradictions": [
                {
                    "lie_id": c.a,
                    "evidence_id": c.b,
                    "suspect": c.effect.suspect,
                    "composure_change": c.effect.composure,
                    "reveals": c.effect.reveals or "",
                }
                for c in case.contradictions
            ],
            "topics": data["topics"],
            "solution": data["solution"],
        }
    )
