# FanCue — Motion & Fan-Delight Upgrade Report
**Document ID:** `docs/plan/phase-10-animation-report.md`  
**Phase:** Phase 10 / Phase 2 Motion & Fan-Delight Upgrade  
**Workspace:** `D:\FanCue`  
**Constitution:** `AGENTS.md` Compliant  

---

## 1. Executive Summary

This upgrade implements a purposeful, high-performance motion and fan-delight system for FanCue's Vite/React frontend, preserving 100% of the existing application architecture, backend contracts, deterministic cricket calculations, and evidence verification integrity.

The design identity directly derives from `Logo.png`: deep navy/teal surfaces (`#0d1320`), electric cyan accents (`#00f2fe`), deep blue structures, and magenta/red wicket dismissals (`#ffb4ab`). Motion is purposeful and story-driven, guiding the fan's eyes across the missed match interval without simulating live broadcasting or fabricated events.

---

## 2. Motion System Architecture & Design Tokens

Motion is declared via design tokens in `frontend/src/index.css` and bound to hardware-accelerated transforms and opacity transitions:

```css
:root {
  --motion-duration-fast: 150ms;
  --motion-duration-ui: 220ms;
  --motion-duration-hero: 700ms;
  --motion-ease-standard: cubic-bezier(0.2, 0, 0, 1);
  --motion-ease-decelerate: cubic-bezier(0, 0, 0.2, 1);
  --motion-ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
}
```

Keyframe animations defined:
- `fadeSlideUp`: Smooth upward translation (14px → 0px) with opacity fade for cards and containers (220ms).
- `fadeSlideIn`: Restrained upward fade (8px → 0px) for micro-elements.
- `growUp`: Baseline scaleY expansion (0 → 1) for over-by-over run bars.
- `pulseGlow`: Restrained cyan/magenta accent glow for focused moments.
- `badgeReveal`: Subdued scale and opacity reveal for the verification badge.

---

## 3. Enhancements Implemented

### A. Match Discovery — Welcoming Entrance
- Match selection cards render with a staggered entrance (`animationDelay: index * 60ms`) using `fadeSlideUp` (220ms).
- Desktop cards feature a restrained lift (`translateY(-2px)`) with subtle cyan border and glow (`box-shadow: 0 8px 24px rgba(0, 242, 254, 0.15)`).
- Keyboard `:focus-visible` provides high-contrast 2px cyan outline.
- Primary "Catch up →" CTA features subtle hover transition.

### B. Interval Selection — Tactful Chapters
- Tactical match phase chips (Powerplay, Middle Overs, Death) and Recent Over Window chips feature background, border-color, and box-shadow transitions (150ms).
- Selected chips display a clear cyan glow, bold border, and checkmark indicator.
- Submit button incorporates `isSubmitting` state with `aria-busy` and `disabled` state to strictly prevent duplicate submissions.

### C. Score Arc — Signature Count-Up
- Custom React hook `useCountUp(target, 700ms, enabled)` animates authoritative score deltas and ending scores smoothly across 700ms using quadratic deceleration.
- Animate only when valid numeric data has changed; never displays fabricated intermediate scores.
- Score changes remain 100% synchronized with the validated backend response.
- Start score (when user left) displays statically as the authoritative baseline.

### D. Runs-Per-Over Phase Barometer
- Renders only when valid `over_summary` facts exist in `evidence_packet.key_facts` from the deterministic engine. Never infers or invents individual over runs from totals.
- Over bars animate from the baseline (`growUp` keyframe) with staggered 40ms delays.
- Wicket overs are automatically tagged with a distinct `WKT` badge and magenta/coral accent bar.

### E. Crucial Moment Cards — Story Reveal
- Chronological turning moments (wickets, sixes/boundaries, high-scoring overs) are rendered from `evidence_packet.key_facts`.
- Cards enter staggered by 60ms (entrance duration capped at 220ms).
- Each moment card features an interactive "Inspect Ball Evidence" action (`.moment-card__action`).
- Clicking a moment selects the event, expands the evidence drawer, scrolls to the matching evidence item, and adds `.evidence-fact--highlighted` while non-selected facts receive `.evidence-fact--dimmed`.

### F. Catch-Up Generation Feedback
- When a catch-up request is initiated, duplicate submissions are disabled.
- The UI transitions into a dedicated status container (`.generation-loading`) displaying "Building your catch-up… Ground-truth Cricsheet calculation & verification in progress".
- Crossfades smoothly into the verified result.
- Recovers from errors with an interactive "Try Again" CTA.
- Deterministic fallback is clearly labelled without alarming red flashes or broken layouts.

### G. Evidence Drawer & Ball Inspection
- Drawer expansion and collapse animated smoothly.
- Facts cited by crucial moments highlight with cyan borders and a "★ Selected Ball Evidence" marker.
- Full provenance (`Cricsheet`, `ODC-By v1.0`, canonical URL) preserved at all times.

### H. Share Recap Feedback
- Copying recap to clipboard triggers a notification toast with `.toast--visible` (entrance 300ms, auto-dismiss 3000ms).
- If clipboard permissions fail in restricted or headless environments, displays a recoverable notice ("Copy failed — please copy manually") without falsely claiming success.

### I. Fan-Delight Sequence (Under 800ms)
The entire hero sequence unfolds in a clean, orchestrated timeline:
1. `0ms`: Context header and score nodes enter (`fadeSlideUp`).
2. `0–700ms`: Authoritative count-up finishes on exact delta (`+runs`) and end score.
3. `150ms`: Headline section fades in.
4. `200–350ms`: Over barometer and moment cards reveal in staggered order.
5. `450ms`: Verification badge (`.generation-badge`) reveals last.

---

## 4. Accessibility & Reduced Motion

The motion system fully honors `prefers-reduced-motion: reduce`:

1. **CSS Overrides:**
   All `animation-duration` and `transition-duration` tokens collapse to `0.01ms !important`, and transforms are suppressed.
2. **React Hook (`usePrefersReducedMotion`):**
   When reduced motion is active, `useCountUp` immediately renders target numbers with zero animation delay or frame requests.
3. **Screen Readers:**
   Live regions (`role="status"`, `aria-live="polite"`, `aria-busy`) announce updates without interference from visual motion.

---

## 5. Verification & Test Evidence

### Frontend Build & Linting
- **Command:** `npm run build`  
  **Result:** Exit code 0, 17 modules transformed, build in 357ms.
- **Command:** `npm run lint` (`oxlint`)  
  **Result:** 0 errors.

### Playwright End-to-End Suite (`tests/integration/test_playwright_e2e.py`)
- **`test_browser_catchup_user_journey`**: **PASSED**  
  Full end-to-end journey selecting India vs West Indies fixture, interval, verifying deltas, fallback badge, and provenance.
- **`test_browser_motion_moment_and_evidence_interaction`**: **PASSED**  
  Verifies score count-up settling, moment card rendering, clicking "Inspect Ball Evidence", automatic drawer expansion, evidence item highlighting, dimming of non-selected facts, drawer toggle, and share recap toast.
- **`test_browser_reduced_motion`**: **PASSED**  
  Emulates `prefers-reduced-motion: reduce`, verifying instantaneous display of authoritative numbers without animation delays.
- **`test_browser_responsive_390px_viewport`**: **PASSED**  
  Verifies complete 390px mobile layout, header containment, button hit targets, and score arc visibility without horizontal clipping.

### Backend Test Suite
- **Command:** `.venv\Scripts\python -m pytest -q --tb=short`  
  **Result:** 378 collected, 377 passed, 1 skipped. 100% passing across contracts, ingestion, state reconciliation, and golden intervals.

---

## 6. Changed Files

1. `frontend/src/index.css`: Added motion tokens, keyframes (`fadeSlideUp`, `growUp`, `pulseGlow`, `badgeReveal`), match-card hover/focus lift, chapter chip transitions, runs-per-over barometer, moment cards, evidence highlight/dimming, loading state styles, and comprehensive `@media (prefers-reduced-motion: reduce)` rules.
2. `frontend/src/App.tsx`: Added `usePrefersReducedMotion` hook, `useCountUp` hook, staggered entrance delays, `OverBarometer` component, `MomentCards` component with "Inspect Ball Evidence" interactive handler, interactive `EvidencePanel` highlighting, and duplicate submission prevention.
3. `tests/integration/test_playwright_e2e.py`: Expanded suite with 3 new Playwright tests covering motion interaction, reduced motion emulation, and 390px mobile responsiveness.
4. `docs/plan/phase-10-animation-report.md`: Created comprehensive motion and fan-delight documentation.

---

## 7. Known Limitations & Boundary Integrity

- Live synchronization and streaming TV frame matching remain non-goals per `AGENTS.md`.
- No simulated probabilities, win predictors, or confetti effects were introduced. All displayed scores and moments derive directly from verified Cricsheet ball-by-ball facts.
