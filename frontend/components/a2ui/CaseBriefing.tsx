"use client";

import { Button, Stamp } from "@/components/ui";
import { useGame } from "@/lib/game-context";

export function CaseBriefing() {
  const { state, send, isRunning } = useGame();
  if (!state) return null;
  const { victim } = state;

  return (
    <article className="paper mx-auto max-w-2xl rounded-sm p-6 sm:p-8">
      <header className="mb-4 flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-type text-ink-soft text-xs tracking-[0.3em] uppercase">Case file</p>
          <h1 className="font-type text-3xl leading-tight">{state.title}</h1>
          <p className="text-ink-soft italic">{state.place}</p>
        </div>
        <Stamp tone="alert">Confidential</Stamp>
      </header>

      <dl className="border-ink/20 mb-4 grid grid-cols-1 gap-x-6 gap-y-1 border-y py-3 text-sm sm:grid-cols-3">
        <div>
          <dt className="font-type text-ink-soft text-xs uppercase">Victim</dt>
          <dd>{victim.name}</dd>
        </div>
        <div>
          <dt className="font-type text-ink-soft text-xs uppercase">Cause</dt>
          <dd>{victim.causeOfDeath}</dd>
        </div>
        <div>
          <dt className="font-type text-ink-soft text-xs uppercase">Time of death</dt>
          <dd>{victim.timeOfDeath}</dd>
        </div>
      </dl>

      <p className="mb-4 leading-relaxed">{state.briefing}</p>
      <p className="text-ink-soft mb-6 text-sm">
        {state.suspects.length} people remain in the house. You have {state.maxTurns} turns.
      </p>

      {state.phase === "briefing" ? (
        <Button onClick={() => send({ type: "begin" })} disabled={isRunning}>
          Begin the investigation
        </Button>
      ) : (
        <Stamp>Investigation under way</Stamp>
      )}
    </article>
  );
}
