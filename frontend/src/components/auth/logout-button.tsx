'use client';

import { useAuthSession } from './auth-session-provider';

export function LogoutButton() {
  const { signOut } = useAuthSession();

  return (
    <button className="atlas-portfolio-logout" onClick={() => void signOut()} type="button">
      <svg
        aria-hidden="true"
        className="w-4 h-4"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        viewBox="0 0 24 24"
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* door frame */}
        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
        {/* arrow pointing right (exit) */}
        <polyline points="16 17 21 12 16 7" />
        <line x1="21" x2="9" y1="12" y2="12" />
      </svg>
      <span>Logout</span>
    </button>
  );
}
