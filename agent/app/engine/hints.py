"""Hints: the next missing step on the way to the key evidence, chosen by code from what the player has found.

Wording escalates: the first hint about a step is a nudge, asking again about the same step names it outright.
"""

from dataclasses import dataclass
from typing import Literal

from app.engine import difficulty
from app.engine.clue_engine import GameRuleError, Outcome, require_investigating, spend
from app.models.case import CaseFile, ExamineUnlock, InterrogateUnlock, Topic
from app.models.public import Progress
from app.themes import theme

HINT_COST = 2  # at Normal; see engine/difficulty.py

StepKind = Literal["examine", "ask", "confront", "accuse"]


@dataclass(frozen=True)
class Step:
    kind: StepKind
    location: str | None = None
    suspect: str | None = None
    topic: str | None = None
    lie: str | None = None
    evidence: str | None = None

    @property
    def key(self) -> str:
        return ":".join(str(v) for v in (self.kind, self.location, self.suspect, self.topic, self.lie, self.evidence))


def _stated(progress: Progress, lie_id: str) -> bool:
    return any(s.lie_id == lie_id for s in progress.statements)


def _step_for_clue(case: CaseFile, progress: Progress, clue_id: str, depth: int = 0) -> Step | None:
    if clue_id in progress.revealed_clues or depth > 6:
        return None
    unlock = case.clue(clue_id).unlock
    if isinstance(unlock, ExamineUnlock):
        return Step("examine", location=unlock.target)
    if isinstance(unlock, InterrogateUnlock):
        return Step("ask", suspect=unlock.suspect, topic=unlock.topic)
    # Confront-only: the cheapest contradiction that reveals it (fewest ingredients still missing).
    candidates = [c for c in case.contradictions if c.effect.reveals == clue_id]

    def missing(entry) -> int:
        return sum(
            0 if (case.lie(ref) and _stated(progress, ref)) or ref in progress.revealed_clues else 1
            for ref in (entry.a, entry.b)
        )

    for entry in sorted(candidates, key=missing):
        lie_ref, evidence_ref = (entry.a, entry.b) if case.lie(entry.a) else (entry.b, entry.a)
        found = case.lie(lie_ref)
        if found and not _stated(progress, lie_ref):
            suspect, lie = found
            return Step("ask", suspect=suspect.id, topic=lie.topics[0])
        if evidence_ref not in progress.revealed_clues:
            step = _step_for_clue(case, progress, evidence_ref, depth + 1)
            if step:
                return step
            continue
        return Step("confront", suspect=entry.effect.suspect, lie=lie_ref, evidence=evidence_ref)
    return None


def next_step(case: CaseFile, progress: Progress) -> Step:
    for clue_id in case.solution.required_evidence:
        step = _step_for_clue(case, progress, clue_id)
        if step:
            return step
    return Step("accuse")


def _topic_phrase(topic: Topic) -> str:
    return f'"{topic.label}"' if topic.label.endswith("?") else topic.label.lower()


def hint_text(case: CaseFile, step: Step, explicit: bool) -> str:
    """The sergeant's line. `explicit` is used when this exact step has been hinted before."""
    name = case.suspect(step.suspect).name if step.suspect else ""
    match step.kind:
        case "examine":
            label = next(loc.label for loc in case.setting.locations if loc.id == step.location)
            place = "the " + label[4:] if label.startswith("The ") else label  # mid-sentence "the Guest Wing"
            if explicit:
                return f"Search {place}, Inspector. I'd stake my pension there's something in it."
            return f"I keep thinking about {place}. Has anyone given it a proper going-over?"
        case "ask":
            topic = next(t for t in case.topics if t.id == step.topic)
            if explicit:
                return f"Ask {name} about {_topic_phrase(topic)}. Straight out."
            return f"{name} knows more than they've told us. Steer them toward {_topic_phrase(topic)}."
        case "confront":
            lie = case.lie(step.lie)[1]  # type: ignore[index]
            if explicit:
                clue = case.clue(step.evidence)
                return f'Confront {name}: put their words, "{lie.statement}", beside the {clue.title.lower()}.'
            return f"Something {name} told us doesn't sit right with what we've found. Lay the two side by side."
        case "accuse":
            if explicit:
                return (
                    f"We have enough, Inspector. Make the arrest before {theme(case.theme).authority} does it for us."
                )
            return "I'd say the evidence is all in front of you. It may be time to name the killer."


def take_hint(case: CaseFile, progress: Progress) -> tuple[str, Outcome]:
    """Spends HINT_COST turns for the next step. Never spends the player's last turns."""
    require_investigating(progress)
    cost = difficulty.settings(progress.difficulty).hint_cost
    if progress.turns_left <= cost:
        raise GameRuleError(f"A hint costs {cost} turn{'s' if cost != 1 else ''}, and you can't spare them now.")
    step = next_step(case, progress)
    explicit = step.key in progress.hints
    progress.hints.append(step.key)
    outcome = Outcome()
    spend(progress, outcome, cost)
    progress.conversation = None
    return hint_text(case, step, explicit), outcome
