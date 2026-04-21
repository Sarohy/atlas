import { describe, expect, it } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AtlasActionsRail } from '@/components/atlas/atlas-chrome';
import { AuthSessionProvider } from '@/components/auth/auth-session-provider';
import PortfolioPage from '@/app/(atlas)/portfolio/page';
import { ATLAS_ACTIONS, ATLAS_ACTIONS_TITLE } from '@/lib/api/atlas-shell';

function wrapper(children: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <AuthSessionProvider>{children}</AuthSessionProvider>
    </QueryClientProvider>
  );
}

describe('Home portfolio page', () => {
  async function renderPage() {
    render(wrapper(await PortfolioPage()));
  }

  it('renders the portfolio main content area', async () => {
    await renderPage();

    expect(screen.getByTestId('atlas-portfolio-page')).toBeInTheDocument();
  });

  it('renders the portfolio holdings, analytics cards, and actions rail', async () => {
    await renderPage();

    // Live metric cards — wait for React Query to resolve MSW data
    await waitFor(() => {
      expect(screen.getByText('Total Portfolio')).toBeInTheDocument();
    });
    // "Cash Reserve" appears in both the metric card and the live cash panel heading
    expect(screen.getAllByText('Cash Reserve').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Portfolio Beta')).toBeInTheDocument();

    // Tickers panel
    expect(screen.getByText('All Tickers')).toBeInTheDocument();
    expect(screen.getByText('+ Add Ticker')).toBeInTheDocument();

    // Live cash panel
    expect(screen.getByText('Current Balance')).toBeInTheDocument();
  });

  it('replaces today actions with a coming soon placeholder', () => {
    render(wrapper(<AtlasActionsRail actions={ATLAS_ACTIONS} title={ATLAS_ACTIONS_TITLE} />));

    expect(screen.getByText("Today's Actions")).toBeInTheDocument();
    expect(screen.getByText('Coming soon...')).toBeInTheDocument();
    expect(screen.queryByText('HOLD CASH')).not.toBeInTheDocument();
    expect(screen.queryByText('SELL ANET')).not.toBeInTheDocument();
  });
});
