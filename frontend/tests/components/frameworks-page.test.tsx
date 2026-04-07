import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import FrameworksPage from '@/app/frameworks/page';
import { AuthSessionProvider } from '@/components/auth/auth-session-provider';

describe('Frameworks page', () => {
  async function renderPage() {
    render(<AuthSessionProvider>{await FrameworksPage()}</AuthSessionProvider>);
  }

  it('renders the frameworks shell with the frameworks nav item active', async () => {
    await renderPage();

    expect(screen.getByTestId('atlas-frameworks-page')).toBeInTheDocument();
    expect(screen.getByText('ATLAS v7.0')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Frameworks' })).toHaveAttribute(
      'aria-current',
      'page',
    );
    expect(screen.getByRole('link', { name: 'Daily Briefing' })).not.toHaveAttribute(
      'aria-current',
      'page',
    );
    expect(screen.getByRole('link', { name: 'Portfolio' })).not.toHaveAttribute(
      'aria-current',
      'page',
    );
    expect(screen.getByText('Logout')).toBeInTheDocument();
  });

  it('renders regime cards, framework cards, and trigger scenarios', async () => {
    await renderPage();

    expect(screen.getByText('VIX Regime')).toBeInTheDocument();
    expect(screen.getByText('VIX 25.33 · declining from 30+')).toBeInTheDocument();
    expect(screen.getByText('#1 VIX Regime Gate')).toBeInTheDocument();
    expect(screen.getByText('#17 Geopolitical Monitor')).toBeInTheDocument();
    expect(screen.getByText('#31 Data Oracle')).toBeInTheDocument();
    expect(screen.queryByText('Scenario Router')).not.toBeInTheDocument();
    expect(screen.queryByText('Live Diplomatic Signals')).not.toBeInTheDocument();
    expect(screen.queryByText('DEAL / EXTENSION')).not.toBeInTheDocument();
    expect(screen.queryByText('ESCALATION')).not.toBeInTheDocument();
  });
});
