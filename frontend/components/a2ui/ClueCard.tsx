"use client";

import { Button, Stamp } from "@/components/ui";
import { useGame } from "@/lib/game-context";

export function ClueCard({ clueId }: { clueId: string }) {
  const { state, updateBoard } = useGame();
  const clue = state?.clues.find((c) => c.id === clueId);
  if (!state || !clue) return null;
  const pinned = state.board.pins.includes(clueId);
  const location = state.locations.find((l) => l.id === clue.location)?.label;

  return (
    <article
      className={`paper border-sepia max-w-md rotate-[-0.4deg] rounded-sm border-l-4 p-4 ${clue.isNew ? "animate-deal" : ""}`}
    >
      <header className="mb-1 flex items-center justify-between gap-2">
        <h3 className="font-type text-lg">{clue.title}</h3>
        {clue.isNew && (
          <span className="animate-stamp">
            <Stamp tone="alert">New clue</Stamp>
          </span>
        )}
      </header>
      <p className="leading-relaxed">{clue.text}</p>
      <footer className="mt-3 flex items-center justify-between gap-2">
        <span className="text-ink-soft text-xs italic">{location ?? "Testimony"}</span>
        <Button
          variant={pinned ? "primary" : "ghost"}
          disabled={pinned}
          onClick={() => updateBoard({ ...state.board, pins: [...state.board.pins, clueId] })}
        >
          {pinned ? "Pinned" : "Pin to board"}
        </Button>
      </footer>
    </article>
  );
}
