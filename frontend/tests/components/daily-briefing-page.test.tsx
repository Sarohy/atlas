import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AuthSessionProvider } from '@/components/auth/auth-session-provider';
import DailyBriefingPage from '@/app/daily-briefing/page';

describe('Daily briefing page', () => {
  async function renderPage() {
    render(<AuthSessionProvider>{await DailyBriefingPage()}</AuthSessionProvider>);
  }

  it('renders the daily briefing shell with the daily briefing nav item active', async () => {
    await renderPage();

    expect(screen.getByTestId('atlas-daily-briefing-page')).toBeInTheDocument();
    expect(screen.getByText('ATLAS v7.0')).toBeInTheDocument();
    expect(screen.getByText('Daily Briefing')).toHaveAttribute('aria-current', 'page');
    expect(screen.getByText('Portfolio')).not.toHaveAttribute('aria-current', 'page');
    expect(screen.getByText('Frameworks')).toBeInTheDocument();
    expect(screen.getByText('Logout')).toBeInTheDocument();
  });

  it('renders the daily briefing question sets, pro forma table, and deploy plan', async () => {
    await renderPage();

    expect(screen.getByText(/Morning Briefing/i)).toBeInTheDocument();
    expect(screen.getByText('DO NOT BUY TODAY')).toBeInTheDocument();

    expect(screen.getByText('Q1 — What do I own and is anything broken?')).toBeInTheDocument();
    expect(screen.getByText('Q2 — What should I buy today?')).toBeInTheDocument();
    expect(screen.getByText('Q3 — What should I sell or trim today?')).toBeInTheDocument();
    expect(screen.getByText('Q4 — Pro forma after all actions')).toBeInTheDocument();
    expect(screen.getByText('Q5 — What changes this today?')).toBeInTheDocument();

    expect(screen.getByText('Post-Saturday Deploy Plan')).toBeInTheDocument();
    expect(screen.getByText('Phase 1 · Iran deal')).toBeInTheDocument();
    expect(screen.getByText('Phase 1 · score 92')).toBeInTheDocument();
    expect(screen.getByText('LITE+')).toBeInTheDocument();
  });
});
