import { apiFetch } from '@/lib/api/client';
import {
  contagionRuleResultSchema,
  framework27ResultSchema,
  type ContagionRuleResult,
  type Framework27Result,
  type ManualFlagRequest,
} from '@/lib/schemas/framework27';
import { z } from 'zod';

/**
 * Fetch the full Framework 27 supply chain contagion map evaluation.
 * Calls GET /api/v1/framework27/contagion.
 * Cached 5 minutes on the backend.
 */
export function fetchFramework27Contagion(): Promise<Framework27Result> {
  return apiFetch('/api/v1/framework27/contagion', framework27ResultSchema);
}

/**
 * Fetch contagion rules for a single ticker.
 * Calls GET /api/v1/framework27/contagion/{ticker}.
 */
export function fetchFramework27TickerContagion(
  ticker: string,
): Promise<ContagionRuleResult[]> {
  return apiFetch(
    `/api/v1/framework27/contagion/${encodeURIComponent(ticker.toUpperCase())}`,
    z.array(contagionRuleResultSchema),
  );
}

/**
 * Operator manual disruption confirmation.
 * Calls POST /api/v1/framework27/contagion/manual-flag.
 */
export function postFramework27ManualFlag(
  body: ManualFlagRequest,
): Promise<Framework27Result> {
  return apiFetch(
    '/api/v1/framework27/contagion/manual-flag',
    framework27ResultSchema,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
  );
}
