'use client';

import { useState } from 'react';
import { z } from 'zod';
import { Button } from '@/components/ui/button';
import { InputField } from '@/components/ui/input-field';
import { AUTH_THEME } from '@/styles/theme';

const signInSchema = z.object({
  email: z.email('Enter a valid email address.'),
  password: z.string().min(1, 'Enter your password.'),
});

function waitForSignIn() {
  return new Promise<void>((resolve) => {
    window.setTimeout(resolve, AUTH_THEME.signInDelayMs);
  });
}

export function SignInForm() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const parsedValues = signInSchema.safeParse({ email, password });
    if (!parsedValues.success) {
      const firstIssue = parsedValues.error.issues[0];
      setErrorMessage(firstIssue?.message ?? 'Unable to sign in.');
      return;
    }

    setErrorMessage('');
    setIsSubmitting(true);
    await waitForSignIn();
    setIsSubmitting(false);
  }

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
      {errorMessage ? (
        <p aria-live="polite" className="atlas-auth-error">
          {errorMessage}
        </p>
      ) : null}
      <Button loading={isSubmitting} type="submit">
        {isSubmitting ? 'Signing in' : 'Sign In'}
      </Button>
    </form>
  );
}
