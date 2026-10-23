"""A pool of validated generated cases, kept topped up in the background so "Play" starts instantly."""

import asyncio
import json
import logging
from collections import deque
from typing import Protocol

import asyncpg

from app.engine.validator import validate_case
from app.generation.generator import choose_setting, generate_case
from app.llm import LLM
from app.models.case import CaseFile
from app.themes import DEFAULT_THEME, theme

log = logging.getLogger(__name__)

RETRY_DELAYS = (60, 300, 900)  # seconds to back off after consecutive failed generations, to cap spend


class CasePool(Protocol):
    async def add(self, case: CaseFile, attempts: int, setting: str) -> None: ...
    async def take(self, theme_id: str = DEFAULT_THEME) -> CaseFile | None: ...

    async def ready(self, theme_id: str | None = None) -> int:
        """Ready cases of one theme, or of all themes."""
        ...

    async def release(self, case: CaseFile) -> None:
        """Puts a taken case back, ready for the next player (it was never actually played)."""
        ...

    async def recent_settings(self, limit: int, theme_id: str = DEFAULT_THEME) -> list[str]:
        """Settings of a theme's most recently generated cases (played or not), newest first."""
        ...


class InMemoryCasePool:
    def __init__(self) -> None:
        self._cases: deque[CaseFile] = deque()
        self._settings: list[tuple[str, str]] = []  # (theme, setting), newest first

    async def add(self, case: CaseFile, attempts: int, setting: str) -> None:
        self._cases.append(case)
        self._settings.insert(0, (case.theme, setting))

    async def take(self, theme_id: str = DEFAULT_THEME) -> CaseFile | None:
        case = next((c for c in self._cases if c.theme == theme_id), None)
        if case is not None:
            self._cases.remove(case)
        return case

    async def release(self, case: CaseFile) -> None:
        self._cases.appendleft(case)

    async def ready(self, theme_id: str | None = None) -> int:
        return sum(1 for c in self._cases if theme_id is None or c.theme == theme_id)

    async def recent_settings(self, limit: int, theme_id: str = DEFAULT_THEME) -> list[str]:
        return [s for t, s in self._settings if t == theme_id][:limit]


SCHEMA = """
CREATE TABLE IF NOT EXISTS generated_cases (
    case_id     TEXT PRIMARY KEY,
    case_file   JSONB NOT NULL,
    attempts    INT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    taken_at    TIMESTAMPTZ
);
ALTER TABLE generated_cases ADD COLUMN IF NOT EXISTS setting TEXT;
ALTER TABLE generated_cases ADD COLUMN IF NOT EXISTS theme TEXT NOT NULL DEFAULT 'golden_age';
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

    async def add(self, case: CaseFile, attempts: int, setting: str) -> None:
        await self.pool.execute(
            """
            INSERT INTO generated_cases (case_id, case_file, attempts, setting, theme)
            VALUES ($1, $2::jsonb, $3, $4, $5)
            """,
            case.case_id,
            json.dumps(case.dump()),
            attempts,
            setting,
            case.theme,
        )

    async def take(self, theme_id: str = DEFAULT_THEME) -> CaseFile | None:
        # Re-validate on the way out: rules may have tightened since the case was stored.
        while True:
            row = await self.pool.fetchrow(
                """
                UPDATE generated_cases SET taken_at = now()
                 WHERE case_id = (SELECT case_id FROM generated_cases WHERE taken_at IS NULL AND theme = $1
                                   ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED)
                RETURNING case_file
                """,
                theme_id,
            )
            if row is None:
                return None
            case = CaseFile.model_validate(json.loads(row["case_file"]))
            if not validate_case(case):
                return case
            log.warning("discarding stored case %s: no longer passes validation", case.case_id)

    async def ready(self, theme_id: str | None = None) -> int:
        return await self.pool.fetchval(
            "SELECT count(*) FROM generated_cases WHERE taken_at IS NULL AND ($1::text IS NULL OR theme = $1)",
            theme_id,
        )

    async def release(self, case: CaseFile) -> None:
        await self.pool.execute(
            """
            INSERT INTO generated_cases (case_id, case_file, attempts, theme) VALUES ($1, $2::jsonb, 1, $3)
            ON CONFLICT (case_id) DO UPDATE SET taken_at = NULL
            """,
            case.case_id,
            json.dumps(case.dump()),
            case.theme,
        )

    async def recent_settings(self, limit: int, theme_id: str = DEFAULT_THEME) -> list[str]:
        rows = await self.pool.fetch(
            """
            SELECT setting FROM generated_cases WHERE setting IS NOT NULL AND theme = $2
             ORDER BY created_at DESC LIMIT $1
            """,
            limit,
            theme_id,
        )
        return [r["setting"] for r in rows]


class PoolFiller:
    """Keeps each theme's target of validated cases ready, generating one case at a time (the theme furthest
    below its target first) and backing off when generation fails."""

    def __init__(self, pool: CasePool, llm: LLM, target: int = 0, targets: dict[str, int] | None = None):
        self.pool, self.llm = pool, llm
        self.targets = targets if targets is not None else {DEFAULT_THEME: target}
        self._wake = asyncio.Event()
        self.generating: str | None = None  # theme being written, if any

    @property
    def enabled(self) -> bool:
        return any(t > 0 for t in self.targets.values())

    async def release(self, case: CaseFile) -> None:
        await self.pool.release(case)

    async def take(self, theme_id: str = DEFAULT_THEME) -> CaseFile | None:
        case = await self.pool.take(theme_id)
        self._wake.set()  # a slot just opened (or the pool was empty): refill
        return case

    async def most_needed(self) -> str | None:
        """The theme furthest below its target, or None if every theme is full."""
        shortfalls = {t: target - await self.pool.ready(t) for t, target in self.targets.items()}
        needed = max(shortfalls, key=shortfalls.__getitem__, default=None)
        return needed if needed is not None and shortfalls[needed] > 0 else None

    async def fill_once(self) -> bool:
        """Generates one case for the neediest theme. Returns False if generation failed."""
        theme_id = await self.most_needed()
        if theme_id is None:
            return True
        setting = choose_setting(
            await self.pool.recent_settings(len(theme(theme_id).settings), theme_id), None, theme_id
        )
        log.info("generating a %s case set in %s", theme_id, setting)
        self.generating = theme_id
        try:
            result = await generate_case(self.llm, setting=setting, theme_id=theme_id)
        finally:
            self.generating = None
        if result.case is None:
            log.warning("case generation failed after %d attempts (%s)", len(result.attempts), result.setting)
            return False
        await self.pool.add(result.case, attempts=len(result.attempts), setting=result.setting)
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
            if await self.most_needed() is None:
                await self._wake.wait()
