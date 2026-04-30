import { apiFetch } from '@/lib/api/client';
import {
  framework12ResultSchema,
  framework12SizingSchema,
  type Framework12Result,
  type Framework12Sizing,
} from '@/lib/schemas/framework12';

const ENCODE = (ticker: string): string => encodeURIComponent(ticker.trim().toUpperCase());

/** GET /api/v1/framework12/{ticker} — full sizing evaluation (runs S16 first). */
export function fetchFramework12(ticker: string): Promise<Framework12Result> {
  return apiFetch(`/api/v1/framework12/${ENCODE(ticker)}`, framework12ResultSchema);
}

/** GET /api/v1/framework12/{ticker}/sizing — lightweight USD range + timing only. */
export function fetchFramework12Sizing(ticker: string): Promise<Framework12Sizing> {
  return apiFetch(
    `/api/v1/framework12/${ENCODE(ticker)}/sizing`,
    framework12SizingSchema,
  );
}
