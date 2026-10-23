"""FastAPI app exposing the game master as an AG-UI endpoint (SSE)."""

import asyncio
import hmac
import logging
import os
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime, timedelta

from ag_ui.core import RunAgentInput
from ag_ui.encoder import EventEncoder
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from app import career, daily
from app.analytics import summarize
from app.engine.case_library import catalogue, daily_case, library
from app.game import GameMaster, Limits
from app.generation.pool import InMemoryCasePool, PoolFiller, PostgresCasePool
from app.llm import ScriptedLLM, default_llm
from app.store.repo import InMemoryRepo, PostgresRepo

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("last_alibi")

RUNS_PER_MINUTE = int(os.getenv("RUNS_PER_MINUTE", "30"))
CASE_POOL_SIZE = int(os.getenv("CASE_POOL_SIZE", "2"))
LIMITS = Limits(
    games_per_day=int(os.getenv("GAMES_PER_DAY", "30")),
    fresh_cases_per_day=int(os.getenv("FRESH_CASES_PER_DAY", "5")),
)
# Shared with the Next.js server; without it anyone who finds this URL could spend the LLM budget.
AGENT_SHARED_SECRET = os.getenv("AGENT_SHARED_SECRET", "")
AGENT_KEY_HEADER = "x-agent-key"


def require_agent_key(key: str | None = Header(default=None, alias=AGENT_KEY_HEADER)) -> None:
    if AGENT_SHARED_SECRET and not hmac.compare_digest(key or "", AGENT_SHARED_SECRET):
        raise HTTPException(status_code=403, detail="forbidden")


SESSION_HEADER = "x-session-id"


class RateLimiter:
    """Sliding-window limit per session, to cap LLM spend."""

    def __init__(self, limit: int, window: float = 60.0):
        self.limit, self.window = limit, window
        self.hits: defaultdict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        hits = self.hits[key]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True


@asynccontextmanager
async def lifespan(app: FastAPI):
    cases = library()  # fail fast if a hand-written case is broken
    log.info("loaded %d validated case(s): %s", len(cases), ", ".join(cases))
    if not AGENT_SHARED_SECRET:
        log.warning("AGENT_SHARED_SECRET not set: the agent accepts calls from anyone (fine for local dev only)")
    dsn = os.getenv("DATABASE_URL")
    repo = await PostgresRepo.connect(dsn) if dsn else InMemoryRepo()
    if not dsn:
        log.warning("DATABASE_URL not set: games and generated cases are kept in memory only")
    llm = default_llm()
    case_pool = await PostgresCasePool.create(repo.pool) if isinstance(repo, PostgresRepo) else InMemoryCasePool()
    # Each generated case is one or more Claude Opus calls; set CASE_POOL_SIZE=0 to turn generation off.
    pool_size = 0 if isinstance(llm, ScriptedLLM) else CASE_POOL_SIZE
    filler = PoolFiller(case_pool, llm, target=pool_size)
    filler_task = asyncio.create_task(filler.run()) if filler.enabled else None
    log.info("case generation %s (pool target %d)", "on" if filler.enabled else "off", pool_size)

    app.state.game = GameMaster(llm, repo, fresh_cases=filler, limits=LIMITS)
    app.state.repo = repo
    app.state.filler = filler
    app.state.limiter = RateLimiter(RUNS_PER_MINUTE)
    yield
    if filler_task:
        filler_task.cancel()
        with suppress(asyncio.CancelledError):
            await filler_task
    if isinstance(repo, PostgresRepo):
        await repo.close()


app = FastAPI(title="The Last Alibi agent", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "cases": list(library())}


@app.get("/cases", dependencies=[Depends(require_agent_key)])
async def cases(request: Request) -> dict:
    filler: PoolFiller = request.app.state.filler
    return {
        "cases": catalogue(),
        "fresh": {
            "enabled": filler.enabled,
            "ready": await filler.pool.ready(),
            "generating": filler.generating,
        },
    }


@app.get("/stats", dependencies=[Depends(require_agent_key)])
async def stats(request: Request, days: int = 30) -> dict:
    now = datetime.now(UTC)
    records = await request.app.state.repo.records(since=now - timedelta(days=max(1, min(days, 365))))
    return {"days": days, **summarize(records, now)}


@app.get("/daily", dependencies=[Depends(require_agent_key)])
async def daily_board(request: Request, session_id: str | None = Header(default=None, alias=SESSION_HEADER)) -> dict:
    """Today's case, the leaderboard, and (with a session) the caller's own daily game."""
    day = daily.today()
    case = daily_case(day)
    entries = daily.leaderboard(await request.app.state.repo.daily_games(day.isoformat()))
    mine = None
    if session_id:
        own = await request.app.state.repo.daily_games(day.isoformat(), owner=session_id)
        if own:
            game = own[0]
            entry = next((e for e in entries if e.thread_id == game.thread_id), None)
            mine = {
                "threadId": game.thread_id,
                "phase": game.record.progress.phase,
                "score": entry.score if entry else None,
                "rank": entry.rank if entry else None,
                "name": game.record.progress.leaderboard_name,
            }
    return {
        "date": day.isoformat(),
        "case": {"caseId": case.case_id, "title": case.setting.title, "place": case.setting.place},
        "players": len(entries),
        "leaderboard": [e.public() for e in entries[: daily.LEADERBOARD_SIZE]],
        "you": mine,
    }


@app.get("/career", dependencies=[Depends(require_agent_key)])
async def career_page(request: Request, session_id: str | None = Header(default=None, alias=SESSION_HEADER)) -> dict:
    """The calling player's career (their identity is the anonymous session)."""
    if not session_id:
        raise HTTPException(status_code=401, detail="missing session")
    return career.summarize(await request.app.state.repo.owner_records(session_id), daily.today())


@app.post("/agent", dependencies=[Depends(require_agent_key)])
async def run_agent(
    run_input: RunAgentInput,
    request: Request,
    session_id: str | None = Header(default=None, alias=SESSION_HEADER),
) -> StreamingResponse:
    if not session_id or len(session_id) > 128:
        raise HTTPException(status_code=401, detail="missing session")
    if not request.app.state.limiter.allow(session_id):
        raise HTTPException(status_code=429, detail="Too many actions. Take a breath, Inspector.")

    encoder = EventEncoder(accept=request.headers.get("accept"))
    game: GameMaster = request.app.state.game

    async def events():
        async for event in game.run(run_input, owner=session_id):
            yield encoder.encode(event)

    return StreamingResponse(events(), media_type=encoder.get_content_type())
