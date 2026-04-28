'use client';

import { useEffect, useRef, useState } from 'react';

import { useSection16, useSetTrackAssignment } from '@/lib/hooks/use-section16';
import type { TrackType } from '@/lib/schemas/section16';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Operator name attached to mutations (single-investor system). */
const OPERATOR_NAME = 'investor';

/** Note string saved with header-driven track changes. */
const HEADER_NOTE = 'Set via UI header';

/** How long the green "saved" flash persists (ms). */
const FLASH_MS = 1500;

/** How long the red "save failed" message persists (ms). */
const ERROR_MS = 3000;

type SelectValue = TrackType;

const OPTION_LABEL: Record<SelectValue, string> = {
  UNASSIGNED: 'UNASSIGNED',
  TRACK_A: 'TRACK A',
  TRACK_B: 'TRACK B',
};

const OPTION_LONG_LABEL: Record<SelectValue, string> = {
  UNASSIGNED: '⚪ UNASSIGNED',
  TRACK_A: '🔵 TRACK A — Core Resilient',
  TRACK_B: '🟣 TRACK B — Satellite/High-Beta',
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

type TrackSelectorProps = {
  ticker: string;
};

/**
 * Header-level Track A/B selector.
 *
 * Reads track from the same `useSection16(ticker)` query the Section 16 card
 * uses, so card buttons and this selector are always in sync via TanStack
 * Query cache.  Saves are immediate (POST /section16/track/{ticker}) and the
 * mutation hook invalidates the cache so the card re-evaluates automatically.
 */
export function TrackSelector({ ticker }: TrackSelectorProps) {
  const { data, isLoading } = useSection16(ticker);
  const mutation = useSetTrackAssignment(ticker);

  const serverValue: SelectValue = data?.track ?? 'UNASSIGNED';
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
    const next = event.target.value as SelectValue;
    // UNASSIGNED is the placeholder — no API call required.
    if (next === 'UNASSIGNED' || next === serverValue) return;
    mutation.mutate(
      { track: next, assigned_by: OPERATOR_NAME, notes: HEADER_NOTE },
      {
        onSuccess: () => showFlash('saved'),
        onError: () => showFlash('error'),
      },
    );
  };

  const isUnassigned = serverValue === 'UNASSIGNED';
  const stateClass = isUnassigned
    ? 'is-track-unassigned'
    : serverValue === 'TRACK_A'
      ? 'is-track-a'
      : 'is-track-b';

  const flashClass =
    flash === 'saved' ? 'is-track-flash-saved' : flash === 'error' ? 'is-track-flash-error' : '';

  const flashText =
    flash === 'saved'
      ? `${OPTION_LABEL[serverValue]} saved`
      : flash === 'error'
        ? 'Save failed — retry'
        : null;

  return (
    <div
      className={cn('atlas-track-selector', stateClass, flashClass)}
      data-testid="track-selector"
    >
      <span className="atlas-track-selector-dot" aria-hidden="true" />
      <select
        className="atlas-track-selector-select"
        aria-label={`Track assignment for ${ticker}`}
        value={serverValue}
        disabled={!ticker || isLoading || mutation.isPending}
        onChange={handleChange}
        data-testid="track-selector-select"
      >
        <option value="UNASSIGNED">{OPTION_LONG_LABEL.UNASSIGNED}</option>
        <option value="TRACK_A">{OPTION_LONG_LABEL.TRACK_A}</option>
        <option value="TRACK_B">{OPTION_LONG_LABEL.TRACK_B}</option>
      </select>
      {flashText !== null && (
        <span className="atlas-track-selector-flash" data-testid="track-selector-flash">
          {flashText}
        </span>
      )}
    </div>
  );
}
