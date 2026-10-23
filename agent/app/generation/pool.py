"""A pool of validated generated cases, kept topped up in the background so "Play" starts instantly."""

import asyncio
import json
import logging
from collections import deque
from typing import Protocol

import asyncpg

from app.engine.validator import validate_case
from app.generation.generator import generate_case
from app.llm import LLM
from app.models.case import CaseFile

log = logging.getLogger(__name__)

RETRY_DELAYS = (60, 300, 900)  # seconds to back off after consecutive failed generations, to cap spend


class CasePool(Protocol):
    async def add(self, case: CaseFile, attempts: int) -> None: ...
    async def take(self) -> CaseFile | None: ...
    async def ready(self) -> int: ...


class InMemoryCasePool:
    def __init__(self) -> None:
        self._cases: deque[CaseFile] = deque()

    async def add(self, case: CaseFile, attempts: int) -> None:
        self._cases.append(case)

    async def take(self) -> CaseFile | None:
        return self._cases.popleft() if self._cases else None

    async def ready(self) -> int:
        return len(self._cases)


SCHEMA = """
CREATE TABLE IF NOT EXISTS generated_cases (
    case_id     TEXT PRIMARY KEY,
    case_file   JSONB NOT NULL,
    attempts    INT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    taken_at    TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS generated_cases_ready_idx ON generated_cases (created_at) WHERE taken_at IS NULL;
"""


class PostgresCasePool:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    @classmethod
    async def create(cls, pool: asyncpg.Pool) -> "PostgresCasePool":
        async with pool.acquire() as conn:
            await conn.execute(SCHEMA)
        return cls(pool)

    async def add(self, case: CaseFile, attempts: int) -> None:
        await self.pool.execute(
            "INSERT INTO generated_cases (case_id, case_file, attempts) VALUES ($1, $2::jsonb, $3)",
            case.case_id,
            json.dumps(case.dump()),
            attempts,
        )

    async def take(self) -> CaseFile | None:
        # Re-validate on the way out: rules may have tightened since the case was stored.
        while True:
            row = await self.pool.fetchrow(
                """
                UPDATE generated_cases SET taken_at = now()
                 WHERE case_id = (SELECT case_id FROM generated_cases WHERE taken_at IS NULL
                                   ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED)
                RETURNING case_file
                """
            )
            if row is None:
                return None
            case = CaseFile.model_validate(json.loads(row["case_file"]))
            if not validate_case(case):
                return case
            log.warning("discarding stored case %s: no longer passes validation", case.case_id)

    async def ready(self) -> int:
        return await self.pool.fetchval("SELECT count(*) FROM generated_cases WHERE taken_at IS NULL")


class PoolFiller:
    """Keeps `target` validated cases ready. Generates one case at a time; backs off when generation fails."""

    def __init__(self, pool: CasePool, llm: LLM, target: int):
        self.pool, self.llm, self.target = pool, llm, target
        self._wake = asyncio.Event()
        self.generating = False

    @property
    def enabled(self) -> bool:
        return self.target > 0

    async def take(self) -> CaseFile | None:
        case = await self.pool.take()
        self._wake.set()  # a slot just opened (or the pool was empty): refill
        return case

    async def fill_once(self) -> bool:
        """Generates one case if the pool is short. Returns False if generation failed."""
        if await self.pool.ready() >= self.target:
            return True
        self.generating = True
        try:
            result = await generate_case(self.llm)
        finally:
            self.generating = False
        if result.case is None:
            log.warning("case generation failed after %d attempts (%s)", len(result.attempts), result.setting)
            return False
        await self.pool.add(result.case, attempts=len(result.attempts))
        log.info(
            "generated case %s '%s' in %d attempt(s)",
            result.case.case_id,
            result.case.setting.title,
            len(result.attempts),
        )
        return True

    async def run(self) -> None:
        failures = 0
        while self.enabled:
            try:
                ok = await self.fill_once()
            except Exception:
                log.exception("case pool filler crashed; retrying later")
                ok = False
            failures = 0 if ok else failures + 1
            if failures:
                await asyncio.sleep(RETRY_DELAYS[min(failures, len(RETRY_DELAYS)) - 1])
                continue
            self._wake.clear()  # clear before checking, so a take() in between still wakes us
            if await self.pool.ready() >= self.target:
                await self._wake.wait()
