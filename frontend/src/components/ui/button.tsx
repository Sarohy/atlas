'use client';

type ButtonProps = {
  children: React.ReactNode;
  disabled?: boolean;
  loading?: boolean;
  onClick?: () => void;
  type?: 'button' | 'submit';
};

export function Button({
  children,
  disabled = false,
  loading = false,
  onClick,
  type = 'button',
}: ButtonProps) {
  return (
    <button
      aria-busy={loading}
      className="atlas-auth-button"
      disabled={disabled || loading}
      onClick={onClick}
      type={type}
    >
      <span className="atlas-auth-button-text">
        {loading ? <span aria-hidden="true" className="atlas-auth-spinner" /> : null}
        <span role={loading ? 'status' : undefined}>{children}</span>
      </span>
    </button>
  );
}
