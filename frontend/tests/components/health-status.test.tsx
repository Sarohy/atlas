import { describe, expect, it } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { http, HttpResponse } from 'msw';
import { server } from '../mocks/server';
import { HealthStatus } from '@/components/health-status';

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe('HealthStatus', () => {
  it('renders a loading state initially', () => {
    const { unmount } = render(<HealthStatus />, { wrapper: createWrapper() });
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
    unmount();
  });

  it('renders "Backend: ok" after successful fetch', async () => {
    render(<HealthStatus />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText('Backend: ok')).toBeInTheDocument();
    });
  });

  it('renders an error state when the server returns 500', async () => {
    server.use(
      http.get('http://localhost:8000/api/v1/health', () => {
        return HttpResponse.json({ error: 'Internal Server Error' }, { status: 500 });
      }),
    );
    render(<HealthStatus />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText(/error/i)).toBeInTheDocument();
    });
  });
});
