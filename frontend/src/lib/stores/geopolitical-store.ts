import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';

import type { GeopoliticalState } from '@/lib/schemas/regime-modifier';

const GEOPOLITICAL_STORAGE_KEY = 'atlas-geopolitical-state';
const DEFAULT_GEOPOLITICAL_STATE: GeopoliticalState = 'NONE';

type GeopoliticalStoreState = {
  geopoliticalState: GeopoliticalState;
  setGeopoliticalState: (state: GeopoliticalState) => void;
};

export const useGeopoliticalStore = create<GeopoliticalStoreState>()(
  persist(
    (set) => ({
      geopoliticalState: DEFAULT_GEOPOLITICAL_STATE,
      setGeopoliticalState: (geopoliticalState) => set({ geopoliticalState }),
    }),
    {
      name: GEOPOLITICAL_STORAGE_KEY,
      storage: createJSONStorage(() => localStorage),
    },
  ),
);
