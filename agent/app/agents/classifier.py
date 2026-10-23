"""Maps a free-text interrogation question to the case's topic vocabulary."""

import re

from pydantic import BaseModel, Field

from app.llm import LLM, PERSONA_MODEL, LLMRefusal
from app.models.case import CaseFile


class TopicGuess(BaseModel):
    topics: list[str] = Field(default_factory=list, description="Topic ids the question is about")


def keyword_topics(case: CaseFile, question: str) -> list[str]:
    text = question.lower()
    return [t.id for t in case.topics if any(re.search(rf"\b{re.escape(k.lower())}", text) for k in t.keywords)]


async def classify_topics(llm: LLM, case: CaseFile, question: str) -> list[str]:
    """Keywords first (free, deterministic); a small model only for questions keywords miss."""
    found = keyword_topics(case, question)
    if found:
        return found
    vocabulary = "\n".join(f"- {t.id}: {t.label} ({', '.join(t.keywords)})" for t in case.topics)
    try:
        guess = await llm.parse(
            model=PERSONA_MODEL,
            system=(
                "You classify a detective's question in a murder-mystery game into topic ids. "
                f"Allowed topic ids:\n{vocabulary}\nReturn only ids from that list; an empty list if none fit."
            ),
            messages=[{"role": "user", "content": question}],
            output_type=TopicGuess,
            max_tokens=256,
        )
    except LLMRefusal:
        return []
    allowed = {t.id for t in case.topics}
    return [t for t in guess.topics if t in allowed]
