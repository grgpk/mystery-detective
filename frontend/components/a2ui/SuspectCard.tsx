"use client";

import { useState } from "react";

import { Button } from "@/components/ui";
import { useGame } from "@/lib/game-context";
import type { Mood } from "@/lib/protocol/types";
import { useUi } from "@/lib/store";

const MOOD_LABEL: Record<Mood, string> = {
  calm: "Composed",
  guarded: "Guarded",
  nervous: "Rattled",
  cracking: "Cracking",
};

export function SuspectCard({ suspectId }: { suspectId: string }) {
  const { state, send, isRunning } = useGame();
  const activeSuspectId = useUi((s) => s.activeSuspectId);
  const setActiveSuspect = useUi((s) => s.setActiveSuspect);
  const suspect = state?.suspects.find((s) => s.id === suspectId);

  // Shake whenever composure drops (derived from the previous render's value, no effect needed).
  const [lastComposure, setLastComposure] = useState(suspect?.composure ?? 100);
  const [shakeKey, setShakeKey] = useState(0);
  if (suspect && suspect.composure !== lastComposure) {
    if (suspect.composure < lastComposure) setShakeKey((k) => k + 1);
    setLastComposure(suspect.composure);
  }

  if (!state || !suspect) return null;
  const active = activeSuspectId === suspectId;
  const investigating = state.phase === "investigating";
  const meterColor = suspect.composure >= 50 ? "bg-sepia" : suspect.composure >= 25 ? "bg-brass" : "bg-string";

  return (
    <article
      key={shakeKey}
      className={`paper rounded-sm p-3 ${shakeKey ? "animate-shake" : ""} ${active ? "ring-brass ring-2" : ""}`}
      aria-label={`${suspect.name}, ${suspect.role}`}
    >
      <header className="flex items-baseline justify-between gap-2">
        <h3 className="font-type text-lg leading-tight">{suspect.name}</h3>
        <span className="text-ink-soft text-xs italic">{suspect.role}</span>
      </header>
      <p className="text-ink-soft mt-1 text-xs">{suspect.appearance}</p>

      <div className="mt-2">
        <div className="text-ink-soft flex justify-between text-[11px] uppercase">
          <span className="font-type">Composure</span>
          <span>{MOOD_LABEL[suspect.mood]}</span>
        </div>
        <meter
          className="sr-only"
          min={0}
          max={100}
          low={25}
          high={50}
          optimum={100}
          value={suspect.composure}
          aria-label={`Composure ${suspect.composure} of 100`}
        />
        <div className="bg-ink/15 mt-1 h-1.5 overflow-hidden rounded-full" aria-hidden>
          <div className={`h-full transition-all duration-700 ${meterColor}`} style={{ width: `${suspect.composure}%` }} />
        </div>
      </div>

      <div className="mt-3 flex gap-2">
        <Button
          variant={active ? "primary" : "ghost"}
          disabled={!investigating}
          onClick={() => setActiveSuspect(suspectId)}
          aria-pressed={active}
        >
          Interrogate
        </Button>
        <Button
          variant="ghost"
          disabled={!investigating || isRunning || state.statements.length === 0}
          onClick={() => send({ type: "open_confront", suspectId })}
        >
          Confront
        </Button>
      </div>
    </article>
  );
}
