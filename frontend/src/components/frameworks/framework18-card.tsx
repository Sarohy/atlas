'use client';

import React from 'react';
import { useFramework18, useRefreshFramework18 } from '@/lib/hooks/use-framework18';
import type { Framework18Result, F18Status } from '@/lib/schemas/framework18';

// Framework 18 is portfolio-level — no ticker prop.
type Framework18CardProps = Record<string, never>;

// ── Status chip colours ───────────────────────────────────────────────────────

function statusClass(status: F18Status): string {
  switch (status) {
    case 'ACTIVE':
      return 'is-f18-active';
    case 'CLEAR':
      return 'is-f18-clear';
    case 'UNKNOWN':
    default:
      return 'is-f18-unknown';
  }
}

function statusLabel(status: F18Status): string {
  switch (status) {
    case 'ACTIVE':
      return 'GATE ACTIVE';
    case 'CLEAR':
      return 'CLEAR';
    case 'UNKNOWN':
    default:
      return 'UNKNOWN';
  }
}

// ── SPY weekly close stat cell ────────────────────────────────────────────────

interface CloseStatProps {
  close: number | null;
  date: string | null;
  prevClose: number | null;
  label: string;
}

function CloseStat({ close, date, prevClose, label }: CloseStatProps) {
  const direction =
    close === null || prevClose === null
      ? null
      : close < prevClose
        ? 'down'
        : close > prevClose
          ? 'up'
          : 'flat';

  return (
    <div className="atlas-f18-close-stat">
      <span className="atlas-f18-close-stat-label">{label}</span>
      <span className="atlas-f18-close-stat-price">
        {close !== null ? `$${close.toFixed(2)}` : '—'}
      </span>
      <span
        className={[
          'atlas-f18-close-stat-arrow',
          direction === 'down'
            ? 'is-down'
            : direction === 'up'
              ? 'is-up'
              : 'is-flat',
        ].join(' ')}
      >
        {direction === 'down' ? '↓' : direction === 'up' ? '↑' : '—'}
      </span>
      <span className="atlas-f18-close-stat-date">
        {date ?? '—'}
      </span>
    </div>
  );
}

// ── Streak progress bar ───────────────────────────────────────────────────────

interface StreakBarProps {
  streak: number;
  threshold: number;
}

function StreakBar({ streak, threshold }: StreakBarProps) {
  const clamped = Math.min(streak, threshold);
  const pct = threshold > 0 ? Math.round((clamped / threshold) * 100) : 0;

  return (
    <div className="atlas-f18-streak-bar-wrap">
      <div
        className="atlas-f18-streak-bar-fill"
        style={{ width: `${pct}%` }}
        role="progressbar"
        aria-valuenow={streak}
        aria-valuemin={0}
        aria-valuemax={threshold}
      />
    </div>
  );
}

// ── Main card ─────────────────────────────────────────────────────────────────

export function Framework18Card(_props: Framework18CardProps) {
  const { data, isLoading, isError, error } = useFramework18();
  const refresh = useRefreshFramework18();

  if (isLoading) {
    return (
      <div className="atlas-f18-card">
        <div className="atlas-f18-loading">Loading Framework 18 — 4-Week Trend Gate…</div>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="atlas-f18-card">
        <div className="atlas-f18-error">
          {error instanceof Error ? error.message : 'Failed to load Framework 18 data.'}
        </div>
      </div>
    );
  }

  const d: Framework18Result = data;

  // Build SPY stat entries (closes are newest-first from the backend).
  const closeEntries = d.spy_weekly_closes.map((close, idx) => ({
    close,
    date: d.candle_dates[idx] ?? null,
    prevClose: d.spy_weekly_closes[idx + 1] ?? null,
    label: `W${idx + 1}`,
  }));

  const streak = d.consecutive_weeks_down ?? 0;
  const threshold = d.consecutive_threshold ?? 0;

  return (
    <div className={['atlas-f18-card', statusClass(d.f18_status)].join(' ')}>
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div className="atlas-f18-header">
        <div className="atlas-f18-header-left">
          <span className="atlas-f18-framework-label">FRAMEWORK 18</span>
          <span className="atlas-f18-title">4-Week Trend Gate</span>
        </div>
        <div className="atlas-f18-header-right">
          <span className={['atlas-f18-status-chip', statusClass(d.f18_status)].join(' ')}>
            {statusLabel(d.f18_status)}
          </span>
          {d.cache_hit && (
            <span className="atlas-f18-cache-badge" title={`Cached. Last evaluated: ${d.last_updated}`}>
              CACHED
            </span>
          )}
        </div>
      </div>

      {/* ── SPY weekly closes panel ──────────────────────────────────────── */}
      <div className="atlas-f18-closes-panel">
        <div className="atlas-f18-closes-label">SPY Weekly Closes (newest first)</div>
        <div className="atlas-f18-closes-grid">
          {d.spy_data_available && closeEntries.length > 0
            ? closeEntries.map((entry) => (
                <CloseStat
                  key={entry.label}
                  close={entry.close}
                  date={entry.date}
                  prevClose={entry.prevClose}
                  label={entry.label}
                />
              ))
            : Array.from({ length: 4 }, (_, i) => (
                <CloseStat
                  key={`empty-${i}`}
                  close={null}
                  date={null}
                  prevClose={null}
                  label={`W${i + 1}`}
                />
              ))}
        </div>
        {d.spy_data_stale && (
          <div className="atlas-f18-stale-badge">⚠ STALE DATA — Polygon.io unavailable</div>
        )}
      </div>

      {/* ── Trend status panel ───────────────────────────────────────────── */}
      <div className={['atlas-f18-trend-panel', statusClass(d.f18_status)].join(' ')}>
        <div className="atlas-f18-streak-row">
          <span className="atlas-f18-streak-label">Consecutive down weeks</span>
          <span className="atlas-f18-streak-count">
            {d.consecutive_weeks_down !== null ? d.consecutive_weeks_down : '—'}
            {threshold > 0 && d.consecutive_weeks_down !== null && (
              <span className="atlas-f18-streak-threshold"> / {threshold} threshold</span>
            )}
          </span>
        </div>
        {d.consecutive_threshold !== null && d.consecutive_weeks_down !== null && (
          <StreakBar streak={streak} threshold={threshold} />
        )}
      </div>

      {/* ── Actions panel (only when active) ────────────────────────────── */}
      {d.f18_active === true && d.actions !== null && (
        <div className="atlas-f18-actions-panel">
          <div className="atlas-f18-actions-label">Gate Restrictions</div>
          <div className="atlas-f18-actions-chips">
            {d.actions.no_speculative_starters && (
              <span className="atlas-f18-action-chip is-block">No new positions</span>
            )}
            {d.actions.tier3_adds_blocked && (
              <span className="atlas-f18-action-chip is-block">Tier 3 blocked</span>
            )}
            {d.actions.reduce_aggressive_adds && (
              <span className="atlas-f18-action-chip is-reduce">
                Adds reduced {d.actions.add_reduction_pct.toFixed(0)}%
              </span>
            )}
            {d.actions.prioritize_quality_only && (
              <span className="atlas-f18-action-chip is-quality">Quality only</span>
            )}
            <span className="atlas-f18-action-chip is-info">
              Min tier: {d.actions.min_tier_for_new_adds}
            </span>
          </div>
        </div>
      )}

      {/* ── Factor 9 impact ──────────────────────────────────────────────── */}
      {d.factor9_contribution !== null && (
        <div className="atlas-f18-factor9-row">
          <span className="atlas-f18-factor9-label">Factor 9 (Regime Fit)</span>
          <span className="atlas-f18-factor9-value">{d.factor9_contribution}</span>
        </div>
      )}

      {/* ── Warnings ─────────────────────────────────────────────────────── */}
      {d.warning_messages.length > 0 && (
        <ul className="atlas-f18-warnings">
          {d.warning_messages.map((msg, i) => (
            <li key={i} className="atlas-f18-warning-item">
              {msg}
            </li>
          ))}
        </ul>
      )}

      {/* ── Data sources & footer ─────────────────────────────────────────── */}
      <div className="atlas-f18-footer">
        <div className="atlas-f18-sources">
          <span
            className={[
              'atlas-f18-source-badge',
              d.polygon_available ? 'is-live' : 'is-unavailable',
            ].join(' ')}
          >
            POLYGON
          </span>
          {d.spy_data_stale && (
            <span className="atlas-f18-source-badge is-stale">STALE CACHE</span>
          )}
          {!d.spy_data_available && (
            <span className="atlas-f18-source-badge is-unavailable">NO DATA</span>
          )}
        </div>
        <div className="atlas-f18-footer-right">
          <button
            className="atlas-f18-refresh-btn"
            onClick={() => refresh.mutate()}
            disabled={refresh.isPending}
            title="Force re-fetch from Polygon.io"
          >
            {refresh.isPending ? 'Refreshing…' : 'Refresh'}
          </button>
          <span className="atlas-f18-footer-ts">
            {d.last_updated ? new Date(d.last_updated).toLocaleTimeString() : '—'}
          </span>
        </div>
      </div>
    </div>
  );
}
