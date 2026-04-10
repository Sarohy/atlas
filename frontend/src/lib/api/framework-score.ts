import { apiFetch } from '@/lib/api/client';
import {
  frameworkScoreResponseSchema,
  type FrameworkScoreResponse,
} from '@/lib/schemas/framework-score';

/**
 * Fetch the complete ATLAS Framework Score for a single ticker from the backend.
 * Calls GET /api/v1/framework-score/{ticker}.
 *
 * Aggregates F1-F5 scores with their Factor_Mapping_Guide weightings and
 * returns the final conviction score with full breakdowns.
 */
export function fetchFrameworkScore(ticker: string): Promise<FrameworkScoreResponse> {
  return apiFetch(
    `/api/v1/framework-score/${encodeURIComponent(ticker.toUpperCase())}`,
    frameworkScoreResponseSchema,
  );
}
