'use client';

import { useEffect, useState } from 'react';
import { HeroPanel } from '@/components/auth/hero-panel';
import { SignInForm } from '@/components/auth/sign-in-form';
import { useTheme } from '@/lib/hooks/use-theme';
import { AUTH_IMAGES } from '@/styles/theme';

// iPad Pro portrait is 1024px wide, so include it in the stacked layout.
const MOBILE_BREAKPOINT_PX = 1024;

function getIsMobileViewport() {
  if (typeof window === 'undefined') {
    return false;
  }

  return window.innerWidth <= MOBILE_BREAKPOINT_PX;
}

export function SignInScreen() {
  const { theme } = useTheme();
  const [isMobileViewport, setIsMobileViewport] = useState(getIsMobileViewport);

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
      return;
    }

    const mediaQueryList = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT_PX}px)`);
    const handleViewportChange = (event: MediaQueryListEvent) => {
      setIsMobileViewport(event.matches);
    };

    mediaQueryList.addEventListener('change', handleViewportChange);

    return () => mediaQueryList.removeEventListener('change', handleViewportChange);
  }, []);

  return (
    <div className="atlas-auth-shell" data-theme={theme}>
      <main className="atlas-auth-page" data-testid="atlas-auth-page">
        {isMobileViewport ? (
          <section className="atlas-auth-mobile">
            <img
              alt=""
              aria-hidden="true"
              className="atlas-auth-background atlas-auth-background--base"
              src={AUTH_IMAGES.backgroundBase}
            />
            <img
              alt=""
              aria-hidden="true"
              className="atlas-auth-background atlas-auth-background--grid"
              src={AUTH_IMAGES.backgroundGrid}
            />
            <div className="atlas-auth-stage">
              <div className="atlas-auth-card atlas-auth-card--mobile">
                <h1 className="atlas-auth-brand">ATLAS v7.0</h1>
                <SignInForm />
              </div>
            </div>
          </section>
        ) : (
          <section className="atlas-auth-desktop">
            <div className="atlas-auth-desktop-panel">
              <div className="atlas-auth-card atlas-auth-card--desktop">
                <h1 className="atlas-auth-brand">ATLAS v7.0</h1>
                <SignInForm />
              </div>
            </div>
            <div className="atlas-auth-desktop-visual">
              <HeroPanel />
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
