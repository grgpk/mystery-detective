"""Game session persistence: hidden case + progress, keyed by AG-UI thread id and owned by a session cookie."""

import json
from dataclasses import dataclass
from typing import Protocol

import asyncpg

from app.models.case import CaseFile
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


class InMemoryRepo:
    def __init__(self) -> None:
        self._rows: dict[str, tuple[str, dict, dict]] = {}

    async def get(self, thread_id: str) -> GameSession | None:
        row = self._rows.get(thread_id)
        if row is None:
            return None
        owner, case, progress = row
        return GameSession(thread_id, owner, CaseFile.model_validate(case), Progress.model_validate(progress))

    async def save(self, session: GameSession) -> None:
        # Store serialized copies so callers can't mutate persisted state by reference.
        self._rows[session.thread_id] = (session.owner, session.case.dump(), session.progress.dump())


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
