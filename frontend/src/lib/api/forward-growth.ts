import { apiFetch } from '@/lib/api/client';
import {
  forwardGrowthResponseSchema,
  type ForwardGrowthResponse,
} from '@/lib/schemas/forward-growth';

type Scores = {
  f5?: number | null;
  f4?: number | null;
  atlas?: number | null;
};

/**
 * Fetch the Forward Growth Score for a ticker.
 * Calls GET /api/v1/forward-growth/{ticker}[?f5_score=&f4_score=&atlas_score=].
 *
 * Pass the live F5 (and ideally F4) scores to get the F5 x FGS x F4 action bucket.
 */
export function fetchForwardGrowth(
  ticker: string,
  scores: Scores = {},
): Promise<ForwardGrowthResponse> {
  const params = new URLSearchParams();
  if (scores.f5 != null) params.set('f5_score', String(Math.round(scores.f5)));
  if (scores.f4 != null) params.set('f4_score', String(Math.round(scores.f4)));
  if (scores.atlas != null) params.set('atlas_score', String(Math.round(scores.atlas)));
  const qs = params.toString();
  return apiFetch(
    `/api/v1/forward-growth/${encodeURIComponent(ticker.toUpperCase())}${qs ? `?${qs}` : ''}`,
    forwardGrowthResponseSchema,
  );
}
