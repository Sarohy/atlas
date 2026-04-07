import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Home from '@/app/page';

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

describe('Home sign-in page', () => {
  beforeEach(() => {
    setViewportWidth(1280);
  });

  it('renders the ATLAS sign-in experience and hero artwork', () => {
    render(<Home />);

    expect(screen.getByTestId('atlas-auth-page')).toBeInTheDocument();
    expect(screen.getByText('ATLAS v7.0')).toBeInTheDocument();
    expect(screen.getByLabelText('Email address')).toBeInTheDocument();
    expect(screen.getByLabelText('Password')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Sign In' })).toBeInTheDocument();
    expect(screen.getByTestId('atlas-auth-page')).toHaveTextContent('Remember me');
    expect(screen.getByAltText('ATLAS market globe')).toHaveAttribute('src', '/atlas.svg');
  });

  it('uses the mobile layout at 1024px to avoid cropping the atlas hero artwork', () => {
    setViewportWidth(1024);

    render(<Home />);

    expect(screen.queryByAltText('ATLAS market globe')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Sign In' })).toBeInTheDocument();
    expect(screen.getByText('ATLAS v7.0')).toBeVisible();
  });

  it('validates email, toggles password visibility, remembers the user, and shows loading state', async () => {
    const user = userEvent.setup();

    render(<Home />);

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
});
