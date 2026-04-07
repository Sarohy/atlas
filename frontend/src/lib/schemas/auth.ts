import { z } from 'zod';

export const signInResponseSchema = z.object({
  email: z.email(),
  message: z.string().min(1),
});

export type SignInResponse = z.infer<typeof signInResponseSchema>;

export const logoutResponseSchema = z.object({
  message: z.string().min(1),
});

export type LogoutResponse = z.infer<typeof logoutResponseSchema>;
