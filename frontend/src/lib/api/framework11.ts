import { apiFetch } from '@/lib/api/client';
import {
  framework11QueueResponseSchema,
  framework11ResultSchema,
  framework11SimpleResultSchema,
  type Framework11QueueResponse,
  type Framework11Result,
  type Framework11SimpleResult,
} from '@/lib/schemas/framework11';

/**
 * Fetch the full Framework 11 cash floor evaluation.
 * Calls GET /api/v1/framework11/status.
 */
export function fetchFramework11Status(): Promise<Framework11Result> {
  return apiFetch('/api/v1/framework11/status', framework11ResultSchema);
}

/**
 * Fetch the lightweight Framework 11 status (for consuming frameworks).
 * Calls GET /api/v1/framework11/status/simple.
 */
export function fetchFramework11Simple(): Promise<Framework11SimpleResult> {
  return apiFetch(
    '/api/v1/framework11/status/simple',
    framework11SimpleResultSchema,
  );
}

/**
 * Fetch all currently queued buy signals.
 * Calls GET /api/v1/framework11/queue.
 */
export function fetchFramework11Queue(): Promise<Framework11QueueResponse> {
  return apiFetch('/api/v1/framework11/queue', framework11QueueResponseSchema);
}

/**
 * Force cache clear and re-evaluate the cash floor.
 * Calls POST /api/v1/framework11/refresh.
 */
export function refreshFramework11(): Promise<Framework11Result> {
  return apiFetch('/api/v1/framework11/refresh', framework11ResultSchema, {
    method: 'POST',
  });
}
