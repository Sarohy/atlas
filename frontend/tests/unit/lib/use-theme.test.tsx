import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useTheme } from '@/lib/hooks/use-theme';
import { AUTH_THEME } from '@/styles/theme';

type MatchMediaConfig = {
  matches: boolean;
  withImplementation?: boolean;
};

function mockMatchMedia({ matches, withImplementation = true }: MatchMediaConfig) {
  if (!withImplementation) {
    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      value: undefined,
    });
    return;
  }

  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      addListener: vi.fn(),
      dispatchEvent: vi.fn(),
      removeEventListener: vi.fn(),
      removeListener: vi.fn(),
    })),
  });
}

function ThemeHarness() {
  const { setTheme, theme, toggleTheme } = useTheme();

  return (
    <div>
      <span>{theme}</span>
      <button onClick={toggleTheme} type="button">
        toggle theme
      </button>
      <button onClick={() => setTheme('dark')} type="button">
        set dark
      </button>
    </div>
  );
}

describe('useTheme', () => {
  beforeEach(() => {
    window.localStorage.clear();
    mockMatchMedia({ matches: false });
  });

  it('uses the stored theme when available', () => {
    window.localStorage.setItem(AUTH_THEME.storageKey, 'light');

    render(<ThemeHarness />);

    expect(screen.getByText('light')).toBeInTheDocument();
    expect(window.localStorage.getItem(AUTH_THEME.storageKey)).toBe('light');
  });

  it('falls back to the system theme when nothing is stored', () => {
    mockMatchMedia({ matches: true });

    render(<ThemeHarness />);

    expect(screen.getByText('light')).toBeInTheDocument();
  });

  it('falls back to dark when matchMedia is unavailable and toggles persist', async () => {
    const user = userEvent.setup();
    mockMatchMedia({ matches: false, withImplementation: false });
    window.localStorage.setItem(AUTH_THEME.storageKey, 'invalid');

    render(<ThemeHarness />);

    expect(screen.getByText('dark')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'toggle theme' }));

    expect(screen.getByText('light')).toBeInTheDocument();
    expect(window.localStorage.getItem(AUTH_THEME.storageKey)).toBe('light');

    await user.click(screen.getByRole('button', { name: 'set dark' }));

    expect(screen.getByText('dark')).toBeInTheDocument();
    expect(window.localStorage.getItem(AUTH_THEME.storageKey)).toBe('dark');
  });
});
