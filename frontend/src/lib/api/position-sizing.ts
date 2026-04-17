import { apiFetch } from '@/lib/api/client';
import {
  positionSizingResponseSchema,
  type PositionSizingResponse,
} from '@/lib/schemas/position-sizing';

export function fetchPositionSizing(
  ticker: string,
  baseScore?: number,
): Promise<PositionSizingResponse> {
  const path = `/api/v1/position-sizing/${encodeURIComponent(ticker.toUpperCase())}`;
  const url = baseScore !== undefined ? `${path}?base_score=${baseScore}` : path;
  return apiFetch(url, positionSizingResponseSchema);
}
