"""Server-side progress (private) and the public state projected to the browser."""

from typing import Literal

from pydantic import Field

from .base import CamelModel

Phase = Literal["briefing", "investigating", "accusing", "ended"]
Mood = Literal["calm", "guarded", "nervous", "cracking"]
StatementKind = Literal["alibi", "claim", "testimony", "confession"]


class Statement(CamelModel):
    id: str
    suspect: str
    text: str
    kind: StatementKind
    lie_id: str | None = None  # hidden: stripped by projection


class BoardLink(CamelModel):
    from_: str = Field(alias="from")
    to: str


class Board(CamelModel):
    pins: list[str] = Field(default_factory=list)
    links: list[BoardLink] = Field(default_factory=list)
    notes: str = ""


class Conversation(CamelModel):
    suspect_id: str
    questions_left: int


class ChatTurn(CamelModel):
    role: Literal["user", "assistant"]
    content: str


class Accusation(CamelModel):
    suspect_id: str
    motive_id: str
    evidence: list[str] = Field(default_factory=list, max_length=3)


class ScoreBreakdown(CamelModel):
    culprit_correct: bool
    motive_correct: bool
    valid_evidence: list[str]
    culprit_points: int
    motive_points: int
    evidence_points: int
    turn_points: int
    total: int
    rank: str


class Progress(CamelModel):
    phase: Phase = "briefing"
    difficulty: Literal["easy", "normal", "hard"] = "normal"
    max_turns: int | None = None  # the turn budget at this difficulty (None on games saved before levels)
    turns_left: int
    revealed_clues: list[str] = Field(default_factory=list)
    new_clues: list[str] = Field(default_factory=list)
    statements: list[Statement] = Field(default_factory=list)
    composure: dict[str, int]
    revealed_secrets: list[str] = Field(default_factory=list)
    examined_locations: list[str] = Field(default_factory=list)
    interrogated: list[str] = Field(default_factory=list)
    conversation: Conversation | None = None
    asked_topics: dict[str, list[str]] = Field(default_factory=dict)
    histories: dict[str, list[ChatTurn]] = Field(default_factory=dict)
    board: Board = Field(default_factory=Board)
    contradictions_found: list[int] = Field(default_factory=list)
    hints: list[str] = Field(default_factory=list)  # step keys hinted, to escalate repeat hints
    daily_date: str | None = None  # ISO date when this is that day's shared case
    leaderboard_name: str | None = None
    last_contradiction: BoardLink | None = None
    accusation: Accusation | None = None
    score: ScoreBreakdown | None = None
    ui_seq: int = 0  # monotonically increasing id for A2UI surfaces / tool calls


# ---- public projection ----------------------------------------------------


class PublicSuspect(CamelModel):
    id: str
    name: str
    role: str
    appearance: str
    composure: int
    mood: Mood


class PublicLocation(CamelModel):
    id: str
    label: str
    description: str
    examined: bool


class PublicClue(CamelModel):
    id: str
    title: str
    text: str
    location: str | None
    is_new: bool


class PublicStatement(CamelModel):
    id: str
    suspect: str
    text: str
    kind: StatementKind


class PublicTimelineEvent(CamelModel):
    time: str
    suspect: str
    event: str
    source: Literal["claimed", "verified"]


class PublicVictim(CamelModel):
    name: str
    cause_of_death: str
    time_of_death: str
    crime_scene: str


class Option(CamelModel):
    id: str
    label: str


class Verdict(CamelModel):
    score: ScoreBreakdown
    culprit_name: str
    motive: str
    true_timeline: list[PublicTimelineEvent]
    found_clues: list[str]
    missed_clues: list[PublicClue]


class DailyInfo(CamelModel):
    date: str
    leaderboard_name: str | None


class PublicState(CamelModel):
    case_id: str
    difficulty: Literal["easy", "normal", "hard"]
    hint_cost: int
    title: str
    place: str
    briefing: str
    phase: Phase
    turns_left: int
    max_turns: int
    victim: PublicVictim
    suspects: list[PublicSuspect]
    locations: list[PublicLocation]
    topics: list[Option]
    motive_options: list[Option]
    clues: list[PublicClue]
    statements: list[PublicStatement]
    timeline: list[PublicTimelineEvent]
    conversation: Conversation | None
    board: Board
    last_contradiction: BoardLink | None
    verdict: Verdict | None = None
    daily: DailyInfo | None = None
