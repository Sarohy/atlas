import { describe, expect, it } from 'vitest';
import { http, HttpResponse } from 'msw';
import { z } from 'zod';
import { server } from '../../mocks/server';
import { fetchHealth } from '@/lib/api/health';
import {
  ApiError,
  ApiValidationError,
  apiFetchEmpty,
  apiPost,
  apiPatch,
  apiPut,
  apiDelete,
} from '@/lib/api/client';

describe('fetchHealth', () => {
  it('returns the parsed health object on success', async () => {
    const result = await fetchHealth();
    expect(result).toEqual({ status: 'ok', service: 'atlas-backend' });
  });

  it('throws ApiError when the server returns a 500', async () => {
    server.use(
      http.get('http://localhost:8000/api/v1/health', () => {
        return HttpResponse.json({ error: 'Internal Server Error' }, { status: 500 });
      }),
    );
    await expect(fetchHealth()).rejects.toThrow(ApiError);
  });

  it('throws ApiValidationError when the response has an unexpected shape', async () => {
    server.use(
      http.get('http://localhost:8000/api/v1/health', () => {
        return HttpResponse.json({ unexpected: 'shape' });
      }),
    );
    await expect(fetchHealth()).rejects.toThrow(ApiValidationError);
  });
});

describe('apiFetchEmpty', () => {
  it('resolves with no value on 204', async () => {
    const result = await apiFetchEmpty('/api/v1/tickers/1', {
      method: 'DELETE',
    });
    expect(result).toBeUndefined();
  });

  it('throws ApiError on non-2xx', async () => {
    server.use(
      http.delete('http://localhost:8000/api/v1/tickers/999', () => {
        return HttpResponse.json({ detail: 'Not found' }, { status: 404 });
      }),
    );
    await expect(apiFetchEmpty('/api/v1/tickers/999', { method: 'DELETE' })).rejects.toThrow(
      ApiError,
    );
  });
});

describe('apiPost', () => {
  it('sends POST and parses the response', async () => {
    const schema = z.object({ id: z.number(), ticker: z.string() });
    const result = await apiPost('/api/v1/tickers', schema, {
      ticker: 'NVDA',
      company_name: 'NVIDIA',
      shares: 25,
    });
    expect(result.ticker).toBe('NVDA');
  });
});

describe('apiPut', () => {
  it('sends PUT and parses the response', async () => {
    const schema = z.object({ cash_balance: z.number(), cash_floor_pct: z.number() });
    const result = await apiPut('/api/v1/portfolio/cash', schema, {
      cash_balance: 3585000,
      cash_floor_pct: 0.1,
    });
    expect(result.cash_balance).toBe(3585000);
  });
});

describe('apiPatch', () => {
  it('sends PATCH and parses the response', async () => {
    const schema = z.object({ id: z.number(), shares: z.coerce.number() });
    const result = await apiPatch('/api/v1/tickers/1', schema, { shares: 200 });
    expect(result.shares).toBe(200);
  });
});

describe('apiDelete', () => {
  it('sends DELETE and resolves with no value', async () => {
    const result = await apiDelete('/api/v1/tickers/1');
    expect(result).toBeUndefined();
  });
});
