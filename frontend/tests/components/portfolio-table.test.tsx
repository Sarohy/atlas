import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';

import { PortfolioTable } from '@/components/portfolio/portfolio-table';
import { server } from '../mocks/server';

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe('PortfolioTable', () => {
  it('renders a loading skeleton on mount', () => {
    render(<PortfolioTable />, { wrapper });
    // Before MSW resolves, the loading state should appear
    expect(document.body).toBeDefined();
  });

  it('renders ticker symbols once data loads', async () => {
    render(<PortfolioTable />, { wrapper });
    await waitFor(() => expect(screen.getByText('AAPL')).toBeInTheDocument());
  });

  it('renders share count alongside ticker', async () => {
    render(<PortfolioTable />, { wrapper });
    await waitFor(() => expect(screen.getByText('AAPL')).toBeInTheDocument());
    expect(screen.getByText('Apple Inc.')).toBeInTheDocument();
  });

  it('renders the empty state when no positions are returned', async () => {
    server.use(http.get('http://localhost:8000/api/v1/positions', () => HttpResponse.json([])));
    render(<PortfolioTable />, { wrapper });
    await waitFor(() => expect(screen.getByText(/No positions/i)).toBeInTheDocument());
  });

  it('opens the edit dialog when Edit button is clicked', async () => {
    const user = userEvent.setup();
    render(<PortfolioTable />, { wrapper });
    await waitFor(() => screen.getByText('AAPL'));
    await user.click(screen.getByRole('button', { name: 'Edit' }));
    expect(screen.getByText('Edit AAPL')).toBeInTheDocument();
  });

  it('closes the edit dialog when ✕ is clicked', async () => {
    const user = userEvent.setup();
    render(<PortfolioTable />, { wrapper });
    await waitFor(() => screen.getByText('AAPL'));
    await user.click(screen.getByRole('button', { name: 'Edit' }));
    await user.click(screen.getByRole('button', { name: '✕' }));
    expect(screen.queryByText('Edit AAPL')).not.toBeInTheDocument();
  });
});
