import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi, afterEach } from 'vitest';
import { http, HttpResponse } from 'msw';

import { server } from '../mocks/server';
import { LiveCashPanel, LiveMetricsGrid } from '@/components/atlas/atlas-chrome';

function makeWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  }
  return Wrapper;
}

afterEach(() => vi.clearAllMocks());

// ── LiveMetricsGrid ──────────────────────────────────────────────────────────

describe('LiveMetricsGrid', () => {
  it('renders a loading skeleton while fetching', () => {
    // Delay the response so skeleton is visible
    server.use(
      http.get('http://localhost:8000/api/v1/portfolio/summary', async () => {
        await new Promise(() => {}); // never resolves in this test
      }),
    );
    render(<LiveMetricsGrid />, { wrapper: makeWrapper() });
    // Skeleton articles should be present; none of the live labels yet
    expect(screen.queryByText('Total Portfolio')).not.toBeInTheDocument();
  });

  it('renders live metric cards from the MSW summary', async () => {
    render(<LiveMetricsGrid />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByText('Total Portfolio')).toBeInTheDocument();
    });
    expect(screen.getByText('Cash Reserve')).toBeInTheDocument();
    expect(screen.getByText('Portfolio Beta')).toBeInTheDocument();
    // Values from MSW handler (total_nav = 23900000)
    expect(screen.getByText('$23.90M')).toBeInTheDocument();
  });
});

// ── LiveCashPanel ────────────────────────────────────────────────────────────

describe('LiveCashPanel', () => {
  it('renders the current balance from the MSW summary', async () => {
    render(<LiveCashPanel />, { wrapper: makeWrapper() });
    await waitFor(() => {
      // cash_balance = 3585000 → $3.58M
      expect(screen.getByText(/\$3\.\d+M/)).toBeInTheDocument();
    });
    expect(screen.getByLabelText('Cash adjustment amount')).toBeInTheDocument();
  });

  it('submit button is disabled when delta input is empty', async () => {
    render(<LiveCashPanel />, { wrapper: makeWrapper() });
    const submitBtn = screen.getByRole('button', { name: /Apply cash adjustment/ });
    expect(submitBtn).toBeDisabled();
  });

  it('calls POST /api/v1/portfolio/cash/adjust when the form is submitted', async () => {
    let postCalled = false;
    server.use(
      http.post('http://localhost:8000/api/v1/portfolio/cash/adjust', () => {
        postCalled = true;
        return HttpResponse.json({ cash_balance: 3985000, cash_floor_pct: 0.1 });
      }),
    );
    const user = userEvent.setup();
    render(<LiveCashPanel />, { wrapper: makeWrapper() });

    await waitFor(() => screen.getByLabelText('Cash adjustment amount'));

    await user.type(screen.getByLabelText('Cash adjustment amount'), '400000');
    await act(async () => {
      await user.click(screen.getByRole('button', { name: /Apply cash adjustment/ }));
    });

    await waitFor(() => expect(postCalled).toBe(true));
  });

  it('accepts a negative delta to subtract from cash', async () => {
    let requestBody: unknown;
    server.use(
      http.post('http://localhost:8000/api/v1/portfolio/cash/adjust', async ({ request }) => {
        requestBody = await request.json();
        return HttpResponse.json({ cash_balance: 3555000, cash_floor_pct: 0.1 });
      }),
    );
    const user = userEvent.setup();
    render(<LiveCashPanel />, { wrapper: makeWrapper() });

    await waitFor(() => screen.getByLabelText('Cash adjustment amount'));

    await user.type(screen.getByLabelText('Cash adjustment amount'), '-30000');
    await act(async () => {
      await user.click(screen.getByRole('button', { name: /Apply cash adjustment/ }));
    });

    await waitFor(() => {
      expect((requestBody as Record<string, unknown>).delta).toBe(-30000);
    });
  });

  it('shows an error message when POST fails', async () => {
    server.use(
      http.post('http://localhost:8000/api/v1/portfolio/cash/adjust', () => {
        return HttpResponse.json({ detail: 'Server error' }, { status: 500 });
      }),
    );
    const user = userEvent.setup();
    render(<LiveCashPanel />, { wrapper: makeWrapper() });

    await waitFor(() => screen.getByLabelText('Cash adjustment amount'));

    await user.type(screen.getByLabelText('Cash adjustment amount'), '9999999');
    await act(async () => {
      await user.click(screen.getByRole('button', { name: /Apply cash adjustment/ }));
    });

    await waitFor(() => {
      expect(screen.getByText(/Server error|Failed to update/i)).toBeInTheDocument();
    });
  });
});
