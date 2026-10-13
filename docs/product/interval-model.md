# FanCue — Cricket Interval Model (V1)

**Version:** 1.0
**Phase:** 01 — Product Specification
**Status:** Normative for Phase 02 contracts and Phase 03 engine development
**Last updated:** 2026-10-11

> This document defines exactly what a "missed interval" means in FanCue's
> cricket context, how boundaries are represented internally, and what
> behaviours the deterministic engine must produce at every edge case.
> It is a contract input, not an implementation.

---

## 1. Human-Readable Definition

An **interval** is a contiguous sequence of deliveries within a single innings
of a cricket match, bounded by two whole-over positions, where the fan was
absent and wishes to understand what they missed.

**Example (human):** "I missed overs 13 through 18 of the first innings."

This means: the fan was present at the end of over 12, left, and returned
after over 18 had completed. FanCue must explain everything that happened
across those six overs.

**What FanCue delivers:**
- The match state at the start boundary (end of over 12)
- The match state at the end boundary (end of over 18)
- The state difference: runs scored, wickets lost, notable events
- All deliveries in overs 13–18 available for evidence selection

---

## 2. V1 Boundary Convention

### 2.1 Whole-over boundaries only (V1)

V1 uses **whole-over boundaries exclusively**. A boundary is defined as
the state that exists immediately after all legal and illegal deliveries
in a given over have been bowled and recorded.

Delivery-level boundary selection is **deferred** until the Cricsheet delivery
schema and extras semantics are fully understood and tested (Phase 03).

### 2.2 Formal boundary definition

A boundary position is identified by a triple:

```
BoundaryPosition = {
    match_id:    string   # Stable Cricsheet match identifier
    innings_index: int    # 0-based (0 = first innings, 1 = second innings, etc.)
    after_over:  int      # 0-based over index. After over N means after all
                          # deliveries in the Nth over have completed.
                          # after_over = -1 represents the innings start
                          # (before any delivery has been bowled).
}
```

### 2.3 Innings-start sentinel

The position **before any delivery** in an innings is represented as:

```
after_over = -1
```

This explicitly avoids confusing "start of innings" with "end of over 0"
(which would mean after the first over has been bowled).

### 2.4 Inclusive/exclusive semantics

| Boundary | Semantics |
|---|---|
| `start_boundary` | **Exclusive** — the delivery immediately after this position is the first delivery in the interval |
| `end_boundary` | **Inclusive** — all deliveries up to and including the final delivery of this over are in the interval |

**In plain English:** An interval `[start=after_over:12, end=after_over:18]`
contains all deliveries belonging to overs at 0-based index 13, 14, 15, 16,
17, and 18 (human: overs 14 through 19 in 1-based notation, or "overs 13–18"
in the common shorthand where over numbering starts at 1 for the first over
of an innings and over 12 means the 12th over has been bowled).

> **Notation decision:** This document uses **0-based over index** internally.
> The UI presents human-friendly 1-based over labels. The conversion is:
> `human_label = after_over + 1`. The boundary `after_over: 0` means
> "after the first over" = human label "end of over 1".

### 2.5 Human-to-internal label mapping

| Human input | Internal representation |
|---|---|
| "Start of innings" | `after_over: -1` |
| "End of over 1" (1 over bowled) | `after_over: 0` |
| "End of over 12" | `after_over: 11` |
| "End of over 18" | `after_over: 17` |
| "End of over 20" (T20 full innings) | `after_over: 19` |
| "End of over 50" (ODI full innings) | `after_over: 49` |

The engine always works with 0-based internal indices. The API contract
accepts both human labels and internal indices; conversion happens at the
API boundary, not inside the engine.

---

## 3. Valid Interval Constraints

An interval is **valid** if and only if ALL of the following conditions hold:

| Constraint | Rule |
|---|---|
| Same match | `start.match_id == end.match_id` |
| Same innings | `start.innings_index == end.innings_index` |
| Start before end | `start.after_over < end.after_over` |
| Non-degenerate | `end.after_over - start.after_over >= 1` (at least one over in interval) |
| Start in range | `start.after_over >= -1` |
| End in range | `end.after_over <= innings_last_completed_over` |
| Innings exists | `innings_index` exists in the match data |

---

## 4. Boundary Validation Decision Table

| Condition | Result | Error code |
|---|---|---|
| `start.after_over == end.after_over` | Reject | `INTERVAL_EMPTY` |
| `start.after_over > end.after_over` | Reject | `INTERVAL_REVERSED` |
| `start.after_over < -1` | Reject | `START_OUT_OF_RANGE` |
| `end.after_over > innings_last_completed_over` | Reject | `END_BEYOND_DATA` |
| `start.innings_index != end.innings_index` | Reject | `CROSS_INNINGS` |
| `innings_index` not present in match | Reject | `INNINGS_NOT_FOUND` |
| `match_id` not in supported dataset | Reject | `MATCH_NOT_FOUND` |
| `end.after_over - start.after_over > MAX_INTERVAL_OVERS` (config) | Reject | `INTERVAL_TOO_LARGE` |
| All constraints pass | Accept | — |

All rejections must occur **before** any engine calculation or AI call.
The API must return a structured error with the error code and a
human-readable explanation.

---

## 5. Canonical Event Sequence

The canonical event sequence for an interval is derived as follows:

1. Load the Cricsheet JSON match file identified by `match_id`.
2. Select the innings at `innings_index`.
3. Filter deliveries where the over index (0-based) satisfies:
   `start.after_over < over_index <= end.after_over`
4. Within each over, preserve the delivery order as recorded in the source file.
5. Assign each delivery a stable **source event ID**:
   ```
   source_event_id = f"{match_id}:{innings_index}:{over_index}:{delivery_index}"
   ```
   where `delivery_index` is the 0-based position of the delivery within its
   over as recorded in the source file (including wides and no-balls).
6. Record the dataset revision used (Cricsheet file hash or version tag).

The engine must not reorder deliveries, deduplicate events, or modify
source delivery records.

---

## 6. State Calculation

### 6.1 State snapshot keys

For V1 cricket, the authoritative state at any boundary position includes:

| Key | Type | Notes |
|---|---|---|
| `runs_scored` | int | Total runs at this position (batting team) |
| `wickets_fallen` | int | Total wickets at this position |
| `overs_completed` | int | Equal to `after_over + 1` (0 if `after_over == -1`) |
| `legal_balls_bowled` | int | Excludes wides and no-balls |
| `current_partnership_runs` | int | Runs in the current (unbroken) partnership |
| `current_partnership_balls` | int | Legal balls in the current partnership |
| `batting_team` | string | Team name as in source data |
| `bowling_team` | string | Team name as in source data |
| `batters_at_crease` | list[string] | At most 2 player names |
| `required_runs` | int or null | For second innings only; null if first innings |
| `required_overs` | int or null | For second innings only; null if first innings |

### 6.2 State difference

The state difference (delta) between `start_state` and `end_state` is:

| Key | Calculation |
|---|---|
| `runs_in_interval` | `end.runs_scored - start.runs_scored` |
| `wickets_in_interval` | `end.wickets_fallen - start.wickets_fallen` |
| `overs_in_interval` | `end.overs_completed - start.overs_completed` |
| `legal_balls_in_interval` | `end.legal_balls_bowled - start.legal_balls_bowled` |
| `events_in_interval` | Ordered list of consequential events (wickets, boundaries, extras runs) |

### 6.3 Reconciliation requirement

After computing `end_state`, the engine must verify:

- Computed `runs_scored` matches the Cricsheet scorecard field for that innings
  up to that over, if a scorecard is present in the source file.
- Computed `wickets_fallen` matches the scorecard.
- If a mismatch is detected: log the discrepancy, return `RECONCILIATION_MISMATCH`
  as a metadata flag on the response, and do not suppress the mismatch.
- Do not silently correct the computed state to match the scorecard.
  Both values must be surfaced.

---

## 7. Edge Cases — Required Behaviours

The following edge cases must have specified expected behaviour before Phase 03
implementation begins. Cases marked **[OPEN]** cannot be resolved until the
Cricsheet JSON schema has been inspected for the chosen dataset; Phase 02 must
close them.

### EC-01 — Wide delivery

**Situation:** A wide is recorded in the source data within the interval.

**Expected behaviour:**
- Wide contributes to `runs_scored` (1 run + any additional runs).
- Wide does NOT count as a legal ball.
- Wide is included in the canonical event sequence as a delivery record.
- `legal_balls_bowled` is NOT incremented.

**Source dependency:** Cricsheet represents wides with `extras.wides` field.
**Status:** Defined. Confirm against actual schema in Phase 02.

---

### EC-02 — No-ball delivery

**Situation:** A no-ball is recorded within the interval.

**Expected behaviour:**
- No-ball contributes to `runs_scored` (1 run + any scored off the bat or further extras).
- No-ball does NOT count as a legal ball.
- No-ball is included in the canonical event sequence.
- `legal_balls_bowled` is NOT incremented.

**Source dependency:** Cricsheet `extras.noballs` field.
**Status:** Defined. Confirm schema in Phase 02.

---

### EC-03 — Bye and leg-bye

**Situation:** A bye or leg-bye is recorded within the interval.

**Expected behaviour:**
- Byes/leg-byes contribute to `runs_scored` as extras.
- They DO count as legal balls (they are bowled legitimately).
- `legal_balls_bowled` is incremented.

**Source dependency:** Cricsheet `extras.byes` / `extras.legbyes` fields.
**Status:** Defined. Confirm schema in Phase 02.

---

### EC-04 — Wicket on the last delivery of an over

**Situation:** A wicket falls on delivery 6 of an over (the last legal delivery).

**Expected behaviour:**
- The wicket is attributed to this over.
- The state at the end of this over records the wicket.
- The new batter who came in (if any) is NOT counted in `batters_at_crease`
  at the over boundary — they appear in the next over's start state.
- **[OPEN]:** Cricsheet sometimes records the new batter on the same
  delivery record. Behaviour must be confirmed against actual data.

**Status:** Partially defined. **[OPEN item for Phase 02].**

---

### EC-05 — Over with more recorded deliveries than legal-ball count

**Situation:** An over in the source data contains 9 delivery records (e.g.,
due to wides and no-balls extending the over beyond 6 legal deliveries).

**Expected behaviour:**
- The over boundary is defined by its legal-ball completion (6 legal balls),
  not by the total number of delivery records.
- All delivery records in the over are included in the canonical event sequence.
- The `after_over` index advances by 1 when the over is complete, regardless
  of how many total delivery records it contains.

**Source dependency:** Cricsheet over structure groups all deliveries by over.
**Status:** Defined. Confirm over termination condition in Phase 02.

---

### EC-06 — Innings termination boundary

**Situation:** The fan selects `end.after_over` equal to the last completed over
of an innings that ended by all-out or declaration.

**Expected behaviour:**
- End state reflects the final recorded state of the innings.
- If fewer than the maximum number of overs were bowled, the engine uses the
  actual innings length as the upper bound.
- The `end.after_over` value is clamped to `innings_last_completed_over`
  with a `BOUNDARY_CLAMPED` warning on the response; it is not an error.

**Status:** Defined.

---

### EC-07 — Innings-start boundary

**Situation:** Fan selects `start.after_over = -1` (beginning of innings,
before any ball has been bowled).

**Expected behaviour:**
- Start state is the initial innings state: 0 runs, 0 wickets, 0 overs.
- The interval begins with the first delivery of the first over.
- This is a valid boundary and must not be treated as an error.

**Status:** Defined.

---

### EC-08 — Scorecard disagreement (reconciliation mismatch)

**Situation:** The engine computes `runs_scored = 143` but the Cricsheet
scorecard field says `143` for the same position. Wait — mismatch case:
engine computes 141, scorecard says 143.

**Expected behaviour:**
- Engine logs a `RECONCILIATION_MISMATCH` with both values.
- Both computed and scorecard values are returned in the API response metadata.
- The engine's computed value is used as the authoritative fact for
  explanation generation, **not** the scorecard value.
- The discrepancy is flagged to the user or logged as a data quality issue.
- Do not silently choose one value. Surface both.

**Rationale:** If the engine's computation is deterministic and correct,
the mismatch reveals a data quality issue in the source. If the engine has
a bug, the mismatch reveals the bug. Either way, hiding it is worse.

**Status:** Defined.

---

### EC-09 — Unfinished over at interval end

**Situation:** V1 UI exposes only whole-over boundaries. The fan cannot select
a partially completed over as an end boundary.

**Expected behaviour:**
- The UI presents only completed over positions for selection.
- If the current over is in progress (live data — not V1 scope), that over
  is not available as an end boundary.
- For historical data, only overs that have a complete delivery record are
  offered as boundary options.

**Status:** Defined. Delivery-level selection deferred to V2.

---

### EC-10 — Cross-innings interval request

**Situation:** Fan specifies start in innings 1 and end in innings 2.

**Expected behaviour:**
- Rejected with `CROSS_INNINGS` error before any processing.
- Error message explains that V1 intervals must be within a single innings.
- Future versions may support cross-innings intervals with explicit design.

**Status:** Defined. Cross-innings deferred.

---

### EC-11 — Penalty runs

**Situation:** Penalty runs are awarded within the interval.

**Expected behaviour [OPEN]:** Cricsheet penalty run representation must be
inspected. Until the field is confirmed, the engine logs a `PENALTY_RUNS_UNHANDLED`
warning if penalty runs are detected, includes the source delivery in the
event sequence, but does not guarantee accurate state for this delivery.

**Status:** **[OPEN — requires Phase 02 schema inspection].**

---

### EC-12 — Source data missing or corrupt

**Situation:** The Cricsheet file for the requested match is absent, truncated,
or fails JSON schema validation.

**Expected behaviour:**
- Reject with `DATA_UNAVAILABLE` before any engine processing.
- Return a structured error with the reason.
- Do not fabricate match data.
- Do not return a partial result as if complete.

**Status:** Defined.

---

## 8. Invariants for Phase 03 Tests

The Phase 03 test suite MUST enforce all of the following:

| ID | Invariant |
|---|---|
| INV-01 | `end_state.runs_scored >= start_state.runs_scored` (runs never decrease within an innings) |
| INV-02 | `end_state.wickets_fallen >= start_state.wickets_fallen` (wickets never decrease) |
| INV-03 | `end_state.wickets_fallen <= 10` (maximum wickets in an innings) |
| INV-04 | `state_diff.runs_in_interval == end_state.runs_scored - start_state.runs_scored` |
| INV-05 | `state_diff.wickets_in_interval == end_state.wickets_fallen - start_state.wickets_fallen` |
| INV-06 | `state_diff.overs_in_interval == end.after_over - start.after_over` |
| INV-07 | Same input always produces the same output (determinism) |
| INV-08 | All deliveries in the interval have a unique `source_event_id` |
| INV-09 | No delivery outside the interval boundary appears in the event sequence |
| INV-10 | Invalid intervals are rejected before engine execution (not after) |
| INV-11 | The dataset revision identifier is present on every response |

---

## 9. Deferred Items (V2)

| Feature | Reason for deferral |
|---|---|
| Delivery-level boundaries | Extras semantics (wides, no-balls) make mid-over state ambiguous until the full schema is understood |
| Cross-innings intervals | Requires consistent state representation across innings transitions |
| DLS-affected match intervals | Requires DLS method metadata not confirmed in V1 dataset |
| Live / in-progress over boundaries | Not V1 scope (historical data only) |
| Penalty-run state accuracy | Source schema unknown until Phase 02 |
| Powerplay / field restriction annotations | Requires additional source metadata |
| Partnership-level interval boundaries | No fan demand evidence yet |

---

## 10. Open Questions (must be resolved in Phase 02)

| ID | Question | Blocking |
|---|---|---|
| OQ-01 | Does Cricsheet JSON record the new batter on the same delivery as the wicket? | EC-04 |
| OQ-02 | How does Cricsheet represent penalty runs? | EC-11 |
| OQ-03 | Does Cricsheet guarantee delivery order within an over? | INV-08 |
| OQ-04 | What field carries the innings-level scorecard total for reconciliation? | EC-08 |
| OQ-05 | How are Super Overs represented — as a separate innings or a special over? | INV-09 |
