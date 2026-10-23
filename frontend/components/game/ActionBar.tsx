"use client";

import { Button } from "@/components/ui";
import { useGame } from "@/lib/game-context";
import { useUi } from "@/lib/store";

export function ActionBar() {
  const { state, send, isRunning } = useGame();
  const openCasePicker = useUi((s) => s.setCasePickerOpen);
  if (!state) return null;
  const { turnsLeft, maxTurns, phase, hintCost } = state;
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
        variant="brass"
        disabled={phase !== "investigating" || isRunning || turnsLeft <= hintCost}
        title={turnsLeft <= hintCost ? "Not enough turns left for a hint" : `Costs ${hintCost} turns`}
        onClick={() => send({ type: "hint" }, "I ask my sergeant what they make of it.")}
      >
        Hint · {hintCost} turn{hintCost === 1 ? "" : "s"}
      </Button>
      <Button
        variant="danger"
        disabled={!canAccuse || isRunning}
        onClick={() => send({ type: "open_accuse" })}
      >
        Accuse
      </Button>
      <Button
        variant="desk"
        onClick={() => openCasePicker(true)}
      >
        New case
      </Button>
    </div>
  );
}
