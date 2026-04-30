'use client';

import { useEffect, useRef, useState } from 'react';

import { useSection16, useSetRule4Today } from '@/lib/hooks/use-section16';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const OPERATOR_NAME = 'investor';
const HEADER_NOTE = 'Set via UI header';
const FLASH_MS = 1500;
const ERROR_MS = 3000;

type FitValue = 'NOT_SET' | 'YES' | 'NO';

const OPTION_LONG_LABEL: Record<FitValue, string> = {
  NOT_SET: '⬜ NOT SET',
  YES: '✅ YES — Fits portfolio',
  NO: '❌ NO — Does not fit',
};

const OPTION_SHORT_LABEL: Record<FitValue, string> = {
  NOT_SET: 'NOT SET',
  YES: 'YES',
  NO: 'NO',
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

/**
 * Derive today's portfolio-fit state from the Section 16 result.
 * Rule 4 is daily — yesterday's YES/NO does NOT carry forward.
 */
function derivedFitValue(
  fitDate: string | null | undefined,
  fitsPortfolio: boolean | null | undefined,
): FitValue {
  if (fitDate !== todayIso() || fitsPortfolio === null || fitsPortfolio === undefined) {
    return 'NOT_SET';
  }
  return fitsPortfolio ? 'YES' : 'NO';
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

type FitSelectorProps = {
  ticker: string;
};

/**
 * Header-level Rule 4 portfolio-fit selector.
 *
 * Reads today's fit state from `useSection16(ticker)`.  Saves are immediate
 * (POST /section16/rule4/{ticker}) and invalidate the cache so all rule
 * displays refresh automatically.  Resets daily — yesterday's YES/NO never
 * carries to the next session.
 */
export function FitSelector({ ticker }: FitSelectorProps) {
  const { data, isLoading } = useSection16(ticker);
  const mutation = useSetRule4Today(ticker);

  const fitDate = data?.rule4?.fit_date ?? null;
  const fits = data?.rule4?.fits_portfolio ?? null;
  const serverValue: FitValue = derivedFitValue(fitDate, fits);

  const [flash, setFlash] = useState<'idle' | 'saved' | 'error'>('idle');
  const flashTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (flashTimer.current !== null) clearTimeout(flashTimer.current);
    };
  }, []);

  const showFlash = (kind: 'saved' | 'error') => {
    if (flashTimer.current !== null) clearTimeout(flashTimer.current);
    setFlash(kind);
    flashTimer.current = setTimeout(
      () => setFlash('idle'),
      kind === 'saved' ? FLASH_MS : ERROR_MS,
    );
  };

  const handleChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const next = event.target.value as FitValue;
    if (next === 'NOT_SET' || next === serverValue) return;
    mutation.mutate(
      {
        fits_portfolio: next === 'YES',
        set_by: OPERATOR_NAME,
        notes: HEADER_NOTE,
      },
      {
        onSuccess: () => showFlash('saved'),
        onError: () => showFlash('error'),
      },
    );
  };

  const stateClass =
    serverValue === 'NOT_SET'
      ? 'is-fit-notset'
      : serverValue === 'YES'
        ? 'is-fit-yes'
        : 'is-fit-no';

  const flashClass =
    flash === 'saved' ? 'is-fit-flash-saved' : flash === 'error' ? 'is-fit-flash-error' : '';

  const flashText =
    flash === 'saved'
      ? `Fit ${OPTION_SHORT_LABEL[serverValue]} saved`
      : flash === 'error'
        ? 'Save failed — retry'
        : null;

  return (
    <div
      className={cn('atlas-fit-selector', stateClass, flashClass)}
      data-testid="fit-selector"
    >
      <span className="atlas-fit-selector-prefix">FIT:</span>
      <select
        className="atlas-fit-selector-select"
        aria-label={`Portfolio fit for ${ticker} today`}
        value={serverValue}
        disabled={!ticker || isLoading || mutation.isPending}
        onChange={handleChange}
        data-testid="fit-selector-select"
      >
        <option value="NOT_SET">{OPTION_LONG_LABEL.NOT_SET}</option>
        <option value="YES">{OPTION_LONG_LABEL.YES}</option>
        <option value="NO">{OPTION_LONG_LABEL.NO}</option>
      </select>
      {flashText !== null && (
        <span className="atlas-fit-selector-flash" data-testid="fit-selector-flash">
          {flashText}
        </span>
      )}
    </div>
  );
}
