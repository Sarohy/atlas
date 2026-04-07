import { describe, expect, it } from 'vitest';

import {
  positionResponseSchema,
  positionSchema,
  tickerSearchResultSchema,
} from '@/lib/schemas/position';

describe('tickerSearchResultSchema', () => {
  it('parses a valid Polygon ticker result', () => {
    const result = tickerSearchResultSchema.parse({
      ticker: 'NVDA',
      name: 'NVIDIA Corporation',
      market: 'stocks',
      type: 'CS',
    });
    expect(result.ticker).toBe('NVDA');
  });

  it('rejects a result missing the name field', () => {
    expect(() =>
      tickerSearchResultSchema.parse({ ticker: 'NVDA', market: 'stocks', type: 'CS' }),
    ).toThrow();
  });
});

describe('positionSchema', () => {
  it('parses a valid position create payload', () => {
    const result = positionSchema.parse({
      ticker: 'AAPL',
      company_name: 'Apple Inc.',
      shares: '150',
    });
    expect(result.ticker).toBe('AAPL');
  });

  it('rejects empty ticker', () => {
    expect(() =>
      positionSchema.parse({ ticker: '', company_name: 'Apple Inc.', shares: '10' }),
    ).toThrow();
  });

  it('rejects non-positive shares', () => {
    expect(() =>
      positionSchema.parse({ ticker: 'AAPL', company_name: 'Apple Inc.', shares: '0' }),
    ).toThrow();
  });
});

describe('positionResponseSchema', () => {
  it('parses a full position response from the API', () => {
    const result = positionResponseSchema.parse({
      id: 1,
      ticker: 'MSFT',
      company_name: 'Microsoft Corporation',
      shares: '50',
      created_at: '2026-04-07T00:00:00Z',
      updated_at: '2026-04-07T00:00:00Z',
    });
    expect(result.id).toBe(1);
    expect(result.ticker).toBe('MSFT');
  });
});
