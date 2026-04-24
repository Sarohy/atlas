'use client';

import React from 'react';
import { useFramework19 } from '@/lib/hooks/use-framework19';
import type { Framework19Result, F19Status, AffectedHolding } from '@/lib/schemas/framework19';

// Framework 19 is portfolio-level — no ticker prop.
type Framework19CardProps = Record<string, never>;

// ── Status chip classes ───────────────────────────────────────────────────────

function statusClass(status: F19Status): string {
  switch (status) {
    case 'ACTIVE':
      return 'is-f19-active';
    case 'CLEAR':
      return 'is-f19-clear';
    case 'UNKNOWN':
      return 'is-f19-unknown';
    case 'OUTSIDE_HOURS':
    default:
      return 'is-f19-outside';
  }
}

function statusLabel(status: F19Status): string {
  switch (status) {
    case 'ACTIVE':
      return 'KILL SWITCH ACTIVE';
    case 'CLEAR':
      return 'CLEAR';
    case 'UNKNOWN':
      return 'UNKNOWN';
    case 'OUTSIDE_HOURS':
    default:
      return 'OUTSIDE HOURS';
  }
}

// ── NVDA drop progress bar ────────────────────────────────────────────────────

interface DropBarProps {
  dropPct: number | null;
  thresholdPct: number;
}

function DropBar({ dropPct, thresholdPct }: DropBarProps) {
  const pct = dropPct !== null && thresholdPct > 0
    ? Math.min(Math.round((dropPct / thresholdPct) * 100), 100)
    : 0;
  const isBreached = dropPct !== null && dropPct >= thresholdPct;

  return (
    <div className="atlas-f19-drop-bar-wrap">
      <div
        className={['atlas-f19-drop-bar-fill', isBreached ? 'is-breached' : ''].join(' ')}
        style={{ width: `${pct}%` }}
        role="progressbar"
        aria-valuenow={dropPct ?? 0}
        aria-valuemin={0}
        aria-valuemax={thresholdPct}
      />
      <div
        className="atlas-f19-drop-bar-threshold"
        style={{ left: '100%' }}
        aria-label={`Threshold: ${thresholdPct}%`}
      />
    </div>
  );
}

// ── Affected holdings row ─────────────────────────────────────────────────────

function HoldingRow({ holding }: { holding: AffectedHolding }) {
  return (
    <tr className={['atlas-f19-holding-row', holding.is_high_beta ? 'is-high-beta' : ''].join(' ')}>
      <td className="atlas-f19-holding-ticker">{holding.ticker}</td>
      <td className="atlas-f19-holding-beta">
        {holding.beta_vs_nvda !== null ? holding.beta_vs_nvda.toFixed(2) : '—'}
      </td>
      <td className="atlas-f19-holding-flag">
        {holding.is_high_beta ? (
          <span className="atlas-f19-badge is-high-beta">HIGH β</span>
        ) : (
          <span className="atlas-f19-badge is-normal-beta">Normal</span>
        )}
      </td>
      <td className="atlas-f19-holding-blocked">
        {holding.market_orders_blocked ? (
          <span className="atlas-f19-badge is-blocked">Market blocked</span>
        ) : (
          <span className="atlas-f19-badge is-clear">—</span>
        )}
      </td>
    </tr>
  );
}

// ── Main card ─────────────────────────────────────────────────────────────────

export function Framework19Card(_props: Framework19CardProps) {
  const { data, isLoading, isError, error } = useFramework19();

  if (isLoading) {
    return (
      <div className="atlas-f19-card">
        <div className="atlas-f19-loading">Loading Framework 19 — NVDA Kill Switch…</div>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="atlas-f19-card">
        <div className="atlas-f19-error">
          {error instanceof Error ? error.message : 'Framework 19 data unavailable'}
        </div>
      </div>
    );
  }

  const d: Framework19Result = data;

  return (
    <div className={['atlas-f19-card', statusClass(d.f19_status)].join(' ')}>

      {/* ── Section 1: Header ─────────────────────────────────────────── */}
      <div className="atlas-f19-header">
        <div className="atlas-f19-header-left">
          <span className="atlas-f19-title">F19 — NVDA Kill Switch</span>
          <span className="atlas-f19-session-date">{d.session_date}</span>
        </div>
        <div className="atlas-f19-header-right">
          <span className={['atlas-f19-status-chip', statusClass(d.f19_status)].join(' ')}>
            {statusLabel(d.f19_status)}
          </span>
          {d.severity && (
            <span className={['atlas-f19-severity-badge', `is-${d.severity.toLowerCase()}`].join(' ')}>
              {d.severity}
            </span>
          )}
        </div>
      </div>

      {/* ── Section 2: NVDA drop monitor ──────────────────────────────── */}
      <div className="atlas-f19-drop-section">
        <div className="atlas-f19-stat-grid">
          <div className="atlas-f19-stat">
            <span className="atlas-f19-stat-label">Current</span>
            <span className="atlas-f19-stat-value">
              {d.nvda_drop.current_price !== null
                ? `$${d.nvda_drop.current_price.toFixed(2)}`
                : 'N/A'}
            </span>
          </div>
          <div className="atlas-f19-stat">
            <span className="atlas-f19-stat-label">Peak ({d.nvda_drop.window_minutes ?? '—'}m)</span>
            <span className="atlas-f19-stat-value">
              {d.nvda_drop.peak_price_in_window !== null
                ? `$${d.nvda_drop.peak_price_in_window.toFixed(2)}`
                : 'N/A'}
            </span>
          </div>
          <div className={[
            'atlas-f19-stat',
            d.nvda_drop.threshold_breached ? 'is-breached' : ''
          ].join(' ')}>
            <span className="atlas-f19-stat-label">Drop</span>
            <span className="atlas-f19-stat-value">
              {d.nvda_drop.drop_pct !== null
                ? `${d.nvda_drop.drop_pct.toFixed(2)}%`
                : 'N/A'}
            </span>
          </div>
          <div className="atlas-f19-stat">
            <span className="atlas-f19-stat-label">Threshold</span>
            <span className="atlas-f19-stat-value">{d.nvda_drop.threshold_pct.toFixed(1)}%</span>
          </div>
        </div>
        <DropBar
          dropPct={d.nvda_drop.drop_pct}
          thresholdPct={d.nvda_drop.threshold_pct}
        />
      </div>

      {/* ── Section 3: Status panel ────────────────────────────────────── */}
      <div className={['atlas-f19-status-panel', statusClass(d.f19_status)].join(' ')}>
        {d.f19_status === 'ACTIVE' && (
          <p>
            <strong>Kill switch fired.</strong> NVDA dropped{' '}
            {d.nvda_drop.drop_pct !== null ? `${d.nvda_drop.drop_pct.toFixed(2)}%` : '—'} within{' '}
            {d.nvda_drop.window_minutes ?? '—'} minutes. All AI-correlated buy orders paused.
            High-beta market orders blocked.
          </p>
        )}
        {d.f19_status === 'CLEAR' && (
          <p>No qualifying NVDA drop detected this session. Orders may proceed normally.</p>
        )}
        {d.f19_status === 'UNKNOWN' && (
          <p>
            <strong>Data unavailable.</strong> NVDA price data could not be retrieved from
            Polygon.io. All AI-correlated buy orders are blocked as a conservative precaution.
          </p>
        )}
        {d.f19_status === 'OUTSIDE_HOURS' && (
          <p>Market session not active. F19 only monitors intraday (09:30–16:00 ET, weekdays).</p>
        )}
      </div>

      {/* ── Section 4: Affected holdings (only when triggered or unknown) */}
      {(d.f19_active === true || d.f19_active === null) && d.affected_holdings.length > 0 && (
        <div className="atlas-f19-holdings-section">
          <span className="atlas-f19-section-label">Affected Holdings</span>
          <table className="atlas-f19-holdings-table">
            <thead>
              <tr>
                <th>Ticker</th>
                <th>Beta vs NVDA</th>
                <th>Risk Flag</th>
                <th>Market Orders</th>
              </tr>
            </thead>
            <tbody>
              {d.affected_holdings.map((h) => (
                <HoldingRow key={h.ticker} holding={h} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Section 5: Alert status ────────────────────────────────────── */}
      <div className="atlas-f19-alert-row">
        <span className="atlas-f19-section-label">Alert</span>
        {d.alert_sent ? (
          <span className="atlas-f19-alert-sent">
            Sent at {d.alert_sent_at ? new Date(d.alert_sent_at).toLocaleTimeString() : '—'}
          </span>
        ) : (
          <span className="atlas-f19-alert-pending">—</span>
        )}
      </div>

      {/* ── Section 6: Session state ───────────────────────────────────── */}
      <div className="atlas-f19-session-row">
        <span className="atlas-f19-section-label">Session</span>
        <span className="atlas-f19-session-triggered">
          {d.triggered_at
            ? `Triggered at ${new Date(d.triggered_at).toLocaleTimeString()}`
            : 'Not triggered this session'}
        </span>
        <span className="atlas-f19-session-paused-count">
          {d.paused_orders_count > 0
            ? `${d.paused_orders_count} order${d.paused_orders_count === 1 ? '' : 's'} paused`
            : ''}
        </span>
      </div>

      {/* ── Section 7: Data source badges ─────────────────────────────── */}
      <div className="atlas-f19-footer">
        <div className="atlas-f19-data-badges">
          <span className={['atlas-f19-data-badge', d.polygon_available ? 'is-live' : 'is-unavailable'].join(' ')}>
            POLYGON {d.polygon_available ? '●' : '✕'}
          </span>
          <span className="atlas-f19-data-badge is-live">BETA DB ●</span>
          <span className="atlas-f19-data-badge is-live">ORDER DB ●</span>
          <span className={['atlas-f19-data-badge', d.regime_available ? 'is-live' : 'is-unavailable'].join(' ')}>
            F2 REGIME {d.regime_available ? '●' : '✕'}
          </span>
          <span className="atlas-f19-data-badge is-no-cache" title="NVDA price data is never cached — every evaluation fetches live data">
            LIVE DATA ONLY
          </span>
        </div>
        <span className="atlas-f19-footer-ts">
          {d.last_updated ? new Date(d.last_updated).toLocaleTimeString() : '—'}
        </span>
      </div>

      {/* Warning messages */}
      {d.warning_messages.length > 0 && (
        <div className="atlas-f19-warnings">
          {d.warning_messages.map((w, i) => (
            <div key={i} className="atlas-f19-warning-msg">{w}</div>
          ))}
        </div>
      )}

    </div>
  );
}
