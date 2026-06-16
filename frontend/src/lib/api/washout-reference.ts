import { apiFetch } from '@/lib/api/client';
import {
  washoutReferenceResponseSchema,
  type WashoutReferenceResponse,
} from '@/lib/schemas/washout-reference';

/** Fetch the washout overlay reference (Settings thresholds + Risk exceptions). */
export function fetchWashoutReference(): Promise<WashoutReferenceResponse> {
  return apiFetch('/api/v1/extension-washout/reference', washoutReferenceResponseSchema);
}
