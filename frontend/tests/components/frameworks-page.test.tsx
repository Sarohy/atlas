import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import FrameworksPage from '@/app/(atlas)/frameworks/page';
import { AuthSessionProvider } from '@/components/auth/auth-session-provider';

function wrapper(children: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <AuthSessionProvider>{children}</AuthSessionProvider>
    </QueryClientProvider>
  );
}

describe('Frameworks page', () => {
  async function renderPage() {
    render(wrapper(await FrameworksPage()));
  }

  it('renders the frameworks content area', async () => {
    await renderPage();

    expect(screen.getByTestId('atlas-frameworks-page')).toBeInTheDocument();
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
