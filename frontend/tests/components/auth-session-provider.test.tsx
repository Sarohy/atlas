import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthGate } from '@/components/auth/auth-gate';
import { AuthSessionProvider, useAuthSession } from '@/components/auth/auth-session-provider';
import { AUTH_SESSION_STORAGE_KEY } from '@/lib/auth/session';

const replaceMock = vi.fn();
const pathnameState = {
  value: '/',
};

vi.mock('next/navigation', () => ({
  usePathname: () => pathnameState.value,
  useRouter: () => ({
    replace: replaceMock,
  }),
}));

function createStoredSession() {
  return JSON.stringify({
    email: 'admin@atlas.com',
    expiresAt: '2099-04-07T18:30:00.000Z',
    lastActivityAt: '2099-04-07T18:00:00.000Z',
    rememberMe: true,
  });
}

function TestProtectedPage() {
  return (
    <AuthSessionProvider>
      <AuthGate>
        <div>Protected portfolio content</div>
      </AuthGate>
    </AuthSessionProvider>
  );
}

function LogoutHarness() {
  const { isAuthenticated, signOut } = useAuthSession();

  return (
    <div>
      <span>{isAuthenticated ? 'Authenticated' : 'Anonymous'}</span>
      <button onClick={() => void signOut()} type="button">
        Logout
      </button>
    </div>
  );
}

function SessionHarness() {
  const { isAuthenticated, signIn } = useAuthSession();

  return (
    <div>
      <span>{isAuthenticated ? 'Authenticated' : 'Anonymous'}</span>
      <button
        onClick={() =>
          void signIn({
            email: 'admin@atlas.com',
            rememberMe: true,
          })
        }
        type="button"
      >
        Sign in
      </button>
    </div>
  );
}

describe('Auth session provider', () => {
  beforeEach(() => {
    pathnameState.value = '/';
    replaceMock.mockReset();
    window.localStorage.clear();
    vi.useRealTimers();
  });

  it('redirects unauthenticated users away from protected routes', async () => {
    render(<TestProtectedPage />);

    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith('/auth/sign-in');
    });
  });

  it('calls the logout api and clears the stored session', async () => {
    window.localStorage.setItem(AUTH_SESSION_STORAGE_KEY, createStoredSession());

    const user = userEvent.setup();

    render(
      <AuthSessionProvider>
        <LogoutHarness />
      </AuthSessionProvider>,
    );

    await user.click(screen.getByRole('button', { name: 'Logout' }));

    await waitFor(() => {
      expect(screen.getByText('Anonymous')).toBeInTheDocument();
    });
    expect(window.localStorage.getItem(AUTH_SESSION_STORAGE_KEY)).toBeNull();
  });

  it('logs the user out automatically after 30 minutes of inactivity', async () => {
    vi.useFakeTimers();

    render(
      <AuthSessionProvider>
        <SessionHarness />
      </AuthSessionProvider>,
    );

    expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    });

    expect(screen.getByText('Authenticated')).toBeInTheDocument();

    await act(async () => {
      vi.advanceTimersByTime(30 * 60 * 1000 + 1000);
    });

    expect(screen.getByText('Anonymous')).toBeInTheDocument();
  });

  it('refreshes the inactivity deadline when user activity happens', async () => {
    vi.useFakeTimers();

    render(
      <AuthSessionProvider>
        <SessionHarness />
      </AuthSessionProvider>,
    );

    expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    });

    await act(async () => {
      vi.advanceTimersByTime(29 * 60 * 1000);
      window.dispatchEvent(new MouseEvent('mousemove'));
      vi.advanceTimersByTime(2 * 60 * 1000);
    });

    expect(screen.getByText('Authenticated')).toBeInTheDocument();
  });

  it('redirects authenticated users away from the sign-in page', async () => {
    pathnameState.value = '/auth/sign-in';
    window.localStorage.setItem(AUTH_SESSION_STORAGE_KEY, createStoredSession());

    render(
      <AuthSessionProvider>
        <AuthGate>
          <div>Sign-in page</div>
        </AuthGate>
      </AuthSessionProvider>,
    );

    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith('/');
    });
  });
});
