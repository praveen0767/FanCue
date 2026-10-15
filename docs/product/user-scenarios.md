# FanCue — Fan User Scenarios (V1)

> **Current deployment scope (2026-10-15):** These scenarios describe the experience when contextual retrieval is available. Qdrant retrieval is optional and disabled in the current Render blueprint; the deployed historical catch-up must remain useful from deterministic facts and event evidence alone.

**Version:** 1.0
**Phase:** 01 — Product Specification
**Last updated:** 2026-10-11

> These are precise scenario specifications, not proof that actual users have
> validated the problem. All persona characteristics are labelled as hypotheses.
> Scenarios are written with enough detail to drive integration test cases.

---

## Trust Rules (Applicable to All Scenarios)

Before reading the scenarios, establish these non-negotiable product truths:

1. **The current score is not an explanation.** A score delta alone is not
   FanCue's value — the context and reasoning around it are.
2. **The model is not the source of match truth.** The deterministic engine is.
3. **Similarity ranking alone does not prove factual correctness.** A retrieved
   document being relevant does not mean a sentence citing it is accurate.
4. **A valid source identifier alone does not prove a sentence is true.**
   Verification checks that the ID exists in the evidence packet, not that
   every natural-language claim in the sentence is semantically correct.
5. **AI or retrieval failure must never be hidden behind fabricated content.**
   If the AI fails, show the deterministic fallback; label it clearly.
6. **No live status is shown for a historical replay.** Ever.
7. **User-selected preferences (language, lens) are allowed.** Hidden emotional
   profiling or manipulative notifications are not.
8. **No betting, wagering, or pressure-based mechanics.**

---

## Scenario A — The Interrupted Viewer

### Context

**Fan:** [HYPOTHESIS] Arjun, 28, software engineer. Watching an ODI on a
streaming app during lunch. His meeting ran long. He returns to the broadcast
40 minutes later and sees "India 147/3 (22.4 overs)" on the screen. He was
watching at the end of over 14.

**What the fan knows:** India were 89/2 at the end of over 14.

**What is missing:** 8+ overs of events — runs scored, wickets, which batters
are now out, who is batting.

**Question:** "What happened in overs 15 through 22?"

---

### Initial Conditions

- A supported historical ODI match is in the dataset with documented provenance.
- At least 22 completed overs in the innings.
- The match has been ingested and its deliveries are available.
- The fan has opened FanCue (no account required in V1).

---

### Fan Actions

1. Fan opens FanCue.
2. Fan selects the match (search or list).
3. Fan selects innings: 1st innings.
4. Fan sets start boundary: end of over 14 (internal: `after_over: 13`).
5. Fan sets end boundary: end of over 22 (internal: `after_over: 21`).
6. Fan submits the interval request.
7. Fan reads the explanation.

---

### Expected System Behaviour

**Step 1 — Validation:**
- API validates the interval: same innings, start < end, within innings length.
- Proceeds without error.

**Step 2 — Engine:**
- Computes start state at end of over 14:
  `{runs, wickets, overs_completed: 14, batters_at_crease, ...}`
- Computes end state at end of over 22.
- Computes state difference:
  `{runs_in_interval, wickets_in_interval: X, overs_in_interval: 8}`
- Selects consequential events: all wicket deliveries, boundaries >= 6 runs
  in a delivery, notable extras (if any).

**Step 3 — Retrieval:**
- Retrieval query built from event types (e.g., wicket type, batter dismissed).
- If retrieval is enabled, Qdrant may return relevant contextual knowledge (sport=cricket, language=English); otherwise this step is skipped.
- All retrieved items carry mandatory provenance.

**Step 4 — Explanation:**
- Evidence packet assembled.
- LLM generates structured explanation bounded by evidence.
- Verification checks score claims and evidence IDs.
- Explanation returned (or deterministic fallback if LLM unavailable).

---

### Expected Output Properties

The response MUST contain:

| Property | Requirement |
|---|---|
| Start state | Runs and wickets at end of over 14 |
| End state | Runs and wickets at end of over 22 |
| State difference | Runs scored in interval, wickets in interval |
| Key events | At least: each wicket with over number, dismissal type, batter name |
| Evidence sources | At least one contextual item with `doc_id` and `source_name` |
| Historical indicator | "Historical match — [date]" visible |
| Fallback label | Shown only if AI explanation is unavailable |

The response MUST NOT contain:

| Property | Why |
|---|---|
| Invented statistics | No hallucinated run rates, partnership records, etc. |
| Live status indicator | This is a historical replay |
| Delivery-level detail by default | V1 shows over-level granularity only |
| Cross-innings data | Interval is within one innings |

---

### Failure Cases

| Failure | Expected system behaviour |
|---|---|
| Over 22 not completed in dataset | Return `END_BEYOND_DATA` with explanation |
| LLM unavailable | Return deterministic fallback, clearly labelled |
| Qdrant unavailable | Return engine-only deterministic fallback; note missing context |
| Fan enters reversed interval (22 to 14) | Return `INTERVAL_REVERSED` before engine call |
| Match not in dataset | Return `MATCH_NOT_FOUND` before engine call |

---

### Pass/Fail Criteria

| Test | Pass condition |
|---|---|
| Score values correct | Computed runs/wickets match Cricsheet delivery records |
| Events complete | All wicket events in overs 15–22 appear in event list |
| Source IDs present | Every event has a `source_event_id` |
| No fabricated data | Manual review finds 0 invented statistics |
| Historical indicator visible | Present on response page |
| Fallback activates | When LLM disabled, structured summary with label appears |

---

### Integration Test Implications

- `test_scenario_a_valid_interval`: submit valid interval, assert response schema.
- `test_scenario_a_state_diff_accuracy`: compare computed delta with manual scorecard.
- `test_scenario_a_events_complete`: assert all wickets in interval appear in events.
- `test_scenario_a_fallback_active`: run with `SKIP_LLM_IN_TESTS=true`, assert fallback label.
- `test_scenario_a_interval_reversed`: submit reversed interval, assert `INTERVAL_REVERSED`.

---

## Scenario B — The Team-Focused Fan

### Context

**Fan:** [HYPOTHESIS] Priya, 34, marketing professional. She watches India
matches but is specifically interested in how India's top-order batters
performed. She missed overs 5 through 15 of India's innings.

**Lens selected:** "India batting."

**Question:** "What happened with India's batters while I was away?"

---

### Initial Conditions

- Same match and innings as Scenario A (or another supported match).
- At least 15 completed overs.
- India are batting in the selected innings.
- The fan selects the "team batting lens" from the UI options.

---

### Fan Actions

1. Fan selects the match and innings.
2. Fan sets interval: overs 5 through 15.
3. Fan selects lens: "India batting."
4. Fan submits.

---

### Expected System Behaviour

**Engine (unchanged):** Computes the same authoritative state difference as
the neutral perspective. Score values, wickets, and event chronology are
identical.

**Relevance adjustment:** The event selection and explanation emphasis changes:
- Batting partnerships are foregrounded.
- Bowling analysis is de-emphasized.
- Player names and batting contributions are highlighted.
- The framing references India's batting performance.

**Verification (unchanged):** The same verification rules apply. Authoritative
facts cannot differ from the neutral perspective.

---

### Expected Output Properties

| Property | Requirement |
|---|---|
| Score values | Identical to neutral-perspective response for same interval |
| Wickets | Identical count and identity |
| Event chronology | Identical order |
| Emphasis | Batting partnerships and individual scores foregrounded |
| No suppressed events | All wickets still present; framing may differ |

---

### Invariant: Perspective Cannot Alter Facts

The authoritative state (runs, wickets, overs, event chronology) must be
identical between any perspective variant and the neutral variant for the
same interval.

This is testable: automated comparison of the `state_diff` and `canonical_events`
fields across response variants must show zero numerical divergence.

---

### Failure Cases

| Failure | Expected behaviour |
|---|---|
| Engine computes different scores for lens-filtered request | This is a bug — perspective must not touch engine computation |
| A wicket is omitted from the lens-filtered event list | Bug — all events must be present; only emphasis changes |
| The explanation claims an invented partnership record | Verification failure → fallback |

---

### Integration Test Implications

- `test_scenario_b_facts_invariant`: compare `state_diff` between neutral and
  team-lens requests for the same interval. Assert identical values.
- `test_scenario_b_events_present`: assert all interval events appear in lens
  response, including events unfavorable to the selected team.

---

## Scenario C — The Fan Seeking a "Why" Explanation

### Context

**Fan:** [HYPOTHESIS] Vikram, 42, occasional cricket viewer. He returned to
find that a key batter had been dismissed. He understands the fact but not why
it matters given the match situation.

**Question:** "Why was Rohit's wicket so important at that moment?"

**Note:** FanCue does not support free-form natural language questions in V1.
This scenario maps to: "Show me what happened in the over containing Rohit's
dismissal and why the match state changed."

The fan selects the over range containing the dismissal via the interval
selector. The "why" is answered by combining the engine's state-difference
output with Qdrant's contextual knowledge.

---

### Initial Conditions

- A supported match with a notable wicket event in the dataset.
- The interval containing that wicket is within the innings bounds.
- Relevant contextual knowledge has been ingested into Qdrant
  (e.g., match context, batting position significance, run-rate pressure).

---

### Fan Actions

1. Fan selects the match.
2. Fan identifies the over range containing the dismissal (from visible match
   timeline or manual knowledge).
3. Fan sets interval: e.g., overs 10 through 14 (containing the wicket at over 12).
4. Fan submits.
5. Fan reads the explanation.

---

### Expected System Behaviour

**Engine:** Computes state difference including the wicket event.

**Retrieval:** The context planner builds a retrieval query from:
- The dismissed batter's role (opening batter, run rate at dismissal).
- The match state at dismissal (partnership broken, required run rate).
- The wicket type (caught, LBW, bowled, etc.).

When configured, Qdrant can return relevant contextual knowledge — for example, cricket rules context for
an opening partnership being broken at this stage, or pressure on the
team at that run rate.

**Explanation:** LLM generates a factually bounded explanation that answers
the "why" by combining engine state-difference facts with retrieved context.

**Verification:** Score claims checked. Evidence IDs checked. Fallback if
verification fails.

---

### Expected Output Properties

| Property | Requirement |
|---|---|
| Wicket event | Present with: over number, batter name, dismissal type, `source_event_id` |
| Match state at dismissal | Runs, wickets, overs at that point in the interval |
| Contextual explanation | At least one retrieved item explains the significance |
| Evidence source | Retrieved item carries `doc_id`, `source_name`, `source_url` |
| No fabricated context | The explanation cites only what the engine computed and what Qdrant returned |
| Fallback | If Qdrant unavailable: engine-only summary; label notes missing context |

---

### The "Why" Boundary

FanCue can explain why a fact matters by combining deterministic engine output
with retrieved contextual knowledge.

FanCue cannot prove that the natural-language explanation is completely
semantically accurate — only that it cites valid evidence IDs and does not
contradict authoritative facts.

This distinction must be stated in the UI when relevant.

---

### Failure Cases

| Failure | Expected behaviour |
|---|---|
| No contextual knowledge ingested yet | Engine fallback only; label notes that context retrieval is not yet available |
| LLM explains a fact not in the evidence packet | Verification fails → fallback |
| Fan selects interval with no wicket | Explanation addresses only run scoring; no wicket explanation fabricated |

---

### Integration Test Implications

- `test_scenario_c_wicket_context_present`: assert retrieved items relevant to
  wicket type appear in evidence packet.
- `test_scenario_c_explanation_bounded`: assert explanation cites only doc_ids
  present in the evidence packet.
- `test_scenario_c_no_qdrant_fallback`: run with Qdrant unavailable; assert
  engine-only fallback with correct label.

---

## Scenario D — The Fan Who Returns to a Completed Match

### Context

**Fan:** Sanjay could not watch the full match. He opens FanCue the next day
to understand an innings he missed entirely: "I want to understand the second
innings."

**Interval:** Innings-start (`after_over: -1`) to end of the last completed
over of the second innings.

---

### Fan Actions

1. Fan selects a completed historical match.
2. Fan selects second innings.
3. Fan sets start: "beginning of innings" (internal: `after_over: -1`).
4. Fan sets end: last over of the innings.
5. Fan submits.

---

### Expected Output Properties

- Start state: 0 runs, 0 wickets, all-out or target context if second innings.
- End state: full innings total.
- State difference: complete innings summary.
- Required runs context present for second innings (`required_runs`, `required_overs`).

---

### Integration Test Implications

- `test_scenario_d_full_innings`: interval from `after_over: -1` to last over;
  assert start state is zero-state; assert end state matches innings total.

---

## Summary of Scenarios and Test Coverage

| Scenario | Key product feature tested | Integration test prefix |
|---|---|---|
| A — Interrupted viewer | Core interval workflow, fallback | `test_scenario_a_` |
| B — Team-focused fan | Perspective does not alter facts | `test_scenario_b_` |
| C — Why explanation | Context retrieval + verification | `test_scenario_c_` |
| D — Completed match | Innings-start boundary, second innings | `test_scenario_d_` |

---

## What These Scenarios Do Not Prove

- That these are the right scenarios (fan interviews required — see `fan-validation-plan.md`).
- That the product will be useful without validation with real fans.
- That the interval model is complete (open questions remain — see `interval-model.md`).
- That implementation of these scenarios is complete (it is not).
