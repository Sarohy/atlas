import { apiFetch } from '@/lib/api/client';
import {
  positionSizingResponseSchema,
  type PositionSizingResponse,
} from '@/lib/schemas/position-sizing';

export function fetchPositionSizing(
  ticker: string,
  baseScore?: number,
  concentrationCapActive?: boolean,
): Promise<PositionSizingResponse> {
  const path = `/api/v1/position-sizing/${encodeURIComponent(ticker.toUpperCase())}`;
  const params = new URLSearchParams();
  if (baseScore !== undefined) params.set('base_score', String(baseScore));
  if (concentrationCapActive) params.set('concentration_cap_active', 'true');
  const query = params.toString();
  const url = query ? `${path}?${query}` : path;
  return apiFetch(url, positionSizingResponseSchema);
}
