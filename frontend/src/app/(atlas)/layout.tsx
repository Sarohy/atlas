import {
  AtlasActionsRail,
  AtlasHeader,
  AtlasHoldingsRail,
  AtlasNavigation,
} from '@/components/atlas/atlas-chrome';
import {
  ATLAS_APP_TITLE,
  ATLAS_NAV_ITEMS,
  ATLAS_ACTIONS,
  ATLAS_ACTIONS_TITLE,
} from '@/lib/api/atlas-shell';
import type { PortfolioNavItem } from '@/types/portfolio';

/**
 * Persistent chrome that wraps every tab in the atlas section.
 * The shell (header, nav, both rails) stays mounted when the user
 * navigates between tabs — only the {children} slot swaps out.
 */
export default function AtlasLayout({ children }: { children: React.ReactNode }) {
  // isActive is intentionally false for all items here — AtlasNavigation
  // derives the active state itself via usePathname() from the live URL.
  const navItems: readonly PortfolioNavItem[] = ATLAS_NAV_ITEMS.map((item) => ({
    ...item,
    isActive: false,
  }));

  return (
    <div className="atlas-portfolio-shell">
      <AtlasHeader appTitle={ATLAS_APP_TITLE} />
      <AtlasNavigation labels={navItems} />
      <div className="atlas-portfolio-layout">
        <AtlasHoldingsRail />
        {children}
        <AtlasActionsRail actions={ATLAS_ACTIONS} title={ATLAS_ACTIONS_TITLE} />
      </div>
    </div>
  );
}
