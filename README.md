# The Last Alibi

A browser murder-mystery where Claude plays the suspects. The agent streams dialogue, shared game state and
declarative UI to a React app over **AG-UI**, with UI described in **A2UI v0.9**.

This is milestones M0–M4 of the plan: a case generator writes brand-new mysteries, and three hand-written,
validated cases serve as the archive and fallback. Every case is playable end to end (interrogate, examine,
confront, accuse, verdict). The hand-written cases are:

- **Murder at Ashford Manor**: a country house, 1928
- **Death on the Midnight Sleeper**: a snowbound London–Edinburgh night train, 1931
- **Snowbound at the Edelweiss**: an Alpine hotel cut off by an avalanche, 1936

```
frontend/  Next.js 16 + React 19 + CopilotKit v2 (AG-UI client, A2UI renderer), react-flow board
agent/     Python 3.12 + FastAPI + ag-ui-protocol, Anthropic SDK, Postgres (asyncpg)
```

## Run it

```bash
docker compose up -d                       # Postgres on localhost:55432

cd agent
cp .env.example .env                       # add ANTHROPIC_API_KEY (or LLM_MODE=scripted to play offline)
uv sync
uv run uvicorn app.main:app --port 8000

cd ../frontend
cp .env.example .env.local
npm install
npm run dev                                # http://localhost:3000
```

## How it fits together

- **The truth is fixed and server-only.** `agent/app/cases/*.json` is the hidden case file. It is validated at
  startup (`engine/validator.py`, the plan's 7 fair-play rules) and never sent to the browser.
  `engine/projection.py` is the only path from hidden state to public state.
- **Rules in code, flavour in the LLM.** `engine/clue_engine.py` decides turns, unlocks, statements,
  contradictions and composure; `engine/scoring.py` scores. Claude Haiku 5.5 voices suspects, narrates rooms and
  classifies question topics; Claude Opus 5.5 writes the final reveal.
- **Generated cases (M4).** `generation/generator.py` has Claude Opus 5.5 write a whole case as JSON in the
  engine's format, guided by the fair-play rules and one worked example. The validator then checks it, including
  a simulated playthrough of the real engine (`engine/solver.py`) that proves the required evidence is reachable
  within budget and every contradiction can be triggered. Rejected cases go back to Claude with the validator's
  errors, up to 3 attempts. `generation/pool.py` keeps `CASE_POOL_SIZE` validated cases ready in Postgres in the
  background. "A brand-new mystery" in the case picker takes one; if none is ready, the player gets an archive
  case while the next one is written.
- **Personas see only their slice** (`agents/persona.py`), are told per turn what they may reveal, and stream
  through a sentence-level leak guard (`agents/guards.py`).
- **Protocol.** Each player action is one AG-UI run, sent as `forwardedProps.gameAction`. The agent emits
  `STATE_SNAPSHOT`/`STATE_DELTA` for public state, `TEXT_MESSAGE_*` for dialogue (message ids carry the speaker),
  and A2UI surfaces as `show_ui` tool results that CopilotRuntime's A2UI middleware turns into activities.
  The frontend renders those surfaces with a custom catalog (`frontend/components/a2ui/`) whose cards read live
  details from shared state.
- **Sessions.** `proxy.ts` sets an anonymous `la_session` cookie; the runtime route forwards it as
  `X-Session-Id`; the agent stores each game by AG-UI thread id and refuses threads owned by another session.

## Checks

```bash
cd agent && uv run pytest                  # engine, validator, every case solvable, guard, golden playthrough
cd agent && uv run python -m scripts.leak_eval   # real-model adversarial leak eval (needs credentials)
cd agent && uv run python -m scripts.generate_eval 10 --into-pool   # generator pass rates and cost (Claude Opus)
cd frontend && npm run typecheck && npm run lint && npm run build
```

Pinned protocol versions: `@copilotkit/*` 1.79.1, `@ag-ui/client` 1.0.2, A2UI v0.9 (`@a2ui/web_core` 0.10.x),
`ag-ui-protocol` 1.0.0.

## Deploying

The two halves deploy separately: the Next.js frontend to Vercel, and the Python agent to a host that keeps a
process running. The agent fills the case pool in a background task and streams long SSE responses, so serverless
functions are a poor fit: use Fly.io, Railway, Render or Cloud Run with min instances = 1.

**Agent** (`agent/Dockerfile`, one worker per instance):

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Claude credentials |
| `DATABASE_URL` | Postgres (games, generated-case pool) |
| `AGENT_SHARED_SECRET` | **Required in production.** Without it anyone who finds the URL can spend your LLM budget |
| `CASE_POOL_SIZE` | Generated cases kept ready (default 2; 0 turns generation off) |
| `GAMES_PER_DAY` / `FRESH_CASES_PER_DAY` | Per-player caps over a rolling 24 hours (default 30 / 5) |
| `RUNS_PER_MINUTE` | Per-player action rate limit (default 30) |

**Frontend** (Vercel, zero config):

| Variable | Purpose |
|---|---|
| `AGENT_URL` | The agent's `/agent` URL, e.g. `https://last-alibi-agent.fly.dev/agent` |
| `AGENT_SHARED_SECRET` | Same value as the agent's |
| `STATS_TOKEN` | Unlocks `/stats?token=...` (in production `/stats` is a 404 without it) |

Locally, `docker compose --profile full up` runs Postgres and the agent container together.

**Known limits of v1.** Players are identified by an anonymous cookie, so clearing cookies resets their daily caps;
put per-IP rate limiting in front of `/api/copilotkit` (for example a Vercel Firewall rule) before a public launch.
Moderation is a local filter for clearly out-of-bounds questions, backed by the suspects' PG-13 instructions and
Claude's own safety training.
