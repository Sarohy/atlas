import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../mocks/server';
import { AuthSessionProvider } from '@/components/auth/auth-session-provider';
import SignInPage from '@/app/auth/sign-in/page';

function setViewportWidth(width: number) {
  Object.defineProperty(window, 'innerWidth', {
    configurable: true,
    value: width,
    writable: true,
  });

  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: vi.fn().mockImplementation((query: string) => {
      const maxWidthMatch = /^\(max-width: (\d+)px\)$/.exec(query);
      const matches = maxWidthMatch === null ? false : width <= Number(maxWidthMatch[1]);

      return {
        matches,
        media: query,
        onchange: null,
        addEventListener: vi.fn(),
        addListener: vi.fn(),
        dispatchEvent: vi.fn(),
        removeEventListener: vi.fn(),
        removeListener: vi.fn(),
      };
    }),
  });
}

describe('Sign-in page', () => {
  beforeEach(() => {
    setViewportWidth(1280);
  });

  function renderPage() {
    return render(
      <AuthSessionProvider>
        <SignInPage />
      </AuthSessionProvider>,
    );
  }

  it('renders the ATLAS sign-in experience and hero artwork', () => {
    renderPage();

    expect(screen.getByTestId('atlas-auth-page')).toBeInTheDocument();
    expect(screen.getByText('ATLAS v7.0')).toBeInTheDocument();
    expect(screen.getByLabelText('Email address')).toBeInTheDocument();
    expect(screen.getByLabelText('Password')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Sign In' })).toBeInTheDocument();
    expect(screen.getByTestId('atlas-auth-page')).toHaveTextContent('Remember me');
    expect(screen.getByAltText('ATLAS market globe')).toHaveAttribute('src', '/atlas.svg');
  });

  it('uses the figma-matched desktop hero background behind the atlas artwork', () => {
    const stylesheetPath = join(process.cwd(), 'src/styles/auth.css');
    const stylesheet = readFileSync(stylesheetPath, 'utf8');

    expect(stylesheet).toContain('--atlas-auth-hero-bg: #151b33;');
    expect(stylesheet).toContain('background: var(--atlas-auth-hero-bg);');
  });

  it('uses the mobile layout at 1024px to avoid cropping the atlas hero artwork', () => {
    setViewportWidth(1024);

    renderPage();

    expect(screen.queryByAltText('ATLAS market globe')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Sign In' })).toBeInTheDocument();
    expect(screen.getByText('ATLAS v7.0')).toBeVisible();
  });

  it('validates email, toggles password visibility, remembers the user, and shows loading state', async () => {
    const user = userEvent.setup();

    renderPage();

    await user.type(screen.getByLabelText('Email address'), 'invalid-email');
    await user.type(screen.getByLabelText('Password'), 'topsecret');
    await user.click(screen.getByRole('button', { name: 'Sign In' }));

    expect(screen.getByText('Enter a valid email address.')).toBeInTheDocument();

    await user.clear(screen.getByLabelText('Email address'));
    await user.type(screen.getByLabelText('Email address'), 'atlas@example.com');
    await user.click(screen.getByRole('button', { name: 'Show password' }));

    expect(screen.getByLabelText('Password')).toHaveAttribute('type', 'text');

    const rememberMe = screen.getByRole('checkbox', { name: 'Remember me' });
    const rememberMeLabel = screen.getByText('Remember me').closest('label');

    expect(rememberMe).not.toBeChecked();
    expect(rememberMeLabel).toHaveAttribute('data-state', 'unchecked');

    await user.click(rememberMe);

    expect(rememberMe).toBeChecked();
    expect(rememberMeLabel).toHaveAttribute('data-state', 'checked');

    await user.click(rememberMe);

    expect(rememberMe).not.toBeChecked();
    expect(rememberMeLabel).toHaveAttribute('data-state', 'unchecked');

    await user.click(screen.getByRole('button', { name: 'Sign In' }));

    expect(screen.getByRole('button', { name: 'Signing in' })).toBeDisabled();
    expect(screen.getByRole('status')).toHaveTextContent('Signing in');

    await waitFor(
      () => {
        expect(screen.getByRole('button', { name: 'Sign In' })).toBeEnabled();
      },
      { timeout: 2500 },
    );
  });

  it('submits valid credentials to the sign-in api and clears loading state on success', async () => {
    const user = userEvent.setup();

    renderPage();

    await user.type(screen.getByLabelText('Email address'), 'admin@atlas.com');
    await user.type(screen.getByLabelText('Password'), 'admin@123');
    await user.click(screen.getByRole('button', { name: 'Sign In' }));

    expect(screen.getByRole('button', { name: 'Signing in' })).toBeDisabled();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Sign In' })).toBeEnabled();
    });

    expect(screen.getByText('Sign in successful.')).toBeInTheDocument();
    expect(screen.getByText('Signed in as admin@atlas.com')).toBeInTheDocument();
    expect(screen.queryByText('Invalid email or password.')).not.toBeInTheDocument();
  });

  it('shows the api error message when sign-in fails', async () => {
    const user = userEvent.setup();
    server.use(
      http.post('http://localhost:8000/api/v1/auth/sign-in', () => {
        return HttpResponse.json({ detail: 'Invalid email or password.' }, { status: 401 });
      }),
    );

    renderPage();

    await user.type(screen.getByLabelText('Email address'), 'admin@atlas.com');
    await user.type(screen.getByLabelText('Password'), 'wrong-password');
    await user.click(screen.getByRole('button', { name: 'Sign In' }));

    await waitFor(() => {
      expect(screen.getByText('Invalid email or password.')).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: 'Sign In' })).toBeEnabled();
  });
});
