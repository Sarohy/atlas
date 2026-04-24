'use client';

import { cn } from '@/lib/utils';
import { useSection16 } from '@/lib/hooks/use-section16';
import type {
  AppreciationStatus,
  GapDownStatus,
  PutProtectionStatus,
  Rule161Result,
  Rule161Status,
  Rule162Result,
  Rule163Result,
  Rule164Result,
  Section16OverallStatus,
  Section16Result,
} from '@/lib/schemas/section16';

// ---------------------------------------------------------------------------
// Named constants — status tone map (reuses global atlas tone classes)
// ---------------------------------------------------------------------------

/** Overall status chip labels. */
const OVERALL_LABEL: Record<Section16OverallStatus, string> = {
  ALL_CLEAR: 'ALL CLEAR',
  EXIT_ACTIVE: 'EXIT ACTIVE',
  PARTIAL_DATA: 'PARTIAL DATA',
  UNKNOWN: 'UNKNOWN',
};

/** Overall status chip tone — uses shared atlas tone palette. */
const OVERALL_TONE: Record<Section16OverallStatus, string> = {
  ALL_CLEAR: 'is-green',
  EXIT_ACTIVE: 'is-red',
  PARTIAL_DATA: 'is-yellow',
  UNKNOWN: 'is-gray',
};

const RULE161_LABEL: Record<Rule161Status, string> = {
  CLEAR: 'CLEAR',
  CYCLE_ONE: 'CYCLE ONE — WATCH',
  CYCLE_ONE_PAUSED: 'CYCLE ONE — PAUSED',
  CYCLE_TWO: 'CYCLE TWO — TRIM TRIGGERED',
  DEFERRED: 'DEFERRED',
  TRIM_TRIGGERED: 'TRIM EXECUTED',
  FULL_EXIT_TRIGGERED: 'FULL EXIT TRIGGERED',
  UNKNOWN: 'DATA UNAVAILABLE',
};

const RULE161_TONE: Record<Rule161Status, string> = {
  CLEAR: 'is-green',
  CYCLE_ONE: 'is-yellow',
  CYCLE_ONE_PAUSED: 'is-orange',
  CYCLE_TWO: 'is-red',
  DEFERRED: 'is-orange',
  TRIM_TRIGGERED: 'is-red',
  FULL_EXIT_TRIGGERED: 'is-red',
  UNKNOWN: 'is-gray',
};

const RULE162_LABEL: Record<GapDownStatus, string> = {
  CLEAR: 'CLEAR',
  HOLDING: '48-HR HOLD ACTIVE',
  RESCORED: 'RESCORED',
  RESOLVED: 'RESOLVED',
  UNKNOWN: 'DATA UNAVAILABLE',
};

const RULE162_TONE: Record<GapDownStatus, string> = {
  CLEAR: 'is-green',
  HOLDING: 'is-red',
  RESCORED: 'is-yellow',
  RESOLVED: 'is-green',
  UNKNOWN: 'is-gray',
};

const RULE163_LABEL: Record<AppreciationStatus, string> = {
  CLEAR: 'CLEAR',
  NO_NEW_CAPITAL: 'NO NEW CAPITAL',
  CONSIDER_TRIM: 'CONSIDER TRIM',
  UNKNOWN: 'DATA UNAVAILABLE',
};

const RULE163_TONE: Record<AppreciationStatus, string> = {
  CLEAR: 'is-green',
  NO_NEW_CAPITAL: 'is-yellow',
  CONSIDER_TRIM: 'is-red',
  UNKNOWN: 'is-gray',
};

const RULE164_LABEL: Record<PutProtectionStatus, string> = {
  PUT_PROTECTION_RECOMMENDED: 'BUY PUTS',
  NOT_TRIGGERED: 'NOT TRIGGERED',
  UNKNOWN: 'DATA UNAVAILABLE',
};

const RULE164_TONE: Record<PutProtectionStatus, string> = {
  PUT_PROTECTION_RECOMMENDED: 'is-red',
  NOT_TRIGGERED: 'is-green',
  UNKNOWN: 'is-gray',
};

// ---------------------------------------------------------------------------
// Formatters
// ---------------------------------------------------------------------------

const EM_DASH = '—';

function fmtStr(val: string | null | undefined): string {
  return val === null || val === undefined || val === '' ? EM_DASH : val;
}

function fmtBool(val: boolean | null | undefined): string {
  if (val === null || val === undefined) return EM_DASH;
  return val ? 'Yes' : 'No';
}

function fmtInt(val: number | null | undefined): string {
  return val === null || val === undefined ? EM_DASH : String(val);
}

function fmtScore(val: string | null | undefined): string {
  if (val === null || val === undefined) return EM_DASH;
  const n = parseFloat(val);
  return Number.isNaN(n) ? EM_DASH : n.toFixed(2);
}

function fmtPct(val: string | null | undefined): string {
  if (val === null || val === undefined) return EM_DASH;
  const n = parseFloat(val);
  return Number.isNaN(n) ? EM_DASH : `${n.toFixed(2)}%`;
}

function fmtMoney(val: string | null | undefined): string {
  if (val === null || val === undefined) return EM_DASH;
  const n = parseFloat(val);
  if (Number.isNaN(n)) return EM_DASH;
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function fmtDate(val: string | null | undefined): string {
  if (!val) return EM_DASH;
  return val.slice(0, 10);
}

function fmtDateTime(val: string | null | undefined): string {
  if (!val) return EM_DASH;
  try {
    return new Date(val).toLocaleString();
  } catch {
    return val;
  }
}

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

type Section16PanelProps = {
  /** Active ticker symbol chosen by the shared selector. */
  ticker: string;
};

/**
 * Section 16 panel — read-only diagnostic view of every value used by the
 * four exit rules. Matches the `atlas-frameworks-panel` visual style.
 */
export function Section16Panel({ ticker }: Section16PanelProps) {
  const { data, isLoading, isError, error } = useSection16(ticker);

  return (
    <section
      className="atlas-frameworks-panel atlas-s16-panel"
      data-testid="section16-panel"
    >
      <header className="atlas-frameworks-panel-header">
        <h2 className="atlas-frameworks-panel-title">Section 16 — Exit Rules</h2>
        {data && (
          <span className={cn('atlas-s16-chip', OVERALL_TONE[data.overall_status])}>
            {OVERALL_LABEL[data.overall_status]}
          </span>
        )}
      </header>

      <div className="atlas-s16-panel-body">
        {!ticker && (
          <p className="atlas-s16-state-msg">
            Select a ticker to evaluate Section 16 exit rules.
          </p>
        )}
        {ticker && isLoading && (
          <p className="atlas-s16-state-msg" data-testid="s16-loading">
            Evaluating Section 16 rules for {ticker}…
          </p>
        )}
        {ticker && isError && (
          <p className="atlas-s16-state-msg atlas-s16-error">
            Failed to load Section 16 data.{' '}
            {error instanceof Error ? error.message : 'Unknown error.'}
          </p>
        )}
        {ticker && !isLoading && !isError && data && (
          <Section16Content data={data} />
        )}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Content
// ---------------------------------------------------------------------------

function Section16Content({ data }: { data: Section16Result }) {
  return (
    <div className="atlas-s16-content">
      {data.override_active && (
        <div className="atlas-s16-override-banner">
          <span className={cn('atlas-s16-chip', 'is-orange')}>
            HUMAN OVERRIDE ACTIVE
          </span>
          {data.override_reason && (
            <p className="atlas-s16-banner-text">{data.override_reason}</p>
          )}
        </div>
      )}

      <OverallBlock data={data} />
      <Rule161Block r={data.rule_161} />
      <Rule162Block r={data.rule_162} />
      <Rule163Block r={data.rule_163} />
      <Rule164Block r={data.rule_164} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Primitive row / block components
// ---------------------------------------------------------------------------

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="atlas-s16-row">
      <span className="atlas-s16-row-label">{label}</span>
      <span className="atlas-s16-row-value">{value}</span>
    </div>
  );
}

function Block({
  title,
  tone,
  chip,
  children,
  missingSources,
}: {
  title: string;
  tone: string;
  chip: string;
  children: React.ReactNode;
  missingSources?: string[];
}) {
  return (
    <div className="atlas-s16-block">
      <div className="atlas-s16-block-header">
        <h3 className="atlas-s16-block-title">{title}</h3>
        <span className={cn('atlas-s16-chip', tone)}>{chip}</span>
      </div>
      <div className="atlas-s16-block-body">{children}</div>
      {missingSources && missingSources.length > 0 && (
        <div className="atlas-s16-missing">
          Missing sources: {missingSources.join(', ')}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Blocks
// ---------------------------------------------------------------------------

function OverallBlock({ data }: { data: Section16Result }) {
  return (
    <Block
      title="Overall"
      tone={OVERALL_TONE[data.overall_status]}
      chip={OVERALL_LABEL[data.overall_status]}
    >
      <Row label="Ticker" value={data.ticker} />
      <Row label="Available" value={fmtBool(data.available)} />
      <Row label="Overall status" value={data.overall_status} />
      <Row label="Any exit signal" value={fmtBool(data.any_exit_signal)} />
      <Row label="Override active" value={fmtBool(data.override_active)} />
      <Row label="Override reason" value={fmtStr(data.override_reason)} />
      <Row label="Override set by" value={fmtStr(data.override_set_by)} />
      <Row label="Override set at" value={fmtDateTime(data.override_set_at)} />
      <Row label="Evaluated at" value={fmtDateTime(data.evaluated_at)} />
    </Block>
  );
}

function Rule161Block({ r }: { r: Rule161Result }) {
  return (
    <Block
      title="16.1 — Score-Based Exit"
      tone={RULE161_TONE[r.status]}
      chip={RULE161_LABEL[r.status]}
      missingSources={r.missing_sources}
    >
      <Row label="Status" value={r.status} />
      <Row label="Cycle count" value={`${r.cycle_count} / 2`} />
      <Row label="Trim triggered" value={fmtBool(r.trim_triggered)} />
      <Row label="Full exit triggered" value={fmtBool(r.full_exit_triggered)} />
      <Row
        label="Exit window (trading days)"
        value={fmtInt(r.exit_window_trading_days)}
      />
      <Row
        label="Trim window (trading days)"
        value={fmtInt(r.trim_window_trading_days)}
      />
      <Row label="Trim %" value={fmtStr(r.trim_pct)} />
      <Row label="Deferred reason" value={fmtStr(r.deferred_reason)} />
      <Row label="Deferred until" value={fmtDate(r.deferred_until)} />
      <Row
        label="Reconciliation pending"
        value={fmtBool(r.reconciliation_pending)}
      />
      <Row label="Claude score" value={fmtScore(r.claude_score)} />
      <Row label="Grok score" value={fmtScore(r.grok_score)} />
      <Row label="Score gap" value={fmtScore(r.score_gap)} />
      <Row label="Triggering score" value={fmtScore(r.triggering_score)} />
      <Row label="Triggering date" value={fmtDate(r.triggering_date)} />
      <Row label="Data available" value={fmtBool(r.data_available)} />
    </Block>
  );
}

function Rule162Block({ r }: { r: Rule162Result }) {
  return (
    <Block
      title="16.2 — Gap-Down"
      tone={RULE162_TONE[r.status]}
      chip={RULE162_LABEL[r.status]}
      missingSources={r.missing_sources}
    >
      <Row label="Status" value={r.status} />
      <Row label="Gap triggered" value={fmtBool(r.gap_triggered)} />
      <Row label="Gap-down %" value={fmtPct(r.gap_down_pct)} />
      <Row label="Prev close" value={fmtMoney(r.prev_close)} />
      <Row label="Open price" value={fmtMoney(r.open_price)} />
      <Row label="Event date" value={fmtDate(r.event_date)} />
      <Row label="Hold until" value={fmtDateTime(r.hold_until)} />
      <Row label="Rescore at" value={fmtDateTime(r.rescore_at)} />
      <Row label="Rescore score" value={fmtScore(r.rescore_score)} />
      <Row label="Resolved at" value={fmtDateTime(r.resolved_at)} />
      <Row label="Data available" value={fmtBool(r.data_available)} />
    </Block>
  );
}

function Rule163Block({ r }: { r: Rule163Result }) {
  return (
    <Block
      title="16.3 — Appreciation Trim"
      tone={RULE163_TONE[r.status]}
      chip={RULE163_LABEL[r.status]}
      missingSources={r.missing_sources}
    >
      <Row label="Status" value={r.status} />
      <Row label="No new capital" value={fmtBool(r.no_new_capital)} />
      <Row label="Consider trim" value={fmtBool(r.consider_trim)} />
      <Row label="Position % of NAV" value={fmtPct(r.position_pct_of_nav)} />
      <Row label="Position value" value={fmtMoney(r.position_value)} />
      <Row label="Total NAV" value={fmtMoney(r.total_nav)} />
      <Row label="Trim %" value={fmtStr(r.trim_pct)} />
      <Row label="Data available" value={fmtBool(r.data_available)} />
    </Block>
  );
}

function Rule164Block({ r }: { r: Rule164Result }) {
  return (
    <Block
      title="16.4 — Put Protection"
      tone={RULE164_TONE[r.status]}
      chip={RULE164_LABEL[r.status]}
      missingSources={r.missing_sources}
    >
      <Row label="Status" value={r.status} />
      <Row label="Recommend puts" value={fmtBool(r.recommend_puts)} />
      <Row
        label="Conditions met"
        value={`${r.conditions_met} / ${r.conditions.length}`}
      />
      <Row label="Data available" value={fmtBool(r.data_available)} />

      <div className="atlas-s16-conditions">
        {r.conditions.map((c) => (
          <div
            key={c.condition_number}
            className={cn(
              'atlas-s16-condition',
              c.met === true
                ? 'is-green'
                : c.met === false
                  ? 'is-red'
                  : 'is-gray',
            )}
          >
            <span className="atlas-s16-condition-marker">
              {c.met === true ? '✓' : c.met === false ? '✗' : '?'}
            </span>
            <span className="atlas-s16-condition-desc">
              {c.condition_number}. {c.description}
            </span>
            <span className="atlas-s16-condition-value">
              {fmtStr(c.value)}
              {c.threshold !== null && (
                <span className="atlas-s16-condition-threshold">
                  {' '}
                  (threshold: {c.threshold})
                </span>
              )}
            </span>
          </div>
        ))}
      </div>
    </Block>
  );
}
