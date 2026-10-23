"use client";

import { Button } from "@/components/ui";
import { useGame } from "@/lib/game-context";

export function ActionBar() {
  const { state, send, isRunning, newGame } = useGame();
  if (!state) return null;
  const { turnsLeft, maxTurns, phase } = state;
  const canAccuse = phase === "investigating" || phase === "accusing";

  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="flex items-center gap-2" aria-label={`${turnsLeft} of ${maxTurns} turns left`} role="img">
        <span className="font-type text-on-desk-soft text-xs uppercase">Turns</span>
        <span className="flex gap-0.5" aria-hidden>
          {Array.from({ length: maxTurns }, (_, i) => (
            <span
              key={i}
              className={`h-3 w-1.5 rounded-sm transition-colors ${i < turnsLeft ? "bg-brass" : "bg-on-desk/15"}`}
            />
          ))}
        </span>
        <span className="font-type text-on-desk tabular-nums">{turnsLeft}</span>
      </div>
      <Button
        variant="danger"
        disabled={!canAccuse || isRunning}
        onClick={() => send({ type: "open_accuse" })}
      >
        Accuse
      </Button>
      <Button
        variant="ghost"
        className="border-on-desk/30 text-on-desk-soft hover:bg-on-desk/10"
        onClick={() => {
          if (phase === "ended" || window.confirm("Abandon this case and start a new one?")) newGame();
        }}
      >
        New case
      </Button>
    </div>
  );
}
