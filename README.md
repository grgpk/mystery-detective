# The Last Alibi

A browser murder-mystery where Claude plays the suspects. The agent streams dialogue, shared game state and
declarative UI to a React app over **AG-UI**, with UI described in **A2UI v0.9**.

This is milestones M0–M3 of the plan: one hand-written, validated case (Ashford Manor), playable end to end:
interrogate, examine, confront, accuse, verdict.

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
cd agent && uv run pytest                  # engine, validator, scoring, projection, guard, golden playthrough
cd agent && uv run python -m scripts.leak_eval   # real-model adversarial leak eval (needs credentials)
cd frontend && npm run typecheck && npm run lint && npm run build
```

Pinned protocol versions: `@copilotkit/*` 1.79.1, `@ag-ui/client` 1.0.2, A2UI v0.9 (`@a2ui/web_core` 0.10.x),
`ag-ui-protocol` 1.0.0.
