"""Output filter: stops a persona from voicing clue or secret text it has not been allowed to reveal."""

import re

from app.models.case import CaseFile
from app.models.public import Progress

STOPWORDS = {
    "about", "after", "again", "against", "always", "around", "before", "being", "could", "every", "himself",
    "herself", "inspector", "never", "other", "should", "their", "there", "these", "those", "through", "tonight",
    "under", "where", "which", "while", "would", "evening", "house", "night",
}  # fmt: skip
LEAK_THRESHOLD = 0.5
MIN_DISTINCT_WORDS = 4
BREAK_CHARACTER = re.compile(r"\b(as an ai|language model|my (system )?prompt|my instructions)\b", re.IGNORECASE)

DEFLECTION = "I've said all I intend to say on that, Inspector."


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z']+", text.lower()) if len(w) >= 5 and w not in STOPWORDS}


def protected_texts(case: CaseFile, progress: Progress, suspect_id: str, allowed: list[str]) -> list[set[str]]:
    """Distinctive words of what this suspect must not voice: unrevealed clues and its own unrevealed secrets.

    Words from the suspect's own openly-told story (alibi, account of the evening, lies) are removed, so a
    suspect repeating their alibi is never mistaken for leaking a clue that happens to confirm it.
    """
    suspect = case.suspect(suspect_id)
    own_story = _words(
        " ".join(
            [
                suspect.alibi_claim,
                *(c.event for c in suspect.claimed_timeline),
                *(lie.statement for lie in suspect.lies),
            ]
        )
    )
    known = {*progress.revealed_clues, *allowed}
    texts = [c.text for c in case.clues if c.id not in known]
    texts += [s.text for s in suspect.secrets if s.id not in progress.revealed_secrets and s.id not in allowed]
    return [words for words in (_words(t) - own_story for t in texts) if len(words) >= MIN_DISTINCT_WORDS]


def leaks(sentence: str, protected: list[set[str]]) -> bool:
    if BREAK_CHARACTER.search(sentence):
        return True
    words = _words(sentence)
    return any(len(words & target) / len(target) >= LEAK_THRESHOLD for target in protected)


_STAGE_DIRECTION = re.compile(r"\*[^*]*\*|\*")
_QUOTES = re.compile(r'["“”]')
_SPEAKER_PREFIX = re.compile(r"\s*((?:[A-Z][\w.']*\s?){1,4}):\s*")


def clean_speech(sentence: str, speaker_name: str, first: bool) -> str:
    """Strips what the prompt forbids but models sometimes add: *stage directions*, a "Name:" prefix, quote marks
    (the UI adds its own). Keeps trailing whitespace so streamed text stays spaced."""
    text = _QUOTES.sub("", _STAGE_DIRECTION.sub("", sentence))
    prefix = _SPEAKER_PREFIX.match(text) if first else None
    if prefix and set(prefix.group(1).split()) & set(speaker_name.split()):
        text = text[prefix.end() :]
    stripped = text.strip()
    return f"{stripped} " if stripped else ""


_SENTENCE_END = re.compile(r"(?<=[.!?…\"”])\s+")


def split_complete_sentences(buffer: str) -> tuple[list[str], str]:
    """Splits finished sentences off the front of a streaming buffer."""
    parts = _SENTENCE_END.split(buffer)
    if len(parts) == 1:
        return [], buffer
    complete, rest = parts[:-1], parts[-1]
    # Re-attach the separator whitespace so streamed text keeps its spacing.
    return [p + " " for p in complete], rest
