import { create } from "zustand";

// Purely local UI state. Anything about the game itself lives in the agent's shared state.
export type MobileTab = "suspects" | "chat" | "board";

interface UiState {
  activeSuspectId: string | null;
  mobileTab: MobileTab;
  casePickerOpen: boolean;
  setCasePickerOpen: (open: boolean) => void;
  setActiveSuspect: (suspectId: string | null) => void;
  setMobileTab: (tab: MobileTab) => void;
}

export const useUi = create<UiState>((set) => ({
  activeSuspectId: null,
  mobileTab: "chat",
  casePickerOpen: false,
  setCasePickerOpen: (casePickerOpen) => set({ casePickerOpen }),
  setActiveSuspect: (activeSuspectId) => set({ activeSuspectId, mobileTab: "chat" }),
  setMobileTab: (mobileTab) => set({ mobileTab }),
}));
