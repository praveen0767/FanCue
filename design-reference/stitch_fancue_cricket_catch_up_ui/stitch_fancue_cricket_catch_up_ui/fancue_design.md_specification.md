# FanCue Design System & Product Specification (DESIGN.md)

## 1. Product Identity & Promise
**FanCue** — Catch the moment. Understand the game.
*"You missed part of the match. We tell you the story, show the moments that mattered, and let you check the evidence."*

A distinctive, premium historical cricket catch-up experience built strictly on verified match intervals and structured evidence, not generic sports dashboards, scorecards, fantasy apps, or unconstrained chatbots.

---

## 2. Core Color Tokens (Derived from FanCue Brand Mark)
*   **Background Canvas (Midnight Navy):** `#070D18`
*   **Surface Layer 1 (Card Container):** `#0E1726` / `rgba(14, 23, 38, 0.85)`
*   **Surface Layer 2 (Elevated Panels):** `#14223A`
*   **Surface Layer 3 (Active / Focus Fill):** `#1B2D4D`
*   **Primary Accent (Electric Cyan):** `#00F2FE` / `#38BDF8` (Used for primary interactions, verified badges, active selection)
*   **Secondary Visual Accent (Hyper Blue):** `#2563EB` / `#3B82F6` (Progress arcs, timeline volume, badges)
*   **Alert & Impact Accent (Magenta / Coral):** `#FF2E7E` / `#F43F5E` (Wickets, milestone triggers, danger boundaries)
*   **Text Colors:**
    *   Primary Text: `#F8FAFC` (Cool Off-White)
    *   Secondary Text: `#94A3B8` (Slate Blue-Gray)
    *   Tertiary Muted: `#64748B` (Subtle metadata, disclaimer)
*   **Border Accents:** `rgba(56, 189, 248, 0.2)` on interactive elements, `rgba(255, 255, 255, 0.08)` for structural cards.

---

## 3. Typography & Numerical Hierarchy
*   **Display / Headlines:** Sans-Serif Bold (Inter / Outfit / system UI), tracking -0.02em. Factual, editorial clarity.
*   **Cricket Numerical Data:** Tabular figures (`font-variant-numeric: tabular-nums`) for score arcs (e.g. `142/3 → 186/6 (+44/3)`), run rates, over counts.
*   **Story & Explanations:** 15px - 16px, line-height 1.6, legible slate tones.

---

## 4. Component System & State Architecture

### A. Match Discovery Cards (Screen 1)
*   **Historical Replay Badge:** Persistent tag `HISTORICAL REPLAY · CRICSHEET ARCHIVE`
*   **Format Pill:** T20 International / ODI / Test with match venue, date, and verified balls recorded.
*   **Primary CTA:** "Catch up" with electric cyan hover glow and arrow icon.
*   **States:** Default, Hover, Loading Skeleton, Empty State, Offline/Recoverable Error state.

### B. Natural Interval Selector Chips (Screen 2)
*   Derived from format boundaries without exposing database coordinates (`after_over`):
    *   *Natural Match Phases:* Powerplay, Middle Overs, Death Overs
    *   *Recent Window Chips:* Last 3 Overs, Last 5 Overs, Last 6 Overs, Last 12 Overs, Full Innings
    *   *Secondary Drawer:* "Choose exact overs" (slider / custom bounds)
*   **States:** Unselected, Active Selected (Cyan ring with soft glow), Disabled/Unavailable, Live Mini-Preview summary.

### C. Story Recap Engine (Screen 3)
1.  **Quiet Context Header:** Match fixture, innings, interval boundaries, Honest Response Mode Badge (`AI explanation · facts checked` vs. `Plain version · no AI`).
2.  **Verified Headline:** Numeric, rule-justified headline (e.g., *"3 wickets fell in this interval as run rate dropped to 6.2"*).
3.  **The Score Arc ("WHEN YOU LEFT → NOW"):**
    *   Start state: Score / Wickets / Over (e.g., `124/2 (14.0)`)
    *   Delta Node: `+48 runs · 3 wickets · 36 balls`
    *   End state: Score / Wickets / Over (e.g., `172/5 (20.0)`)
4.  **Runs-Per-Over Interactive Timeline:**
    *   Accessible bars with run tallies and red/magenta wicket pins (`W`).
    *   Interactive click-to-inspect ball event with synchronized card highlight.
5.  **Chronological Story-Beat Cards:**
    *   Wicket (Magenta dot + bowler/batsman fact), Boundary flurry, Milestone (50/100), Big Over.
    *   "Inspect Event / See the Ball" button.
6.  **"Why it Matters" Broadcast Synthesis:**
    *   Brief conversational takeaways, resilient to missing/unverified AI generations.
7.  **Evidence Drawer (Inspect the Evidence):**
    *   Collapsible by default.
    *   Shows delivery event references, official Cricsheet ball index, runs, dismissal metadata, and calculation rules.
8.  **Bounded Follow-up Interaction:**
    *   Scoped prompts ("What changed during this interval?", "Explain this selected moment?").
9.  **Share Recap Action:** One-click copy formatted plain-text recap with toast feedback (Success / Failure states).

---

## 5. Viewport Adaptation
*   **Desktop (1440px):** Two-column editorial split on Story screen (Score Arc + Timeline + Story Cards on left/center; Sticky Evidence & Follow-up on right).
*   **Mobile (390px):** Single-column stacked stream, sticky bottom navigation & drawer sheets, high touch targets (>=44px), zero horizontal overflow.
