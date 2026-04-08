# ATLAS — Color Palette & Design Direction
**For Developer / Figma Designer Use**
**Version 1.0 | March 31, 2026**

---

## Design Concept

ATLAS is a professional trading decision support system used by one operator managing a ~$24M portfolio in high-stakes market conditions. The interface should feel like a premium institutional terminal — not a retail trading app, not a generic SaaS dashboard.

**The aesthetic direction:** Dark, precise, data-dense, trust-inspiring. Think Bloomberg Terminal meets modern design sensibility. Every color carries meaning. Every element earns its space.

**The one thing someone will remember:** The Regime Banner. The massive color-coded status bar that tells you in one glance whether you can trade today. Green, amber, or red — nothing else matters until you look at that.

---

## Color Palette

### Background Colors
| Name | Hex | Use |
|------|-----|-----|
| Background Primary | `#0A0E1A` | Main app background — very dark navy |
| Background Secondary | `#0F1524` | Card / panel backgrounds |
| Background Tertiary | `#161D2F` | Hover states, subtle differentiation |
| Background Elevated | `#1C2438` | Modals, dropdowns, elevated surfaces |

### Text Colors
| Name | Hex | Use |
|------|-----|-----|
| Text Primary | `#E8EDF5` | Main content, headings |
| Text Secondary | `#8A95A8` | Labels, metadata, secondary info |
| Text Muted | `#4A5568` | Timestamps, inactive states |
| Text Inverse | `#0A0E1A` | Text on colored backgrounds |

### Status Colors — CRITICAL
These colors carry framework meaning throughout the entire system. Use them consistently and never decoratively.

| Name | Hex | Meaning | Use |
|------|-----|---------|-----|
| Crisis Red | `#E53E3E` | Hard halt — do not trade | VIX >30, Brent >$108, active hard stops |
| Crisis Red Background | `#2D1515` | Red status backgrounds | Regime banner (crisis), alert panels |
| Caution Amber | `#DD6B20` | Elevated risk — proceed carefully | VIX 24-30, oil approaching threshold |
| Caution Amber Background | `#2D1F0F` | Amber status backgrounds | Regime banner (caution) |
| Partial Deploy Yellow | `#D69E2E` | Conditions improving — limited deploy | Framework gates partially open |
| Partial Deploy Background | `#2D250A` | Yellow status backgrounds | Regime banner (partial deploy) |
| Deploy Green | `#38A169` | All frameworks clear | Full deploy authorized |
| Deploy Green Background | `#0F2318` | Green status backgrounds | Regime banner (deploy), positive indicators |

### Data Colors
| Name | Hex | Use |
|------|-----|-----|
| Price Up | `#48BB78` | Positive price change |
| Price Down | `#FC8181` | Negative price change |
| Neutral | `#A0AEC0` | Flat / unchanged |
| Conviction High | `#4299E1` | Conviction score 80+ |
| Conviction Mid | `#ECC94B` | Conviction score 60-79 |
| Conviction Low | `#FC8181` | Conviction score below 60 |

### Border & Divider Colors
| Name | Hex | Use |
|------|-----|-----|
| Border Subtle | `#1E2A3F` | Card borders, table dividers |
| Border Emphasis | `#2D3F5C` | Active selections, focus states |
| Border Accent | `#4A6FA5` | Highlighted elements |

### Accent Colors
| Name | Hex | Use |
|------|-----|-----|
| Primary Accent | `#4A90D9` | Primary buttons, links, active nav |
| Primary Accent Hover | `#3A7BC8` | Button hover states |
| Secondary Accent | `#667EEA` | Secondary interactive elements |

---

## Typography

### Font Selections
**Display / Headings:** `IBM Plex Mono` — monospace, technical, precise. Available free via Google Fonts. Use for: ticker symbols, prices, regime banner, conviction scores, any number-heavy display.

**Body / UI:** `Inter` — clean, readable, purpose-built for screens. Use for: descriptions, briefing text, labels, navigation, general prose.

**Data Tables:** `IBM Plex Mono` — all numerical data should be monospaced for visual alignment in tables.

### Type Scale
| Name | Size | Weight | Use |
|------|------|--------|-----|
| Display | 48px | 700 | Regime banner status text |
| Heading 1 | 28px | 600 | Screen titles |
| Heading 2 | 20px | 600 | Section headings, card titles |
| Heading 3 | 16px | 600 | Sub-headings |
| Body Large | 15px | 400 | Briefing text, descriptions |
| Body | 14px | 400 | General UI text |
| Small | 12px | 400 | Labels, metadata, timestamps |
| Ticker | 18px | 700 | IBM Plex Mono — ticker symbols |
| Price | 20px | 600 | IBM Plex Mono — price display |
| Score | 36px | 700 | IBM Plex Mono — conviction score display |

---

## Component Design Notes

### Regime Banner
The most important element in the entire system. Should be unmissable.
- Full width, approximately 80px tall
- Background color changes based on regime state (use Background colors from Status Colors above)
- Left side: regime status text in Display size (CRISIS HALT / CAUTION / PARTIAL DEPLOY / DEPLOY)
- Right side: key metrics — VIX, Brent, Cash %
- Subtle animated pulse on CRISIS HALT state (CSS pulse animation, not distracting)

### Framework Status Tiles
Four tiles in a row. Each tile:
- Card background with subtle border
- Top: framework name in small caps
- Middle: current value in large monospace
- Bottom: threshold value in muted text
- Left edge: 4px vertical colored bar (red / amber / green) — this is the instant visual indicator
- Hover state: slightly elevated background

### Conviction Score Display
When showing a conviction score (0-100):
- Large circular gauge or arc graphic
- Score number in center in monospace 36px bold
- Color of gauge matches conviction level (blue 80+, yellow 60-79, red below 60)
- Small label below: "Conviction Score"

### Action Queue Items
Each pending action in the queue:
- Left: colored dot matching action type (green = buy/add, red = exit/sell, yellow = trim)
- Ticker symbol bold
- Action type label
- One-line reason in muted text
- Right: Confirm (primary button) and Dismiss (ghost button)
- Border between items, no full card for each — list style

### Data Tables
All tables:
- Dark header row with slightly lighter background
- Alternating row colors (primary and secondary backgrounds)
- Monospace font for all numbers
- Color-coded cells for price changes (red/green)
- Hover row highlight
- Sortable columns (click header to sort)
- No excessive padding — data density is important

### Modals
- Overlay: `rgba(0,0,0,0.75)` backdrop
- Modal background: Background Elevated
- Border: Border Emphasis with subtle glow on border for critical modals
- Critical modals (Human Confirmation): red accent border on left edge
- Close button: top right corner
- Primary action button: full width at bottom of modal

---

## Iconography

Use a consistent icon library. Recommended: **Lucide Icons** (open source, clean, professional).

Key icons:
- Shield: Framework Status
- Target / Crosshair: Wargame Mode
- BarChart2: Portfolio
- Terminal: Morning Briefing
- Clock: Decision Log
- Radar / Scan: Stream 2 Scanner
- AlertTriangle: Warning / Caution
- CheckCircle: Confirmed
- XCircle: Blocked / Denied
- TrendingUp / TrendingDown: Price direction
- Lock: Blocked action (cash floor hit)

---

## Motion & Animation

Keep animations purposeful and minimal. This is a professional tool, not a consumer app.

**Use animation for:**
- Regime banner state transitions (color crossfade, ~300ms)
- Conviction score gauge fill on load (~800ms ease-out)
- New briefing text appearing (fade in, staggered line by line)
- Alert pulse on CRISIS HALT (subtle, looping)
- Modal open/close (scale + fade, ~150ms)
- Row highlight on hover (instant background color change)

**Never use animation for:**
- Continuous decorative motion that serves no function
- Loading spinners on data that should be fast
- Page transitions between main screens (instant navigation preferred)

---

## Spacing System

Base unit: 4px. All spacing should be multiples of 4.

| Token | Value | Use |
|-------|-------|-----|
| xs | 4px | Tight internal padding |
| sm | 8px | Component internal spacing |
| md | 16px | Standard content padding |
| lg | 24px | Section spacing |
| xl | 32px | Major section gaps |
| 2xl | 48px | Screen-level spacing |

---

## What NOT to Do

- No gradients on backgrounds (flat dark colors only — gradients are distracting in a data-dense interface)
- No rounded corners above 6px radius (sharp corners read as professional / precise)
- No drop shadows except on modals and elevated surfaces
- No decorative illustrations or icons
- No marketing-style hero sections or large empty spaces
- No purple — it reads as consumer / generic AI
- No white backgrounds anywhere — everything stays dark
- Do not use font sizes above 48px except for the Regime Banner display
- Do not use more than 3 font weights on any single screen

---

*End of Color Palette & Design Direction Document*
