import { apiFetch, apiPost } from '@/lib/api/client';
import {
  overrideUseRequestSchema,
  overrideUseResponseSchema,
  rule4RequestSchema,
  rule4ResponseSchema,
  section16GateSchema,
  section16ResultSchema,
  trackAssignmentRequestSchema,
  trackAssignmentResponseSchema,
  type OverrideUseRequest,
  type OverrideUseResponse,
  type Rule4Request,
  type Rule4Response,
  type Section16Gate,
  type Section16Result,
  type TrackAssignmentRequest,
  type TrackAssignmentResponse,
} from '@/lib/schemas/section16';

const ENCODE = (ticker: string): string => encodeURIComponent(ticker.trim().toUpperCase());

/** GET /api/v1/section16/{ticker} — full evaluation with all 4 rules. */
export function fetchSection16(ticker: string): Promise<Section16Result> {
  return apiFetch(`/api/v1/section16/${ENCODE(ticker)}`, section16ResultSchema);
}

/** GET /api/v1/section16/{ticker}/gate — lightweight gate verdict only. */
export function fetchSection16Gate(ticker: string): Promise<Section16Gate> {
  return apiFetch(`/api/v1/section16/${ENCODE(ticker)}/gate`, section16GateSchema);
}

/** POST /api/v1/section16/track/{ticker} — assign Track A or Track B. */
export function setTrackAssignment(
  ticker: string,
  body: TrackAssignmentRequest,
): Promise<TrackAssignmentResponse> {
  trackAssignmentRequestSchema.parse(body);
  return apiPost(
    `/api/v1/section16/track/${ENCODE(ticker)}`,
    trackAssignmentResponseSchema,
    body,
  );
}

/** POST /api/v1/section16/rule4/{ticker} — set today's portfolio-fit YES/NO. */
export function setRule4Today(
  ticker: string,
  body: Rule4Request,
): Promise<Rule4Response> {
  rule4RequestSchema.parse(body);
  return apiPost(
    `/api/v1/section16/rule4/${ENCODE(ticker)}`,
    rule4ResponseSchema,
    body,
  );
}

/** POST /api/v1/section16/override/{ticker}/use — burn the override for this earnings cycle. */
export function postOverrideUse(
  ticker: string,
  body: OverrideUseRequest,
): Promise<OverrideUseResponse> {
  overrideUseRequestSchema.parse(body);
  return apiPost(
    `/api/v1/section16/override/${ENCODE(ticker)}/use`,
    overrideUseResponseSchema,
    body,
  );
}
