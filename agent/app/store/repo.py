"""Game session persistence: hidden case + progress, keyed by AG-UI thread id and owned by a session cookie."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

import asyncpg

from app.models.case import GENERATED_PREFIX, CaseFile
from app.models.public import Progress


@dataclass
class GameSession:
    thread_id: str
    owner: str
    case: CaseFile
    progress: Progress


class SessionRepo(Protocol):
    async def get(self, thread_id: str) -> GameSession | None: ...
    async def save(self, session: GameSession) -> None: ...
    async def delete(self, thread_id: str) -> None: ...

    async def unstarted_generated(
        self, owner: str | None = None, idle_for: timedelta | None = None
    ) -> list[GameSession]:
        """Games on a generated case still on the briefing: one owner's, or anyone's idle for `idle_for`."""
        ...


class InMemoryRepo:
    def __init__(self) -> None:
        self._rows: dict[str, tuple[str, dict, dict, datetime]] = {}

    async def get(self, thread_id: str) -> GameSession | None:
        row = self._rows.get(thread_id)
        if row is None:
            return None
        owner, case, progress, _ = row
        return GameSession(thread_id, owner, CaseFile.model_validate(case), Progress.model_validate(progress))

    async def save(self, session: GameSession) -> None:
        # Store serialized copies so callers can't mutate persisted state by reference.
        self._rows[session.thread_id] = (
            session.owner,
            session.case.dump(),
            session.progress.dump(),
            datetime.now(UTC),
        )

    async def delete(self, thread_id: str) -> None:
        self._rows.pop(thread_id, None)

    async def unstarted_generated(
        self, owner: str | None = None, idle_for: timedelta | None = None
    ) -> list[GameSession]:
        cutoff = datetime.now(UTC) - idle_for if idle_for is not None else None
        found = []
        for thread_id, (row_owner, case, progress, updated) in self._rows.items():
            if (
                case["caseId"].startswith(GENERATED_PREFIX)
                and progress["phase"] == "briefing"
                and (owner is None or row_owner == owner)
                and (cutoff is None or updated <= cutoff)
            ):
                found.append(await self.get(thread_id))
        return found


SCHEMA = """
CREATE TABLE IF NOT EXISTS game_sessions (
    thread_id   TEXT PRIMARY KEY,
    owner       TEXT NOT NULL,
    case_id     TEXT NOT NULL,
    case_file   JSONB NOT NULL,
    progress    JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS game_sessions_owner_idx ON game_sessions (owner);
"""


class PostgresRepo:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    @classmethod
    async def connect(cls, dsn: str) -> "PostgresRepo":
        pool = await asyncpg.create_pool(dsn, min_size=1, max_size=10)
        async with pool.acquire() as conn:
            await conn.execute(SCHEMA)
        return cls(pool)

    async def close(self) -> None:
        await self.pool.close()

    async def get(self, thread_id: str) -> GameSession | None:
        row = await self.pool.fetchrow(
            "SELECT owner, case_file, progress FROM game_sessions WHERE thread_id = $1", thread_id
        )
        if row is None:
            return None
        return GameSession(
            thread_id,
            row["owner"],
            CaseFile.model_validate(json.loads(row["case_file"])),
            Progress.model_validate(json.loads(row["progress"])),
        )

    async def save(self, session: GameSession) -> None:
        await self.pool.execute(
            """
            INSERT INTO game_sessions (thread_id, owner, case_id, case_file, progress)
            VALUES ($1, $2, $3, $4::jsonb, $5::jsonb)
            ON CONFLICT (thread_id) DO UPDATE
               SET case_id = EXCLUDED.case_id, case_file = EXCLUDED.case_file,
                   progress = EXCLUDED.progress, updated_at = now()
            """,
            session.thread_id,
            session.owner,
            session.case.case_id,
            json.dumps(session.case.dump()),
            json.dumps(session.progress.dump()),
        )

    async def delete(self, thread_id: str) -> None:
        await self.pool.execute("DELETE FROM game_sessions WHERE thread_id = $1", thread_id)

    async def unstarted_generated(
        self, owner: str | None = None, idle_for: timedelta | None = None
    ) -> list[GameSession]:
        rows = await self.pool.fetch(
            """
            SELECT thread_id, owner, case_file, progress FROM game_sessions
             WHERE starts_with(case_id, $1) AND progress->>'phase' = 'briefing'
               AND ($2::text IS NULL OR owner = $2)
               AND ($3::interval IS NULL OR updated_at <= now() - $3::interval)
            """,
            GENERATED_PREFIX,
            owner,
            idle_for,
        )
        return [
            GameSession(
                row["thread_id"],
                row["owner"],
                CaseFile.model_validate(json.loads(row["case_file"])),
                Progress.model_validate(json.loads(row["progress"])),
            )
            for row in rows
        ]
