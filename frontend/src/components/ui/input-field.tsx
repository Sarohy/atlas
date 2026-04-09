'use client';

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
      <span className="atlas-auth-input-frame">
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
            {type === 'password' ? (
              /* Eye — show password */
              <svg
                aria-hidden="true"
                fill="none"
                stroke="currentColor"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.75}
                viewBox="0 0 24 24"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
            ) : (
              /* Eye-off — hide password */
              <svg
                aria-hidden="true"
                fill="none"
                stroke="currentColor"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.75}
                viewBox="0 0 24 24"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94" />
                <path d="M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19" />
                <line x1="1" x2="23" y1="1" y2="23" />
              </svg>
            )}
          </button>
        ) : null}
      </span>
    </label>
  );
}
