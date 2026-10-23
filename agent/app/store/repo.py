"""Game session persistence: hidden case + progress, keyed by AG-UI thread id and owned by a session cookie."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

import asyncpg

from app.analytics import GameRecord
from app.daily import DailyGame
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

    async def count_games(self, owner: str, since: datetime, generated_only: bool = False) -> int:
        """Games this owner created since `since` (optionally only on generated cases)."""
        ...

    async def unstarted_generated(
        self, owner: str | None = None, idle_for: timedelta | None = None
    ) -> list[GameSession]:
        """Games on a generated case still on the briefing: one owner's, or anyone's idle for `idle_for`."""
        ...

    async def records(self, since: datetime) -> list[GameRecord]:
        """Every game created since `since`, for analytics."""
        ...

    async def daily_games(self, day: str, owner: str | None = None) -> list[DailyGame]:
        """Games on the shared case of `day` (ISO date), optionally one owner's."""
        ...


class InMemoryRepo:
    def __init__(self) -> None:
        self._rows: dict[str, tuple[str, dict, dict, datetime]] = {}
        self._created: dict[str, datetime] = {}

    async def get(self, thread_id: str) -> GameSession | None:
        row = self._rows.get(thread_id)
        if row is None:
            return None
        owner, case, progress, _ = row
        return GameSession(thread_id, owner, CaseFile.model_validate(case), Progress.model_validate(progress))

    async def save(self, session: GameSession) -> None:
        # Store serialized copies so callers can't mutate persisted state by reference.
        self._created.setdefault(session.thread_id, datetime.now(UTC))
        self._rows[session.thread_id] = (
            session.owner,
            session.case.dump(),
            session.progress.dump(),
            datetime.now(UTC),
        )

    async def delete(self, thread_id: str) -> None:
        self._rows.pop(thread_id, None)
        self._created.pop(thread_id, None)

    async def daily_games(self, day: str, owner: str | None = None) -> list[DailyGame]:
        found = []
        for thread_id, (row_owner, case, progress, updated) in self._rows.items():
            if progress.get("dailyDate") == day and (owner is None or row_owner == owner):
                record = GameRecord(
                    CaseFile.model_validate(case), Progress.model_validate(progress), self._created[thread_id], updated
                )
                found.append(DailyGame(thread_id, row_owner, record))
        return found

    async def records(self, since: datetime) -> list[GameRecord]:
        return [
            GameRecord(CaseFile.model_validate(case), Progress.model_validate(progress), self._created[tid], updated)
            for tid, (_, case, progress, updated) in self._rows.items()
            if self._created[tid] >= since
        ]

    async def count_games(self, owner: str, since: datetime, generated_only: bool = False) -> int:
        return sum(
            1
            for thread_id, (row_owner, case, _, _) in self._rows.items()
            if row_owner == owner
            and self._created[thread_id] >= since
            and (not generated_only or case["caseId"].startswith(GENERATED_PREFIX))
        )

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
CREATE INDEX IF NOT EXISTS game_sessions_daily_idx ON game_sessions ((progress->>'dailyDate'))
    WHERE progress->>'dailyDate' IS NOT NULL;
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

    async def daily_games(self, day: str, owner: str | None = None) -> list[DailyGame]:
        rows = await self.pool.fetch(
            """
            SELECT thread_id, owner, case_file, progress, created_at, updated_at FROM game_sessions
             WHERE progress->>'dailyDate' = $1 AND ($2::text IS NULL OR owner = $2)
            """,
            day,
            owner,
        )
        return [
            DailyGame(
                r["thread_id"],
                r["owner"],
                GameRecord(
                    CaseFile.model_validate(json.loads(r["case_file"])),
                    Progress.model_validate(json.loads(r["progress"])),
                    r["created_at"],
                    r["updated_at"],
                ),
            )
            for r in rows
        ]

    async def records(self, since: datetime) -> list[GameRecord]:
        rows = await self.pool.fetch(
            "SELECT case_file, progress, created_at, updated_at FROM game_sessions WHERE created_at >= $1", since
        )
        return [
            GameRecord(
                CaseFile.model_validate(json.loads(r["case_file"])),
                Progress.model_validate(json.loads(r["progress"])),
                r["created_at"],
                r["updated_at"],
            )
            for r in rows
        ]

    async def count_games(self, owner: str, since: datetime, generated_only: bool = False) -> int:
        return await self.pool.fetchval(
            """
            SELECT count(*) FROM game_sessions
             WHERE owner = $1 AND created_at >= $2 AND (NOT $3 OR starts_with(case_id, $4))
            """,
            owner,
            since,
            generated_only,
            GENERATED_PREFIX,
        )

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
