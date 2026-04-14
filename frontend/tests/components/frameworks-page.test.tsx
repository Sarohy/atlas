import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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

  it('renders the overview and analysis panels without the legacy rule cards', async () => {
    await renderPage();

    expect(screen.getByText('Initial Catalyst')).toBeInTheDocument();
    expect(screen.getByTestId('framework-initial-catalyst-select')).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Yes' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'No' })).toBeInTheDocument();
    expect(screen.getByTestId('frameworks-panels-section')).toBeInTheDocument();
    expect(screen.getByTestId('frameworks-ticker-bar')).toBeInTheDocument();
    expect(screen.getByTestId('framework-score-panel')).toHaveClass('atlas-fws-panel--half-width');
    expect(screen.getByTestId('regime-guidance-panel')).toBeInTheDocument();
    expect(screen.getByText('Framework 3')).toBeInTheDocument();
    expect(screen.getByTestId('framework-score-hover-overlay')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Preview framework score details' })).toBeInTheDocument();
    expect(screen.queryByText('F1 Momentum')).not.toBeInTheDocument();
    expect(screen.queryByText('F2 Earnings Quality')).not.toBeInTheDocument();
    expect(screen.queryByText('F3 Analyst Conviction')).not.toBeInTheDocument();
    expect(screen.queryByText('F4 Options Flow')).not.toBeInTheDocument();
    expect(screen.queryByText('F5 Fundamental Quality')).not.toBeInTheDocument();
    expect(screen.queryByText('#1 VIX Regime Gate')).not.toBeInTheDocument();
    expect(screen.queryByText('#17 Geopolitical Monitor')).not.toBeInTheDocument();
    expect(screen.queryByText('#31 Data Oracle')).not.toBeInTheDocument();
    expect(screen.queryByText('Scenario Router')).not.toBeInTheDocument();
    expect(screen.queryByText('Live Diplomatic Signals')).not.toBeInTheDocument();
    expect(screen.queryByText('DEAL / EXTENSION')).not.toBeInTheDocument();
    expect(screen.queryByText('ESCALATION')).not.toBeInTheDocument();
  });

  it('opens a framework details overlay when the framework score eye icon is clicked', async () => {
    const user = userEvent.setup();

    await renderPage();

    await user.click(screen.getByRole('button', { name: 'Preview framework score details' }));

    const overlay = screen.getByRole('dialog', { name: 'Framework detail cards' });
    const overlayContent = within(overlay);

    expect(overlay).toBeInTheDocument();
    expect(overlayContent.getByText('Framework Detail Cards')).toBeInTheDocument();
    expect(overlayContent.getByText('F1 Momentum')).toBeInTheDocument();
    expect(overlayContent.getByText('F2 Earnings Quality')).toBeInTheDocument();
    expect(overlayContent.getByText('F3 Analyst Conviction')).toBeInTheDocument();
    expect(overlayContent.getByText('F4 Options Flow')).toBeInTheDocument();
    expect(overlayContent.getByText('F5 Fundamental Quality')).toBeInTheDocument();
  });

  it('reveals the eye on hover and opens the detail cards only after clicking it', async () => {
    const user = userEvent.setup();

    await renderPage();

    await user.hover(screen.getByTestId('framework-score-panel'));

    expect(
      screen.queryByRole('dialog', { name: 'Framework detail cards' }),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Preview framework score details' }));

    const overlay = screen.getByRole('dialog', { name: 'Framework detail cards' });
    const overlayContent = within(overlay);

    expect(overlay).toBeInTheDocument();
    expect(overlayContent.getByText('F1 Momentum')).toBeInTheDocument();
    expect(overlayContent.getByText('F2 Earnings Quality')).toBeInTheDocument();
    expect(overlayContent.getByText('F3 Analyst Conviction')).toBeInTheDocument();
    expect(overlayContent.getByText('F4 Options Flow')).toBeInTheDocument();
    expect(overlayContent.getByText('F5 Fundamental Quality')).toBeInTheDocument();
  });
});
