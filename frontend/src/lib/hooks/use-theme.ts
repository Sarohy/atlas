'use client';

import { useEffect, useState } from 'react';
import { AUTH_THEME, type AtlasTheme } from '@/styles/theme';

const DEFAULT_THEME: AtlasTheme = 'dark';

function getSystemTheme(): AtlasTheme {
  const mediaQueryList =
    typeof window === 'undefined'
      ? undefined
      : window.matchMedia?.('(prefers-color-scheme: light)');
  return mediaQueryList?.matches ? 'light' : DEFAULT_THEME;
}

function getStoredTheme(): AtlasTheme | null {
  const storedTheme =
    typeof window === 'undefined' ? null : window.localStorage.getItem(AUTH_THEME.storageKey);
  return storedTheme === 'light' || storedTheme === 'dark' ? storedTheme : null;
}

export function useTheme() {
  const [theme, setTheme] = useState<AtlasTheme>(() => getStoredTheme() ?? getSystemTheme());

  useEffect(() => {
    window.localStorage.setItem(AUTH_THEME.storageKey, theme);
  }, [theme]);

  return {
    setTheme,
    theme,
    toggleTheme: () => setTheme((currentTheme) => (currentTheme === 'dark' ? 'light' : 'dark')),
  };
}
