import { create } from "zustand";

import type { Difficulty } from "@/lib/protocol/types";

const DIFFICULTY_KEY = "last-alibi:difficulty";

function readDifficulty(): Difficulty {
  try {
    const stored = typeof window !== "undefined" ? window.localStorage.getItem(DIFFICULTY_KEY) : null;
    return stored === "easy" || stored === "hard" ? stored : "normal";
  } catch {
    return "normal";
  }
}

// Purely local UI state. Anything about the game itself lives in the agent's shared state.
export type MobileTab = "suspects" | "chat" | "board";

interface UiState {
  activeSuspectId: string | null;
  mobileTab: MobileTab;
  casePickerOpen: boolean;
  setCasePickerOpen: (open: boolean) => void;
  /** Last agent run error (CopilotKit reports these via onError, not by throwing from runAgent). */
  runError: string | null;
  setRunError: (message: string | null) => void;
  /** Difficulty for the next new game (remembered per browser). */
  difficulty: Difficulty;
  setDifficulty: (difficulty: Difficulty) => void;
  setActiveSuspect: (suspectId: string | null) => void;
  setMobileTab: (tab: MobileTab) => void;
}

export const useUi = create<UiState>((set) => ({
  activeSuspectId: null,
  mobileTab: "chat",
  casePickerOpen: false,
  setCasePickerOpen: (casePickerOpen) => set({ casePickerOpen }),
  runError: null,
  setRunError: (runError) => set({ runError }),
  difficulty: readDifficulty(),
  setDifficulty: (difficulty) => {
    try {
      window.localStorage.setItem(DIFFICULTY_KEY, difficulty);
    } catch {
      // Not remembered; still applies to this visit.
    }
    set({ difficulty });
  },
  setActiveSuspect: (activeSuspectId) => set({ activeSuspectId, mobileTab: "chat" }),
  setMobileTab: (mobileTab) => set({ mobileTab }),
}));
