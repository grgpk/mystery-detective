"use client";

import { Button, Stamp } from "@/components/ui";
import { useGame } from "@/lib/game-context";

export function LocationCard({ locationId }: { locationId: string }) {
  const { state, send, isRunning } = useGame();
  const location = state?.locations.find((l) => l.id === locationId);
  if (!state || !location) return null;
  const isScene = state.victim.crimeScene === locationId;

  return (
    <article className="paper flex items-start justify-between gap-3 rounded-sm p-3">
      <div className="min-w-0">
        <h3 className="font-type leading-tight">
          {location.label} {isScene && <span className="text-alert text-xs">(scene)</span>}
        </h3>
        <p className="text-ink-soft mt-0.5 text-xs">{location.description}</p>
      </div>
      {location.examined ? (
        <Stamp>Searched</Stamp>
      ) : (
        <Button
          variant="ghost"
          className="shrink-0"
          disabled={isRunning || state.phase !== "investigating"}
          onClick={() => send({ type: "examine", locationId }, `I search ${location.label.toLowerCase()}.`)}
        >
          Examine
        </Button>
      )}
    </article>
  );
}
