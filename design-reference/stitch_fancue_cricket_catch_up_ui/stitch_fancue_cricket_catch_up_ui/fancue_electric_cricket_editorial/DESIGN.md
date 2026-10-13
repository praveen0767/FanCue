---
name: FanCue Electric Cricket Editorial
colors:
  surface: '#0d1320'
  surface-dim: '#0d1320'
  surface-bright: '#333948'
  surface-container-lowest: '#080e1b'
  surface-container-low: '#161b29'
  surface-container: '#1a1f2d'
  surface-container-high: '#242a38'
  surface-container-highest: '#2f3543'
  on-surface: '#dde2f5'
  on-surface-variant: '#b9cacb'
  inverse-surface: '#dde2f5'
  inverse-on-surface: '#2a303f'
  outline: '#849495'
  outline-variant: '#3a494b'
  surface-tint: '#00dce6'
  primary: '#e0fdff'
  on-primary: '#00373a'
  primary-container: '#00f2fe'
  on-primary-container: '#006a70'
  inverse-primary: '#00696f'
  secondary: '#b4c5ff'
  on-secondary: '#002a78'
  secondary-container: '#0053db'
  on-secondary-container: '#cdd7ff'
  tertiary: '#fff5f6'
  on-tertiary: '#66002b'
  tertiary-container: '#ffcfd8'
  on-tertiary-container: '#be0057'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#6ff6ff'
  primary-fixed-dim: '#00dce6'
  on-primary-fixed: '#002022'
  on-primary-fixed-variant: '#004f53'
  secondary-fixed: '#dbe1ff'
  secondary-fixed-dim: '#b4c5ff'
  on-secondary-fixed: '#00174b'
  on-secondary-fixed-variant: '#003ea8'
  tertiary-fixed: '#ffd9e0'
  tertiary-fixed-dim: '#ffb1c2'
  on-tertiary-fixed: '#3f0018'
  on-tertiary-fixed-variant: '#8f0040'
  background: '#0d1320'
  on-background: '#dde2f5'
  surface-variant: '#2f3543'
typography:
  display-hero:
    fontFamily: Outfit
    fontSize: 56px
    fontWeight: '800'
    lineHeight: 64px
    letterSpacing: -0.02em
  display-hero-mobile:
    fontFamily: Outfit
    fontSize: 36px
    fontWeight: '800'
    lineHeight: 42px
    letterSpacing: -0.02em
  score-lead:
    fontFamily: Outfit
    fontSize: 44px
    fontWeight: '700'
    lineHeight: 48px
    letterSpacing: -0.03em
  score-lead-mobile:
    fontFamily: Outfit
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 36px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Outfit
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Outfit
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Outfit
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  label-telemetry:
    fontFamily: Space Grotesk
    fontSize: 13px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.06em
  label-tag:
    fontFamily: Space Grotesk
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 14px
    letterSpacing: 0.08em
  data-tabular:
    fontFamily: Space Grotesk
    fontSize: 15px
    fontWeight: '500'
    lineHeight: 18px
    letterSpacing: -0.01em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-desktop: 1.5rem
  margin: 1rem
  margin-tablet: 1.5rem
  margin-desktop: 2.5rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2.5rem
---

## Brand & Style

The design system establishes a premium, broadcast-grade cricket catch-up and live telemetry interface. Drawing directly from the visual intensity of the brand mark—where the kinetic seam of a cricket ball fuses with an electric play button and audio-visual pulses—the system delivers adrenaline, analytical rigor, and frictionless catch-up experiences for global cricket enthusiasts.

### Target Audience & Emotional Response
The experience caters to modern cricket followers: fans seeking rapid recap reels, ball-by-ball momentum analytics, deep tactical telemetry, and live milestone alerts. The UI evokes:
- **Kinetic Precision:** Instantaneous comprehension of match state, run-rates, and predictive win margins.
- **Broadcast Immersion:** Visual cues reminiscent of elite sports telecasts—crisp contrast, glowing high-impact status signals, and dark stadium ambiance.
- **Confident Authority:** Clear data hierarchies with tabular figures ensuring stress-free legibility during tense final-over chases.

### Visual Style
A blend of **Modern Sports Editorial** and **Refined Dark-Mode Cybernetics**:
- Deep navy and teal obsidian backdrops prevent eye fatigue during prolonged viewing.
- High-frequency electric cyan and stadium blue handle active interaction, scrubbing timelines, and verified live stats.
- Vivid magenta and coral red provide surgical urgency for high-stakes events (wickets, reviews, century milestones).
- Hairline structural grids and micro-glow accents preserve clarity without devolving into visual noise.

## Colors

The palette directly extrapolates the vibrant, backlit aesthetic of the brand asset. It relies on deep optical depth paired with photon-charged accents.

### Color Roles & Hierarchy
- **Canvas & Background (`#0B111E`):** Pure deep midnight obsidian teal. Ground zero for full-bleed live streams and dense statistical cards.
- **Surface Elevation 1 (`#0F172A`):** Match overview containers, module cards, and grouped feeds.
- **Surface Elevation 2 (`#141E33`):** Active player cards, flyout drawers, elevated scorecards, and floating controls.
- **Primary Interactive (`#00F2FE` - Electric Cyan):** Primary CTAs ("Catch Up to Live", timeline scrub handles, ball-by-ball boundaries `4s`), active filter toggles, verified highlight flags.
- **Secondary Accent (`#2563EB` - Stadium Blue):** Structural fills, team identifier backings, progressive telemetry bars, and secondary interactions.
- **Tertiary Alert (`#FF2E7E` - Coral Magenta):** Critical game events (`WICKET`, `DRS REVIEW`, century celebration markers, live countdown beacons).
- **Text & Contrast Layers:**
  - `Cool White (#F8FAFC)`: Primary numerical scores, match status, player headings.
  - `Muted Slate (#94A3B8)`: Secondary descriptions, bowler run-ups, commentary snippets.
  - `Tertiary Slate (#64748B)`: Over numbers, historical date stamps, inactive meta labels.
  - `Hairline Grid (`rgba(56, 189, 248, 0.16)`): Structural separators and card outlines.

## Typography

The typography architecture uses a disciplined three-tier stack:
1. **Headlines & Scores (Outfit):** Delivers aerodynamic, geometric weight reminiscent of modern broadcast overlays and athletic branding.
2. **Editorial Commentary & Body (Inter):** Guarantees flawless reading rhythm across high-density match summaries, ball commentaries, and match reports.
3. **Telemetry, Overs & Metadata (Space Grotesk):** Enforces a technical, track-side personality with open geometric numerals, perfect for strike rates, run rates (`CRR 8.42 | RRR 10.15`), and ball speed meters (`148.6 km/h`).

### Tabular Figures Implementation
All numeric score trackers, bowling economy columns, and over counts (`19.4`) must enable OpenType tabular numbers (`tnum`) to eliminate layout jitter during live socket updates.

## Layout & Spacing

The layout embraces a responsive, dynamic 12-column grid designed for split-screen highlight catching, side-docked pitch maps, and continuous ball-by-ball video feed anchoring.

### Spatial Rhythms
- **Mobile (< 768px):** 4-column layout with `1rem` outer margins. Match scoreboards take sticky top placement with horizontal scrolling "Key Cues" timelines directly beneath video previews.
- **Tablet (768px – 1024px):** 8-column layout with `1.5rem` margins and gutters. Splits screen between the master match cue feed (60% width) and deep player metrics (40% width).
- **Desktop (> 1024px):** 12-column wide grid bound to a max container width of `1440px`. Accommodates simultaneous high-definition stream player, real-time ball arc wagon wheels, and catch-up reel playlist.

Component padding relies strictly on the `space-*` scale to maintain clean structural cadence across score badges, table rows, and alert banners.

## Elevation & Depth

Visual hierarchy abandons traditional muddy dropshadows in favor of an emitted light and layered obsidian model:

### 1. Tonal Surface Stacking
- **Canvas Base:** `#0B111E` gives maximum visual contrast for colorful player kits and ball trails.
- **Card Tier 1:** `#0F172A` layered with a 1px border of `rgba(56, 189, 248, 0.14)`.
- **Raised Interactive Layer:** `#141E33` with subtle interior top highlight `linear-gradient(180deg, rgba(255, 255, 255, 0.05) 0%, rgba(255, 255, 255, 0) 100%)`.

### 2. Kinetic Neon Glow & Highlights
- **Active State Scrubbers & Primary CTAs:** Glow shadow using `0 0 20px rgba(0, 242, 254, 0.35)`.
- **Wicket & Milestone Events:** Glow pulse using `0 0 24px rgba(255, 46, 126, 0.4)`.

### 3. Glassmorphic Overlays
Broadcast overlays and timeline control HUDs floating over match footage use an ultra-dark frosted glass treatment:
- Background: `rgba(11, 17, 30, 0.78)`
- Backdrop Blur: `16px`
- Border: `1px solid rgba(56, 189, 248, 0.22)`

## Shapes

The system implements **Level 2 (Rounded)** shape geometry, pairing athletic speed with ergonomic tactile usability:
- Standard buttons, telemetry chips, and modular match cards use `0.5rem` (`8px`).
- Catch-up reel cards, modal dialogs, and video player containers leverage `rounded-lg` (`1rem` / `16px`).
- Wicket counters, ball outcome markers (e.g., `[6]`, `[W]`, `[.]`), and status pips use full circular pill styles to mimic cricket ball geometry.

## Components

### Buttons
- **Primary Action ("Catch Up to Live", "Watch Reel"):** Electric Cyan background (`#00F2FE`), text `#0B111E` (weight 700), subtle cyan aura on hover, rounded to `0.5rem`.
- **Secondary Action ("Scorecard", "Match Telemetry"):** Background `#141E33`, border `1px solid rgba(56, 189, 248, 0.25)`, text `#F8FAFC`.
- **Critical / Live Marker ("LIVE", "HAWK-EYE"):** Magenta-Coral fill (`#FF2E7E`), white text, animated gentle glow.

### Ball-by-Ball Timeline & Event Cues (Custom Flagship Component)
- Horizontal strip displaying past balls of the over.
- Balls represented as `32px` circular badges:
  - Dot Ball (`.`): Background `#141E33`, text `#64748B`.
  - Boundary Four (`4`): Cyan outline, text `#00F2FE`.
  - Maximum Six (`6`): Cyan solid background, text `#0B111E`, high glow.
  - Wicket (`W`): Coral Magenta solid (`#FF2E7E`), text `#FFFFFF`, pulsating ring indicator.

### Match Cards & Live Score Widgets
- Container built with `#0F172A` background and `rgba(56, 189, 248, 0.16)` border.
- Team abbreviation in `Space Grotesk` uppercase, lead score in `Outfit` 32px/44px tabular numerals.
- Live over indicator pill pinned to the top right with an electric pulse dot.

### Chips & Filter Tabs
- Height `32px`, pill or `8px` roundedness.
- Inactive: `#0F172A`, text `#94A3B8`.
- Active: `#2563EB` background with `#00F2FE` border stroke, text `#F8FAFC`.

### Form Fields & Search Inputs
- Used for quick player search, match archives, and commentary jump.
- Background: `#0B111E`, inset border `1px solid rgba(148, 163, 184, 0.2)`.
- Focused: Border transitions to `#00F2FE` with `0 0 12px rgba(0, 242, 254, 0.25)` outer bloom.