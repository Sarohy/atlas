import { create } from 'zustand';

type FrameworkStoreState = {
  /** Currently selected ticker driving all framework panels and the overview card. */
  activeTicker: string;
  setActiveTicker: (ticker: string) => void;
};

export const useFrameworkStore = create<FrameworkStoreState>((set) => ({
  activeTicker: '',
  setActiveTicker: (ticker) => set({ activeTicker: ticker }),
}));
