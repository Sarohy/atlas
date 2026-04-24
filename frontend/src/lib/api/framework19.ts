import { apiFetch } from '@/lib/api/client';
import {
  framework19ResultSchema,
  framework19SimpleResultSchema,
  f19PausedOrderSchema,
  type Framework19Result,
  type Framework19SimpleResult,
  type F19PausedOrder,
  type ReviewOrderRequest,
} from '@/lib/schemas/framework19';
import { z } from 'zod';

/**
 * Fetch the full Framework 19 status.
 *
 * ZERO caching — every call makes a fresh Polygon.io request on the backend.
 * Never use a long staleTime for this query; the kill switch must be reactive.
 */
export function fetchFramework19Status(): Promise<Framework19Result> {
  return apiFetch('/api/v1/framework19/status', framework19ResultSchema);
}

/**
 * Fetch the lightweight Framework 19 status from DB session state.
 * No Polygon.io call — reads today's framework19_sessions row.
 */
export function fetchFramework19Simple(): Promise<Framework19SimpleResult> {
  return apiFetch('/api/v1/framework19/status/simple', framework19SimpleResultSchema);
}

/**
 * Fetch today's paused orders for human review.
 */
export function fetchFramework19PausedOrders(): Promise<F19PausedOrder[]> {
  return apiFetch('/api/v1/framework19/paused-orders', z.array(f19PausedOrderSchema));
}

/**
 * Submit a human review decision for a paused order.
 */
export function reviewPausedOrder(
  pausedOrderId: number,
  body: ReviewOrderRequest,
): Promise<F19PausedOrder> {
  return apiFetch(`/api/v1/framework19/paused-orders/${pausedOrderId}/review`, f19PausedOrderSchema, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

/**
 * Fetch last 30 days of F19 session history.
 */
export function fetchFramework19History(): Promise<unknown[]> {
  return apiFetch('/api/v1/framework19/history', z.array(z.record(z.string(), z.unknown())));
}
