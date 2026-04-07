'use client';

import { useEffect, useState } from 'react';
import { z } from 'zod';
import { Button } from '@/components/ui/button';
import { InputField } from '@/components/ui/input-field';
import { useAuthSession } from '@/components/auth/auth-session-provider';
import { useSignIn } from '@/lib/hooks/use-sign-in';

const signInSchema = z.object({
  email: z.email('Enter a valid email address.'),
  password: z.string().min(1, 'Enter your password.'),
});

export function SignInForm() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [validationMessage, setValidationMessage] = useState('');
  const { clearError, errorMessage, isSubmitting, signInResponse, submit } = useSignIn();
  const { signIn } = useAuthSession();

  useEffect(() => {
    if (signInResponse === null) {
      return;
    }

    void signIn({
      email: signInResponse.email,
      rememberMe,
    });
  }, [rememberMe, signIn, signInResponse]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const parsedValues = signInSchema.safeParse({ email, password });
    if (!parsedValues.success) {
      const firstIssue = parsedValues.error.issues[0];
      setValidationMessage(firstIssue?.message ?? 'Unable to sign in.');
      clearError();
      return;
    }

    setValidationMessage('');
    await submit(parsedValues.data.email, parsedValues.data.password);
  }

  const visibleErrorMessage = validationMessage || errorMessage;

  return (
    <form className="atlas-auth-form" noValidate onSubmit={handleSubmit}>
      <InputField
        autoComplete="email"
        label="Email address"
        name="email"
        onChange={setEmail}
        placeholder="abc@gmail.com"
        type="email"
        value={email}
      />
      <InputField
        autoComplete="current-password"
        label="Password"
        name="password"
        onChange={setPassword}
        onToggleVisibility={() => setShowPassword((currentValue) => !currentValue)}
        placeholder="***************"
        type={showPassword ? 'text' : 'password'}
        value={password}
      />
      <label className="atlas-auth-remember" data-state={rememberMe ? 'checked' : 'unchecked'}>
        <input
          checked={rememberMe}
          name="rememberMe"
          onChange={() => setRememberMe((currentValue) => !currentValue)}
          type="checkbox"
        />
        <span aria-hidden="true" className="atlas-auth-remember-icon" />
        <span className="atlas-auth-remember-label">Remember me</span>
      </label>
      {visibleErrorMessage ? (
        <p aria-live="polite" className="atlas-auth-error">
          {visibleErrorMessage}
        </p>
      ) : null}
      {signInResponse ? (
        <div aria-live="polite" className="atlas-auth-success">
          <p>{signInResponse.message}</p>
          <p>Signed in as {signInResponse.email}</p>
        </div>
      ) : null}
      <Button loading={isSubmitting} type="submit">
        {isSubmitting ? 'Signing in' : 'Sign In'}
      </Button>
    </form>
  );
}
