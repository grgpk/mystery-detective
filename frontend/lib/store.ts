import { create } from "zustand";

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
  setActiveSuspect: (activeSuspectId) => set({ activeSuspectId, mobileTab: "chat" }),
  setMobileTab: (mobileTab) => set({ mobileTab }),
}));
