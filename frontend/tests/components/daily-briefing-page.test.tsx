import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthSessionProvider } from '@/components/auth/auth-session-provider';
import DailyBriefingPage from '@/app/(atlas)/daily-briefing/page';

function wrapper(children: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <AuthSessionProvider>{children}</AuthSessionProvider>
    </QueryClientProvider>
  );
}

describe('Daily briefing page', () => {
  async function renderPage() {
    render(wrapper(await DailyBriefingPage()));
  }

  it('renders the daily briefing content area', async () => {
    await renderPage();

    expect(screen.getByTestId('atlas-daily-briefing-page')).toBeInTheDocument();
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

  it('styles daily briefing question headings with the figma cyan accent', () => {
    const stylesheetPath = join(process.cwd(), 'src/styles/daily-briefing.css');
    const stylesheet = readFileSync(stylesheetPath, 'utf8');

    expect(stylesheet).toContain('.atlas-briefing-question');
    expect(stylesheet).toContain('color: #38bdf8;');
  });

  it('renders the Framework 2 geopolitical gate controls in the morning briefing', async () => {
    await renderPage();

    expect(screen.getByText('Framework 2 Geopolitical Gate')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'None' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'De-escalating' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Active risk' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Resolved' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Escalating' })).toBeInTheDocument();
  });
});
