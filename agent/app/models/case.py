"""Hidden case file. Never leaves the server; see engine/projection.py for what the browser sees."""

from typing import Literal

from pydantic import Field

from .base import CamelModel


class Location(CamelModel):
    id: str
    label: str
    description: str


class Setting(CamelModel):
    title: str
    place: str
    era_note: str = ""
    locations: list[Location]


class Victim(CamelModel):
    name: str
    cause_of_death: str
    time_of_death: str  # "HH:MM-HH:MM"
    crime_scene: str  # location id


class Motive(CamelModel):
    id: str
    text: str


class MotiveOption(CamelModel):
    id: str
    label: str


class TimelineEvent(CamelModel):
    time: str
    suspect: str
    event: str
    location: str | None = None


class ClaimedEvent(CamelModel):
    time: str
    event: str


class Secret(CamelModel):
    id: str
    text: str
    confession: str  # first-person line the suspect says when it comes out
    reveal_at_composure: int


class Lie(CamelModel):
    id: str
    text: str
    statement: str  # first-person quote recorded when the suspect tells this lie
    topics: list[str]
    contradicted_by: list[str] = Field(default_factory=list)


class Suspect(CamelModel):
    id: str
    name: str
    role: str
    personality: str
    appearance: str = ""
    alibi_claim: str
    claimed_timeline: list[ClaimedEvent] = Field(default_factory=list)
    knows: list[str] = Field(default_factory=list)
    motive_hint: str = ""
    secrets: list[Secret] = Field(default_factory=list)
    lies: list[Lie] = Field(default_factory=list)
    starting_composure: int = 100


class ExamineUnlock(CamelModel):
    type: Literal["examine"]
    target: str


class InterrogateUnlock(CamelModel):
    type: Literal["interrogate"]
    suspect: str
    topic: str


class ConfrontUnlock(CamelModel):
    """Only revealed as the `reveals` effect of a contradiction."""

    type: Literal["confront"]


Unlock = ExamineUnlock | InterrogateUnlock | ConfrontUnlock


class Clue(CamelModel):
    id: str
    title: str
    text: str
    location: str | None = None
    unlock: Unlock = Field(discriminator="type")
    points_to: list[str] = Field(default_factory=list)
    is_red_herring: bool = False
    timeline_event: TimelineEvent | None = None


class ContradictionEffect(CamelModel):
    suspect: str
    composure: int
    reveals: str | None = None  # clue id


class Contradiction(CamelModel):
    a: str  # lie id or clue id
    b: str
    effect: ContradictionEffect


class Topic(CamelModel):
    id: str
    label: str
    keywords: list[str]


class Solution(CamelModel):
    required_evidence: list[str]
    acceptable_motives: list[str]


class CaseFile(CamelModel):
    case_id: str
    setting: Setting
    victim: Victim
    briefing: str
    culprit: str
    motive: Motive
    motive_options: list[MotiveOption]
    truth_timeline: list[TimelineEvent]
    suspects: list[Suspect]
    clues: list[Clue]
    contradictions: list[Contradiction]
    topics: list[Topic]
    solution: Solution
    max_turns: int = 15

    def suspect(self, suspect_id: str) -> Suspect:
        return next(s for s in self.suspects if s.id == suspect_id)

    def clue(self, clue_id: str) -> Clue:
        return next(c for c in self.clues if c.id == clue_id)

    def lie(self, lie_id: str) -> tuple[Suspect, Lie] | None:
        for s in self.suspects:
            for lie in s.lies:
                if lie.id == lie_id:
                    return s, lie
        return None

    def location_ids(self) -> set[str]:
        return {loc.id for loc in self.setting.locations}
