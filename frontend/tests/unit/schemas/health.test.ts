import { describe, expect, it } from 'vitest';
import { healthResponseSchema } from '@/lib/schemas/health';

describe('healthResponseSchema', () => {
  it('parses a valid payload successfully', () => {
    const result = healthResponseSchema.safeParse({ status: 'ok', service: 'atlas-backend' });
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data).toEqual({ status: 'ok', service: 'atlas-backend' });
    }
  });

  it('rejects a payload missing status', () => {
    const result = healthResponseSchema.safeParse({ service: 'atlas-backend' });
    expect(result.success).toBe(false);
  });

  it('rejects a payload missing service', () => {
    const result = healthResponseSchema.safeParse({ status: 'ok' });
    expect(result.success).toBe(false);
  });

  it('rejects a payload with wrong types', () => {
    const result = healthResponseSchema.safeParse({ status: 42, service: true });
    expect(result.success).toBe(false);
  });
});
