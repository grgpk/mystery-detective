"""Case generator (plan section 5.1): Claude writes a case, the validator judges it, Claude repairs it.

The validator is the authority. A case reaches players only if it passes every fair-play rule, including a
simulated playthrough of the real engine.
"""

import logging
import random
import time
import uuid
from dataclasses import dataclass, field
from functools import cache

import anthropic
from pydantic import ValidationError

from app.engine.case_library import library
from app.engine.validator import validate_case
from app.generation.schema import GeneratedCase, from_case_file, to_case_file
from app.llm import GENERATOR_MODEL, LLM, LLMRefusal, LLMTruncated
from app.models.case import CaseFile

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
MAX_TOKENS = 32000
EXAMPLE_CASE_ID = "ashford_manor"

# Settings the generator is steered toward; the hand-written cases already cover a manor, a train and a hotel.
SETTINGS = [
    "a lighthouse keeper's cottage on a storm-cut Cornish island, 1925",
    "an archaeologists' dig house outside Luxor, 1934",
    "a supra feast in a wine merchant's house in Tbilisi's old town, 1927",
    "a crumbling Venetian palazzo during Carnival, 1929",
    "a transatlantic ocean liner in mid-crossing, 1932",
    "a Highland shooting lodge cut off by floods, 1926",
    "a Hollywood film studio's sound stage after hours, 1938",
    "a Cambridge college on the night of the May Ball, 1931",
    "a remote tea estate bungalow in the Ceylon hills during the monsoon, 1933",
    "a Monte Carlo casino villa during the Grand Prix, 1930",
    "a Swiss sanatorium high above Davos, 1928",
    "a Paris couture house the night before a collection is shown, 1935",
]

DESIGN_RULES = """You are a mystery novelist designing a fair-play golden-age whodunit for an interactive detective \
game. The player has 15 turns to question suspects, search rooms, and catch liars out with proof. Game code (not \
you) decides what is revealed when, so your case must fit the engine's mechanics EXACTLY.

## Story requirements
- Exactly one culprit, with clear means, motive, and opportunity. Every suspect has a plausible motive and one secret.
- Innocent suspects lie only about their own secrets, never about the murder. They do not know who did it.
- 5 suspects, 5 locations, 6-8 topics, 12-16 clues. PG-13: no gore.
- Write in the voice of a 1920s/30s detective novel. Names, roles and details must suit the setting.

## Ids
- Suspects: s1..s5. Clues: c1, c2, ... Locations and topics: short snake_case ids.
- Lie ids: "<suspect>_lie_<word>", secret ids: "<suspect>_sec". Every id is unique across the whole case.

## Topics (how questions are matched)
- The player types free-text questions; a question matches a topic if it contains one of its keywords.
- Keywords are lowercase words or short phrases a player would naturally type ("garden", "shed", "will").
- You MUST include a topic with id "whereabouts" ("Where were you?"). The first question to any suspect always \
counts as asking about whereabouts.

## Lies and statements
- A lie is told the first time the player asks its suspect about any of the lie's topics. `statement` is the exact \
first-person line recorded as a quote on the board. `contradicted_by` lists the evidence that breaks it.
- The culprit has 2-3 lies. One MUST be their alibi: topics ["whereabouts"], and its statement must equal the \
culprit's alibi_claim. Every culprit lie must appear in at least one contradiction.
- Each innocent has exactly one lie, about their secret, with topics other than "whereabouts".

## Clues and how they unlock
- unlock_type "examine": found by searching unlock_location (set unlock_location = location; unlock_suspect and \
unlock_topic ""). Every location must hold at least one examine clue; the crime scene holds 2.
- unlock_type "interrogate": a suspect reveals it when asked about unlock_topic (set unlock_suspect, unlock_topic; \
unlock_location ""; location may be ""). It must be something that suspect knows (list it in their `knows`).
- unlock_type "confront": revealed ONLY as the `reveals` of a contradiction (all unlock_* fields ""). Use this \
for admissions a suspect makes when caught out.
- points_to lists suspects the clue implicates. is_red_herring marks clues that point at an innocent and only \
seem damning. Red herrings never point at the culprit.
- At least 4 non-herring clues point at the culprit, reachable through different actions (search, testimony, \
confrontation). No innocent may have as many non-herring clues as the culprit. Use 2-3 red herrings, each \
pointing at a different innocent.
- Optional event_time / event_suspect / event_text: a verified fact the clue establishes, shown on the player's \
timeline. Leave all three "" when the clue establishes no timed event.

## Contradictions (the core "aha" mechanic)
- Each contradiction pairs a lie (lie_id) with a clue that disproves it (evidence_id). suspect = the liar. \
composure_change is between -35 and -25. `reveals` is a confront-unlock clue id or "".
- The evidence must be findable without that same contradiction (an examine or interrogate clue, or a confront \
clue revealed by a different contradiction).
- Give the culprit's alibi lie two different contradictions (physical evidence and a witness), both revealing the \
same admission clue, so the player has two routes to the breakthrough.
- Each innocent's lie gets one contradiction, usually with their red herring as the evidence; it may reveal a clue \
that clears them (an alibi confirmation, with a timeline event).
- Secrets: reveal_at_composure 60-70 (one contradiction is not enough to crack them; two is). The confession is a \
first-person line admitting the secret, never the murder.

## Solution
- required_evidence: exactly 3 clue ids that prove the case: two examine clues and the culprit's confront-only \
admission. Finding all three must take at most 9 actions.
- motive_options: 5 options including the true motive (same id as motive.id); acceptable_motives contains motive.id.

## Timeline
- Times are 24-hour "HH:MM". time_of_death is "HH:MM-HH:MM". truth_timeline lists 6-8 events in order. The \
culprit has an event at the crime scene inside the time-of-death window. Every event has a location id.
- claimed_timeline is what each suspect SAYS they did (the culprit's is false).

## Output
Reply with ONE JSON object and nothing else: no prose, no code fences. It must match the example's structure \
exactly: the same keys, nesting and types, every key present (use "" for an empty string field, [] for an empty \
list). Below is a complete, valid example. Do not reuse its setting, names, plot or clues."""


@cache
def system_prompt() -> str:
    example = from_case_file(library()[EXAMPLE_CASE_ID]).model_dump_json(indent=1)
    return f"{DESIGN_RULES}\n\n<example_case>\n{example}\n</example_case>"


@dataclass
class Attempt:
    errors: list[str]
    seconds: float


@dataclass
class GenerationResult:
    case: CaseFile | None
    setting: str
    attempts: list[Attempt] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)

    @property
    def first_try(self) -> bool:
        return self.case is not None and len(self.attempts) == 1


def _json_object(text: str) -> str:
    """The outermost JSON object in a reply (tolerates prose or ``` fences around it)."""
    start, end = text.find("{"), text.rfind("}")
    return text[start : end + 1] if 0 <= start < end else text


def _schema_errors(exc: ValidationError) -> list[str]:
    return [f"schema: {'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()[:30]]


def check(reply: str, case_id: str) -> tuple[CaseFile | None, list[str]]:
    """Parses and validates a reply. Every failure becomes an error message the model can act on."""
    try:
        generated = GeneratedCase.model_validate_json(_json_object(reply))
        case = to_case_file(generated, case_id)
    except ValidationError as exc:
        return None, _schema_errors(exc)
    errors = validate_case(case)
    return (None if errors else case), errors


def _brief(setting: str) -> str:
    return (
        f"Design a brand-new case set in {setting}.\n"
        "Make the culprit someone the player will not suspect first, and give every innocent a secret worth hiding."
    )


def _repair(errors: list[str]) -> str:
    listed = "\n".join(f"- {e}" for e in errors[:30])
    return (
        "The fair-play validator rejected this case:\n"
        f"{listed}\n\n"
        "Return the complete corrected case. Keep everything that works and change only what is needed to fix "
        "these problems."
    )


def _add_usage(total: dict[str, int], usage: dict[str, int]) -> None:
    for key, value in usage.items():
        total[key] = total.get(key, 0) + value


async def generate_case(
    llm: LLM, setting: str | None = None, rng: random.Random | None = None, max_attempts: int = MAX_ATTEMPTS
) -> GenerationResult:
    """Generates and validates one case, repairing it up to max_attempts times. `case` is None if all fail."""
    setting = setting or (rng or random).choice(SETTINGS)
    case_id = f"gen_{uuid.uuid4().hex[:10]}"
    result = GenerationResult(case=None, setting=setting)
    messages: list[dict] = [{"role": "user", "content": _brief(setting)}]

    for _ in range(max_attempts):
        started = time.monotonic()
        try:
            output = await llm.complete(
                model=GENERATOR_MODEL, system=system_prompt(), messages=messages, max_tokens=MAX_TOKENS
            )
        except anthropic.BadRequestError:
            raise  # a malformed request never succeeds on retry
        except (LLMRefusal, LLMTruncated, anthropic.APIError) as err:
            log.warning("case generation call failed: %s", err)
            result.attempts.append(Attempt(errors=[f"generation failed: {type(err).__name__}"], seconds=0.0))
            continue
        _add_usage(result.usage, output.usage)
        case, errors = check(output.text, case_id)
        result.attempts.append(Attempt(errors=errors, seconds=time.monotonic() - started))
        if case is not None:
            result.case = case
            return result
        log.info("generated case rejected (%d errors), asking for a repair", len(errors))
        messages = [
            *messages,
            {"role": "assistant", "content": output.text},
            {"role": "user", "content": _repair(errors)},
        ]
    return result
