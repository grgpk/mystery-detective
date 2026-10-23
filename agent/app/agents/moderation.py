"""First line of moderation for player questions (plan section 10: keep the game PG-13).

A local, deterministic filter for clearly out-of-bounds requests, so they never reach a model and cost no turn.
It deliberately does not try to be clever: suspects are also instructed to stay PG-13, and the model's own
safety training is the backstop for anything subtler.
"""

import re
import unicodedata

REFUSAL = "Your question hangs in the air, unanswered. That is not a line of inquiry the Yard pursues, Inspector."

_PATTERNS = [
    # Sexual content
    r"\bporn\w*",
    r"\bsex(ual(ly)?)?\b",
    r"\bnude(s)?\b",
    r"\bnaked\b(?!\s+(flame|light|eye))",
    r"\brap(e|ed|ing|ist)\b",
    r"\bmolest\w*",
    r"\bincest\w*",
    r"\bstrip\s*(tease|for me)\b",
    # Graphic violence beyond a golden-age whodunit
    r"\bdismember\w*",
    r"\bdisembowel\w*",
    r"\bgor(e|y)\b",
    r"\btortur\w*",
    r"\bin (graphic|gory|gruesome) detail\b",
    r"\bmutilat\w*",
]
_BLOCKED = re.compile("|".join(_PATTERNS), re.IGNORECASE)


def normalize(text: str) -> str:
    """Folds look-alike characters and drops control characters, so spelling tricks don't slip past."""
    folded = unicodedata.normalize("NFKC", text)
    return "".join(ch for ch in folded if ch.isprintable() or ch in "\n\t").strip()


def refusal_for(question: str) -> str | None:
    """None if the question may go to a suspect; otherwise the narrator's in-character refusal."""
    return REFUSAL if _BLOCKED.search(normalize(question)) else None
