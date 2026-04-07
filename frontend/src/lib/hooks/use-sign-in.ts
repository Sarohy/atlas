import { useState } from 'react';
import { ApiError } from '@/lib/api/client';
import { signIn } from '@/lib/api/auth';
import { type SignInResponse } from '@/lib/schemas/auth';

const DEFAULT_SIGN_IN_ERROR = 'Unable to sign in.';

export function useSignIn() {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [signInResponse, setSignInResponse] = useState<SignInResponse | null>(null);

  async function submit(email: string, password: string): Promise<void> {
    setErrorMessage('');
    setSignInResponse(null);
    setIsSubmitting(true);

    try {
      const response = await signIn({ email, password });
      setSignInResponse(response);
    } catch (error: unknown) {
      if (error instanceof ApiError && error.message === 'Invalid email or password.') {
        setErrorMessage(error.message);
      } else {
        setErrorMessage(DEFAULT_SIGN_IN_ERROR);
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return {
    clearError: () => setErrorMessage(''),
    errorMessage,
    isSubmitting,
    signInResponse,
    submit,
  };
}
