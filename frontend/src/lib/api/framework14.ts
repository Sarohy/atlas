import { apiFetch } from '@/lib/api/client';
import {
  framework14ResultSchema,
  type Framework14Result,
} from '@/lib/schemas/framework14';

/**
 * Fetch Framework 14 position sizing rules evaluation for a given ticker.
 *
 * The backend computes concentration cap status, grandfathered status,
 * cluster concentration, and sizing tier guidance from the live portfolio DB.
 */
export function fetchFramework14(ticker: string): Promise<Framework14Result> {
  return apiFetch(
    `/api/v1/framework14/${encodeURIComponent(ticker.toUpperCase())}`,
    framework14ResultSchema,
  );
}
