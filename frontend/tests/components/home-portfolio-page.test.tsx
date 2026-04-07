import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AuthSessionProvider } from '@/components/auth/auth-session-provider';
import Home from '@/app/page';

describe('Home portfolio page', () => {
  async function renderPage() {
    render(<AuthSessionProvider>{await Home()}</AuthSessionProvider>);
  }

  it('renders the portfolio workspace shell and primary navigation', async () => {
    await renderPage();

    expect(screen.getByTestId('atlas-portfolio-page')).toBeInTheDocument();
    expect(screen.getByText('ATLAS v7.0')).toBeInTheDocument();
    expect(screen.getByText('Daily Briefing')).toBeInTheDocument();
    expect(screen.getByText('Portfolio')).toBeInTheDocument();
    expect(screen.getByText('Frameworks')).toBeInTheDocument();
    expect(screen.getByText('Logout')).toBeInTheDocument();
  });

  it('renders the portfolio holdings, analytics cards, and actions rail', async () => {
    await renderPage();

    expect(screen.getByText('Holdings — AI Core')).toBeInTheDocument();
    expect(screen.getByText('MU')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Cash' })).toBeInTheDocument();

    expect(screen.getByText('Total Portfolio')).toBeInTheDocument();
    expect(screen.getByText('Cash Reserve')).toBeInTheDocument();
    expect(screen.getByText('Portfolio Beta')).toBeInTheDocument();
    expect(screen.getByText('Optics Cluster')).toBeInTheDocument();

    expect(screen.getByText('All Tickers')).toBeInTheDocument();
    expect(screen.getByText('Edit Tickers')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Add Cash' })).toBeInTheDocument();
    expect(screen.getByText('Current Balance')).toBeInTheDocument();

    expect(screen.getByText("Today's Actions")).toBeInTheDocument();
    expect(screen.getByText('Portfolio Summary')).toBeInTheDocument();
    expect(screen.getByText('HOLD CASH')).toBeInTheDocument();
    expect(screen.getByText('SELL ANET')).toBeInTheDocument();
  });
});
