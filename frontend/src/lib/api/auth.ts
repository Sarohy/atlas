import { apiFetch } from './client';
import {
  logoutResponseSchema,
  signInResponseSchema,
  type LogoutResponse,
  type SignInResponse,
} from '@/lib/schemas/auth';

type SignInPayload = {
  email: string;
  password: string;
};

export async function signIn(payload: SignInPayload): Promise<SignInResponse> {
  return apiFetch('/api/v1/auth/sign-in', signInResponseSchema, {
    body: JSON.stringify(payload),
    headers: {
      'Content-Type': 'application/json',
    },
    method: 'POST',
  });
}

export async function signOut(): Promise<LogoutResponse> {
  return apiFetch('/api/v1/auth/logout', logoutResponseSchema, {
    method: 'POST',
  });
}
