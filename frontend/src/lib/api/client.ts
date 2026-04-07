import { type ZodSchema } from 'zod';

/** Thrown when the server responds with a non-2xx status code. */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

/** Thrown when the response body does not match the expected Zod schema. */
export class ApiValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ApiValidationError';
  }
}

const BASE_URL = process.env['NEXT_PUBLIC_API_URL'] ?? 'http://localhost:8000';

type ApiFetchOptions = RequestInit;

/**
 * Typed fetch wrapper.
 * Throws ApiError on non-2xx responses, ApiValidationError on schema mismatch.
 */
export async function apiFetch<T>(
  path: string,
  schema: ZodSchema<T>,
  options?: ApiFetchOptions,
): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const response = await fetch(url, options);

  if (!response.ok) {
    let errorMessage = `Request failed: ${response.status} ${response.statusText}`;

    try {
      const errorBody: unknown = await response.json();
      if (
        typeof errorBody === 'object' &&
        errorBody !== null &&
        'detail' in errorBody &&
        typeof errorBody.detail === 'string'
      ) {
        errorMessage = errorBody.detail;
      }
    } catch {
      // Fall back to the HTTP status message when no JSON body is available.
    }

    throw new ApiError(
      response.status,
      errorMessage,
    );
  }

  const json: unknown = await response.json();
  const parsed = schema.safeParse(json);

  if (!parsed.success) {
    throw new ApiValidationError(`Response validation failed: ${parsed.error.message}`);
  }

  return parsed.data;
}
