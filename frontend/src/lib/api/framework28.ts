import { apiFetch } from '@/lib/api/client';
import {
  framework28ResultSchema,
  type Framework28Result,
} from '@/lib/schemas/framework28';

/**
 * Fetch the Framework 28 war duration ladder evaluation.
 * Calls GET /api/v1/framework28/ladder.
 * Cached 5 minutes on the backend.
 */
export function fetchFramework28Ladder(): Promise<Framework28Result> {
  return apiFetch('/api/v1/framework28/ladder', framework28ResultSchema);
}
