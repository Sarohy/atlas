'use client';

import { useAuthSession } from './auth-session-provider';

export function LogoutButton() {
  const { signOut } = useAuthSession();

  return (
    <button className="atlas-portfolio-logout" onClick={() => void signOut()} type="button">
      <span aria-hidden="true">[ ]</span>
      <span>Logout</span>
    </button>
  );
}
