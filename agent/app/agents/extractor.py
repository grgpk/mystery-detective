"""Pulls one notable, checkable claim out of a suspect's reply for the evidence board."""

from pydantic import BaseModel, Field

from app.llm import LLM, PERSONA_MODEL, LLMRefusal

MAX_WORDS = 25


class ExtractedClaim(BaseModel):
    claim: str | None = Field(
        default=None,
        description="One first-person quote (max 25 words) stating a checkable fact, or null if there is none",
    )


async def extract_claim(llm: LLM, speaker: str, reply: str, already_recorded: list[str]) -> str | None:
    recorded = "\n".join(f"- {s}" for s in already_recorded) or "- none"
    try:
        result = await llm.parse(
            model=PERSONA_MODEL,
            system=(
                "You keep a detective's notebook. From a suspect's answer, extract at most ONE notable, checkable "
                "factual claim (where they were, what they saw, who they were with, what they know about others) "
                "as a short first-person quote. Skip opinions, pleasantries, and anything already recorded."
            ),
            messages=[
                {
                    "role": "user",
                    "content": f"Speaker: {speaker}\nAlready recorded:\n{recorded}\n\nAnswer:\n{reply}",
                }
            ],
            output_type=ExtractedClaim,
            max_tokens=256,
        )
    except LLMRefusal:
        return None
    claim = (result.claim or "").strip().strip('"')
    if not claim or len(claim.split()) > MAX_WORDS:
        return None
    if any(claim.lower() in r.lower() or r.lower() in claim.lower() for r in already_recorded):
        return None
    return claim
