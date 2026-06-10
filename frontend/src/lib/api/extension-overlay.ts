import { apiFetch } from '@/lib/api/client';
import {
  extensionOverlayResponseSchema,
  type ExtensionOverlayResponse,
} from '@/lib/schemas/extension-overlay';

/**
 * Fetch the Overbought / Extension Overlay for a single ticker.
 * Calls GET /api/v1/extension-overlay/{ticker}[?atlas_score={n}].
 *
 * Pass the ticker's final ATLAS conviction score to get an action
 * recommendation from the quality x timing matrix.
 */
export function fetchExtensionOverlay(
  ticker: string,
  atlasScore?: number | null,
): Promise<ExtensionOverlayResponse> {
  const query =
    atlasScore != null ? `?atlas_score=${encodeURIComponent(Math.round(atlasScore))}` : '';
  return apiFetch(
    `/api/v1/extension-overlay/${encodeURIComponent(ticker.toUpperCase())}${query}`,
    extensionOverlayResponseSchema,
  );
}
