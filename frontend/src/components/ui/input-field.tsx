'use client';

import { AUTH_IMAGES } from '@/styles/theme';

type InputFieldProps = {
  autoComplete?: string;
  label: string;
  name: string;
  onChange: (value: string) => void;
  onToggleVisibility?: () => void;
  placeholder: string;
  type: 'email' | 'password' | 'text';
  value: string;
};

export function InputField({
  autoComplete,
  label,
  name,
  onChange,
  onToggleVisibility,
  placeholder,
  type,
  value,
}: InputFieldProps) {
  return (
    <label className="atlas-auth-field" htmlFor={name}>
      <span className="atlas-auth-label">{label}</span>
      <span
        className="atlas-auth-input-frame"
        style={
          {
            '--atlas-auth-input-frame-url': `url(${AUTH_IMAGES.inputFrame})`,
          } as React.CSSProperties
        }
      >
        <input
          autoComplete={autoComplete}
          className="atlas-auth-input"
          id={name}
          name={name}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          type={type}
          value={value}
        />
        {onToggleVisibility ? (
          <button
            aria-label={type === 'password' ? 'Show password' : 'Hide password'}
            className="atlas-auth-visibility"
            onClick={onToggleVisibility}
            type="button"
          >
            <img alt="" aria-hidden="true" src={AUTH_IMAGES.eye} />
          </button>
        ) : null}
      </span>
    </label>
  );
}
