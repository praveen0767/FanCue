# FanCue — Fan Validation Plan (V1)

**Version:** 1.0
**Phase:** 01 — Product Specification
**Last updated:** 2026-10-11

> This document defines two validation tracks: direct fan conversations and an
> offline scenario evaluation using real match data. No fan interviews have
> occurred yet. Do not cite this plan as evidence of validated assumptions.
> Update this document with actual results when sessions occur.

---

## Purpose

The product hypotheses in `vision.md` and `user-scenarios.md` are unvalidated.
This plan creates a method to test them before Phase 06 UI investment becomes
difficult to reverse.

The plan has two parts:

1. **Direct fan feedback** — short conversations with cricket fans.
2. **Offline scenario evaluation** — manually checked match intervals with a
   future golden set.

---

## Part A: Direct Fan Feedback

### Objective

Determine whether the assumed fan problem (missed interval, context gap) is
real, frequent, and important enough that a product like FanCue would be used.

### Participant criteria

- Follows cricket actively (watches at least 5 matches per year).
- Has missed part of a match at least once in the past 6 months.
- Has not been briefed on FanCue's concept before the session.
- Participation is voluntary and informed.

### Target: 5 conversations

5 is not statistically representative. It is the minimum to identify
patterns or divergence in responses. Results must not be generalized.
If all 5 give strongly aligned responses, that increases (but does not
prove) confidence. If responses diverge widely, additional conversations
are needed before making product decisions.

### Interview structure

Each session: 20–30 minutes, conversational, not a structured questionnaire.

**Opening (5 min) — understand the context:**
- "Tell me about the last time you missed part of a cricket match."
- "What was the situation — what were you doing when you left?"
- "When you came back, what was the first thing you looked at?"

**Problem exploration (10 min) — neutral, factual questions:**
- "What information did you look for when you came back?"
- "How did you figure out what you had missed?"
- "What was difficult or frustrating about that process?"
- "Was there anything you wanted to know that you couldn't find easily?"

**Concept probe (10 min) — show a description or paper prototype if available:**
- "Here's what FanCue would do: [describe, do not oversell]. Does that address
  anything you described?"
- "When you missed a match, what would you have needed first — the score summary,
  the key events, or an explanation of why things changed?"
- "If you could get this in Tamil / Hindi / English — which would you choose,
  and does that matter to you for cricket specifically?"
- "If the app said 'I missed part of this over and can't show you a complete
  picture,' would that be more or less trustworthy than one that always showed
  something?"

**Closing (5 min) — surface concerns:**
- "What would make you distrust this kind of product?"
- "Is there anything about the idea that concerns you?"

### Questions to avoid

- Leading: "Would you love an app that ..." → Avoid.
- Hypothetical commitment: "Would you pay for this?" → Too early; avoid.
- Assumptions embedded in questions: "Since fans always need context ..." → Avoid.

### What to record

After each session:
- Verbatim quotes on key points.
- Whether the participant described the problem without being prompted.
- Which information type they mentioned first (score, events, explanation).
- Language preference for cricket specifically.
- Level of expressed concern about AI-generated content vs. manual summaries.
- Any concern about trust, data source, or accuracy.

Record in `docs/evaluation/fan-conversations.md` as each session occurs.
Do not create this file until at least one real session has taken place.

---

## Part B: Offline Scenario Evaluation

### Objective

After Phase 03 (engine) and Phase 04 (retrieval) are complete, evaluate the
quality of engine output, retrieval results, AI explanations, and fallbacks
against a manually curated golden set of cricket intervals.

### Golden set design (Phase 04/05)

Propose an initial set of 15 intervals across at least 2 distinct matches
(subject to licensing in Phase 02). The set must cover:

| Category | Minimum intervals |
|---|---|
| Ordinary scoring (no wickets, no extras) | 2 |
| Exactly one wicket in interval | 3 |
| Multiple wickets in interval | 2 |
| High-scoring over (>= 15 runs) | 2 |
| Extras present (wide, no-ball, bye) | 2 |
| Innings boundary (start at over 0 or end at last over) | 2 |
| Short interval (2 overs) | 1 |
| Long interval (>= 15 overs) | 1 |

Total: 15 intervals minimum. Document match_id, innings_index, start
boundary, end boundary, and manually verified ground truth for each.

The golden set file: `tests/evaluation/cricket_golden_set.yml`
Status: **Not created yet.** Created in Phase 04 after dataset is selected.

### Evaluation dimensions

For each golden interval, evaluate:

#### 1. Source-fact accuracy

- Engine computed runs == manually verified runs from source.
- Engine computed wickets == manually verified wickets from source.
- All wicket events in the interval appear in the event list.
- No extra wicket events appear (events outside the interval boundary).

**Pass threshold:** 100% accuracy on numerical values for all 15 intervals.

---

#### 2. Evidence-reference validity

- Every `doc_id` cited in the AI explanation exists in the evidence packet.
- Every `source_event_id` cited exists in the canonical event sequence.

**Pass threshold:** 0 invalid references across all 15 intervals.

---

#### 3. Unsupported-claim count

Count claims in the explanation that cannot be directly traced to either:
(a) the engine's authoritative state output, or
(b) a retrieved document in the evidence packet.

Examples of unsupported claims:
- "This was the highest partnership in the match" — not in engine output.
- "The bowler's recent form suggests..." — not in retrieved documents.

**Pass threshold:** < 3 unsupported claims per explanation (V1 quality bar).
Document each unsupported claim found.

---

#### 4. Language comprehension review (Tamil)

Only required after Tamil output is enabled (Phase 09):
- Cricket terms translated correctly and consistently.
- Player and team names appropriately transliterated (not translated).
- Numerical values are correct.
- Meaning is preserved, not paraphrased into something different.

Reviewer: A Tamil speaker with cricket knowledge who has not seen the
English original first.

**Pass threshold (AC-10):** >= 8 of 10 reviewed intervals approved with
no critical factual errors.

---

#### 5. Fallback behaviour

Run each interval with `SKIP_LLM_IN_TESTS=true`. Confirm:
- Fallback response produced (not an error).
- Fallback contains engine state difference.
- Fallback is labelled as non-AI-generated.
- Numerical values in fallback match engine output.

**Pass threshold:** 100% of intervals produce a valid fallback response.

---

#### 6. Latency measurement

For each interval, record:
- Engine processing time (ms)
- Retrieval time (ms)
- LLM call time (ms, when available)
- Verification time (ms)
- Total end-to-end time (ms)

Calculate median and 95th percentile across 15 intervals.

**Target (AC-11):** Median <= 30,000 ms total. Not a gate — a measurement.
Report actual values without adjustment.

---

### Reviewer disagreement handling

When two reviewers disagree on whether a claim is unsupported or a translation
is acceptable:

1. Both reviewers document their reasoning.
2. A third reviewer casts a deciding opinion.
3. Both the disagreement and resolution are recorded in the evaluation log.
4. Do not silently average scores or suppress disagreements.

---

### Baseline comparison: deterministic recap vs. AI explanation

For each golden interval, produce both:
- The deterministic fallback (engine-only structured summary).
- The AI explanation (when the LLM is available).

Compare on:
- Factual accuracy: expect the same (both grounded in engine output).
- Completeness: does the AI add meaningful context that the fallback lacks?
- Trust: does the AI explanation contain any claim the fallback does not,
  and is that claim verifiable?

If the AI explanation adds no verifiable value over the deterministic fallback
for a category of intervals, that is an important finding. Do not assume that
AI provides value simply because it produces more natural prose.

Record findings in `docs/evaluation/ai-vs-fallback-comparison.md` (Phase 05).

---

## Plan Status and Timeline Dependencies

| Task | Depends on | Estimated phase |
|---|---|---|
| Fan conversation guide is ready | This document | Now (Phase 01) |
| At least 1 fan conversation | Guide ready + participant available | Phase 01–02 |
| Golden set defined | Phase 02 dataset selection | Phase 04 |
| Numerical accuracy evaluation | Phase 03 engine | Phase 03 |
| Retrieval quality evaluation | Phase 04 ingestion | Phase 04 |
| AI explanation evaluation | Phase 05 orchestration | Phase 05 |
| Latency measurement | Phase 06 end-to-end | Phase 06 |
| Tamil language review | Phase 05 LLM + Tamil prompt | Phase 09 |
| Usability sessions | Phase 06 UI complete | Phase 09 |

---

## What This Plan Cannot Do

- Confirm that the fan problem is universal or common.
- Replace quantitative user research with 5 conversations.
- Prove that FanCue's interval model is the right interaction paradigm.
- Guarantee that identified improvements will be implementable within the
  assignment timeline.

These are known limitations. They must be stated in the Phase 09 submission.
