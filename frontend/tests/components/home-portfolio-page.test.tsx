import { describe, expect, it } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthSessionProvider } from '@/components/auth/auth-session-provider';
import PortfolioPage from '@/app/(atlas)/portfolio/page';

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
    expect(screen.getByText('Edit Tickers')).toBeInTheDocument();

    // Live cash panel
    expect(screen.getByText('Current Balance')).toBeInTheDocument();
  });
});
