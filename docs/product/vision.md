# FanCue — Product Vision

*Phase 00 document. Assumptions marked [HYPOTHESIS] require fan interviews to validate.*

---

## Problem Statement

Live sport is increasingly consumed in fragmented sessions — fans step away for
work, family, commute, or sleep and return to a match already in progress. The
scoreboard shows the current state but provides no narrative explanation of
how it was reached. The gap between "score I see now" and "context I need to
understand it" is the FanCue problem space.

This problem is not solved by highlight reels (require video and attention),
ball-by-ball commentary feeds (require sequential reading), or generic sports
apps (show current state, not a personalized interval explanation).

---

## Primary Fan Persona

*This is a design hypothesis, not confirmed market research.*

**Name:** Aarav (composite persona)
**Age range:** 22–38
**Context:** Lives in India or the South Asian diaspora. Follows cricket
  seriously. May also follow domestic football (ISL/EPL).
**Behaviour:**
  - Watches matches across multiple sessions, often interrupted.
  - Uses a phone as primary viewing and browsing device.
  - Switches between match apps, social media, and work mid-match.
  - Wants to re-engage quickly without scrolling through commentary.
**Assumption [HYPOTHESIS]:** Prefers a concise, structured summary (< 60 seconds
  to read) over a full ball-by-ball replay.
**Assumption [HYPOTHESIS]:** Values factual accuracy over narrative entertainment.
**Assumption [HYPOTHESIS]:** Would value the same experience in Tamil (as the first
  evaluated regional language) as well as English.

---

## User Journey

1. Fan opens FanCue on their phone.
2. Fan searches for or selects the supported match they are exploring (historical replay).
3. Fan specifies an interval: "I missed overs 12 to 18" (whole-over boundaries).
4. FanCue presents a structured explanation of that interval:
   - Key events in chronological order with inspectable evidence.
   - Match state at the start and end of the interval.
   - Why the key events matter (contextual knowledge).
5. Fan optionally selects an evaluated language (English baseline, Tamil evaluated) or detail level.
6. Fan re-engages with the match with full context.

---

## Core Value Proposition

> FanCue closes the context gap between a score and its story.
> It tells you not just what happened, but why it matters — in seconds,
> grounded in verifiable facts.

---

## First-Release Scope

The first release establishes one complete, verified workflow:

1. A fan selects a **historical cricket match** (not live initially).
2. The fan specifies an **interval** (whole-over range).
3. FanCue **reconstructs** the interval from authoritative data.
4. FanCue **retrieves** relevant contextual knowledge from Qdrant.
5. FanCue **generates** a structured explanation verified against match facts.
6. The fan receives the explanation through a **functional web UI** with an evidence drawer.
7. If the AI explanation fails, the fan receives a **deterministic fallback**.

This is the complete first-release scope. Nothing beyond it is in scope.

---

## Non-Goals

- Real-time live match data (requires licensed feed — future).
- Predictions, betting tips, or fantasy recommendations.
- Video highlight playback.
- Social sharing features.
- User accounts and personalisation.
- Football (planned Phase 08, not first release).
- Mobile native app.
- More than one verified LLM provider at launch.

---

## Assumptions Requiring Fan Interviews

| Assumption | Validation method |
|---|---|
| Fans prefer structured summary over long-form commentary | Usability test with 5 cricket fans |
| Concise < 60 second reads are preferred | A/B test: short vs. detailed explanation |
| Tamil language option meaningfully increases utility | Prototype review with native Tamil-speaking cricket fans |
| Interval selection is the right interaction model | Usability sessions testing whole-over boundary controls |
| Historical matches are sufficient for first release | Fan survey on replay exploration vs. live context needs |

---

## Measurable User Outcomes

At end of first release, success is defined as:

1. A fan can specify a cricket match interval and receive a verified explanation
   within 30 seconds.
2. The explanation contains no verifiable factual errors (manual review of
   10 test queries).
3. The fallback path produces a useful structured summary when the LLM is
   unavailable.
4. At least 3 real cricket fans complete the full journey without assistance
   in a usability session.

These are not projections — they are acceptance criteria for Phase 09.
