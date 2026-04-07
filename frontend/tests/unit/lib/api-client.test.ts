import { describe, expect, it } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '../../mocks/server';
import { fetchHealth } from '@/lib/api/health';
import { ApiError, ApiValidationError } from '@/lib/api/client';

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
