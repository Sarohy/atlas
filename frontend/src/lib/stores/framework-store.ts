import { create } from 'zustand';

type FrameworkStoreState = {
  /** Currently selected ticker driving all framework panels and the overview card. */
  activeTicker: string;
  setActiveTicker: (ticker: string) => void;
  /**
   * The exact score the investor sees on the F1 panel:
   * final_score (re-computed from live factor hooks) + regime modifier, clamped 0-100.
   * Written by FrameworkScorePanel; read by F6, F7, and any other panel that needs
   * the same value to avoid a discrepancy.
   */
  f1DisplayScore: number | undefined;
  setF1DisplayScore: (score: number | undefined) => void;
};

export const useFrameworkStore = create<FrameworkStoreState>((set) => ({
  activeTicker: '',
  setActiveTicker: (ticker) => set({ activeTicker: ticker }),
  f1DisplayScore: undefined,
  setF1DisplayScore: (score) => set({ f1DisplayScore: score }),
}));
