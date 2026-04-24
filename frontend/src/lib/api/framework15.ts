import { apiFetch } from '@/lib/api/client';
import {
  framework15ResultSchema,
  framework15SimpleResultSchema,
  vixSnapshotSchema,
  type AddOverrideRequest,
  type Framework15Result,
  type Framework15SimpleResult,
  type ReviewOrderRequest,
  type VixSnapshot,
} from '@/lib/schemas/framework15';

/** Zod schema for the paused-orders response envelope. */
import { z } from 'zod';
import { pausedOrderSchema } from '@/lib/schemas/framework15';

const pausedOrdersResponseSchema = z.object({
  session_date: z.string(),
  paused_orders: z.array(pausedOrderSchema),
  count: z.number(),
});
type PausedOrdersResponse = z.infer<typeof pausedOrdersResponseSchema>;

/**
 * Fetch the full Framework 15 VIX Regime Override evaluation.
 * Calls GET /api/v1/framework15/status.
 * Cached 60 s on the backend.
 */
export function fetchFramework15Status(): Promise<Framework15Result> {
  return apiFetch('/api/v1/framework15/status', framework15ResultSchema);
}

/**
 * Fetch the lightweight F15 status for consuming frameworks.
 * Calls GET /api/v1/framework15/status/simple.
 */
export function fetchFramework15Simple(): Promise<Framework15SimpleResult> {
  return apiFetch(
    '/api/v1/framework15/status/simple',
    framework15SimpleResultSchema,
  );
}

/**
 * Fetch the VIX snapshot for Framework 25 — Liquidity Protocol.
 * Calls GET /api/v1/framework15/vix-snapshot.
 */
export function fetchVixSnapshot(): Promise<VixSnapshot> {
  return apiFetch('/api/v1/framework15/vix-snapshot', vixSnapshotSchema);
}

/**
 * Fetch all paused orders for today's session.
 * Calls GET /api/v1/framework15/paused-orders.
 */
export function fetchPausedOrders(): Promise<PausedOrdersResponse> {
  return apiFetch(
    '/api/v1/framework15/paused-orders',
    pausedOrdersResponseSchema,
  );
}

/**
 * Apply a human override for the current session halt.
 * Calls POST /api/v1/framework15/override.
 */
export function addOverride(
  body: AddOverrideRequest,
): Promise<Record<string, unknown>> {
  return apiFetch('/api/v1/framework15/override', z.record(z.unknown()), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

/**
 * Record operator review decision for one paused order.
 * Calls PUT /api/v1/framework15/paused-orders/{orderId}/review.
 */
export function reviewPausedOrder(
  orderId: number,
  body: ReviewOrderRequest,
): Promise<Record<string, unknown>> {
  return apiFetch(
    `/api/v1/framework15/paused-orders/${orderId}/review`,
    z.record(z.unknown()),
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
  );
}

/**
 * Invalidate the backend cache and re-evaluate Framework 15.
 * Calls POST /api/v1/framework15/refresh.
 */
export function refreshFramework15(): Promise<Framework15Result> {
  return apiFetch('/api/v1/framework15/refresh', framework15ResultSchema, {
    method: 'POST',
  });
}
