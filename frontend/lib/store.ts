import { create } from "zustand";

import type { Difficulty } from "@/lib/protocol/types";

const DIFFICULTY_KEY = "last-alibi:difficulty";
const THEME_KEY = "last-alibi:theme";

function readStored(key: string): string | null {
  try {
    return typeof window !== "undefined"
      ? window.localStorage.getItem(key)
      : null;
  } catch {
    return null;
  }
}

function store(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Not remembered; still applies to this visit.
  }
}

function readDifficulty(): Difficulty {
  const stored = readStored(DIFFICULTY_KEY);
  return stored === "easy" || stored === "hard" ? stored : "normal";
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
  /** Theme for the next brand-new (generated) mystery (remembered per browser). */
  theme: string;
  setTheme: (theme: string) => void;
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
    store(DIFFICULTY_KEY, difficulty);
    set({ difficulty });
  },
  theme: readStored(THEME_KEY) ?? "golden_age",
  setTheme: (theme) => {
    store(THEME_KEY, theme);
    set({ theme });
  },
  setActiveSuspect: (activeSuspectId) =>
    set({ activeSuspectId, mobileTab: "chat" }),
  setMobileTab: (mobileTab) => set({ mobileTab }),
}));
