"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";

import type { PublicState } from "@/lib/protocol/types";
import { isMuted, play, setMuted, subscribeMuted } from "@/lib/sound";

/** The mute toggle as React state, shared by every component that shows it. */
export function useMuted(): [boolean, (muted: boolean) => void] {
  const muted = useSyncExternalStore(subscribeMuted, isMuted, () => false);
  return [muted, setMuted];
}

/**
 * Turns shared-state transitions into sound and a contradiction flash. Watches the state rather than events, so
 * cues fire the same way whatever triggered the change. Returns a key that changes on each contradiction.
 */
export function useGameCues(state: PublicState | null): number {
  const previous = useRef<PublicState | null>(null);
  const [flashKey, setFlashKey] = useState(0);

  useEffect(() => {
    const before = previous.current;
    previous.current = state;
    // Same case only: loading or switching a case is not news.
    if (!state || !before || before.caseId !== state.caseId) return;

    const contradiction =
      state.lastContradiction &&
      (state.lastContradiction.from !== before.lastContradiction?.from ||
        state.lastContradiction.to !== before.lastContradiction?.to);
    if (contradiction) {
      play("contradiction");
      setFlashKey((k) => k + 1);
    } else if (state.clues.length > before.clues.length) {
      play("clue");
    }
    if (state.verdict && !before.verdict) play(state.verdict.score.culpritCorrect ? "solved" : "unsolved");
  }, [state]);

  return flashKey;
}
