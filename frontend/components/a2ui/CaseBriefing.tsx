"use client";

import { Typewriter } from "@/components/Typewriter";
import { Button, Stamp } from "@/components/ui";
import { useGame } from "@/lib/game-context";
import { useUi } from "@/lib/store";

export function CaseBriefing() {
  const { state, send, isRunning } = useGame();
  const openCasePicker = useUi((s) => s.setCasePickerOpen);
  if (!state) return null;
  const { victim } = state;

  return (
    <article className="paper animate-deal mx-auto max-w-2xl rounded-sm p-6 sm:p-8">
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

      {state.phase === "briefing" ? (
        <Typewriter text={state.briefing} className="mb-4 cursor-text leading-relaxed" />
      ) : (
        <p className="mb-4 leading-relaxed">{state.briefing}</p>
      )}
      <p className="text-ink-soft mb-6 text-sm">
        {state.suspects.length} suspects. {state.maxTurns} turns to find the truth.
      </p>

      {state.phase === "briefing" ? (
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => send({ type: "begin" })} disabled={isRunning}>
            Begin the investigation
          </Button>
          <Button variant="ghost" onClick={() => openCasePicker(true)} disabled={isRunning}>
            Choose another case
          </Button>
        </div>
      ) : (
        <Stamp>Investigation under way</Stamp>
      )}
    </article>
  );
}
