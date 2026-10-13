# FanCue — Product Acceptance Criteria (V1)

**Version:** 1.0
**Phase:** 01 — Product Specification
**Last updated:** 2026-10-11

> These criteria define measurable, observable conditions for the first complete
> FanCue release. Each criterion has a stable identifier, preconditions, an
> action, expected result, and a pass/fail rule. They are not implementation
> instructions — they are the external specification that implementation must satisfy.

---

## Criterion Categories

| Category | Prefix | Description |
|---|---|---|
| Product / user journey | AC | Fan-facing acceptance criteria |
| Deterministic engine | ENG | Cricket engine correctness criteria |
| Retrieval | RET | Qdrant knowledge retrieval criteria |
| AI output quality | AI | LLM explanation quality criteria |
| Operational | OPS | Latency, fallback, disclosure criteria |
| Future scale | SCALE | Objectives deferred beyond first release |

---

## AC — Product Acceptance Criteria

---

### AC-01 — Supported match selection

**Requirement:** The fan can choose a supported historical cricket fixture from
a presented list. Requesting an unsupported match returns an explicit,
informative result — not a fabricated scorecard.

**Preconditions:**
- At least one cricket match dataset has been ingested with documented provenance.
- The match index is populated with at least the matches from that dataset.

**Action:** Fan opens FanCue and views available matches, or searches by match
identifier.

**Expected result:**
- Supported matches appear in the list with accurate identifiers.
- If the fan enters an unsupported match ID, the system returns a structured
  `MATCH_NOT_FOUND` response with an explanation.
- No match data is invented or approximated.

**Pass rule:** The displayed match list matches the ingested dataset inventory.
An unsupported match request returns `MATCH_NOT_FOUND`, not a partial result.

**Fail rule:** Any fabricated match data appears in the UI, or an unsupported
match silently returns partial scorecard data.

**Verification method:** Manual inspection of UI against ingested match index.
Integration test: request a known-invalid match ID; assert `MATCH_NOT_FOUND`.

**Phase dependency:** Phase 03 (dataset ingestion), Phase 06 (UI).

**Open assumptions:** Match index format and search UX not yet designed.

---

### AC-02 — Valid interval selection and rejection

**Requirement:** A valid same-innings interval (per the interval model) is
accepted. An invalid or reversed interval is rejected with an error code
before any engine calculation or AI call is made.

**Preconditions:**
- A supported match is selected.
- At least one innings with at least 2 completed overs exists.

**Action:**
- (Pass path) Fan selects a valid interval: `start.after_over < end.after_over`,
  same innings, within the innings length.
- (Fail path) Fan submits a reversed interval (`start.after_over > end.after_over`),
  a cross-innings interval, or an out-of-range end boundary.

**Expected result:**
- Valid interval: proceeds to engine processing.
- Invalid interval: returns structured error with error code and human-readable
  explanation, before any engine or AI processing begins.

**Pass rule:** All 7 rejection conditions in the interval model validation table
are enforced. Invalid requests never reach the engine.

**Fail rule:** An invalid interval reaches the engine, or returns a result
as if valid.

**Verification method:** Contract test for each rejection condition.
Integration test: submit each invalid interval type; assert correct error code.

**Phase dependency:** Phase 02 (contracts), Phase 03 (engine validation).

---

### AC-03 — Deterministic state reconstruction and scorecard reconciliation

**Requirement:** For any valid interval on a supported match, the engine
produces a start state, end state, and state difference that reconcile against
the Cricsheet scorecard for that match, or reports a `RECONCILIATION_MISMATCH`
if a discrepancy exists.

**Preconditions:**
- A match with a known scorecard is in the dataset.
- A valid interval is specified.

**Action:** The engine reconstructs match state for the interval.

**Expected result:**
- `state_diff.runs_in_interval` equals the run total difference between the
  two over boundaries as computed from delivery records.
- `state_diff.wickets_in_interval` equals the wicket count difference.
- Computed values match the Cricsheet scorecard, or a `RECONCILIATION_MISMATCH`
  flag is returned with both values shown.
- The same input always produces the same output on every call (determinism).

**Pass rule:**
- All INV-01 through INV-11 invariants hold (see interval model).
- Reconciliation mismatch is reported, not silently suppressed.

**Fail rule:**
- Engine produces different results for identical inputs.
- Engine silently uses the scorecard value instead of its own computation.
- A reconciliation discrepancy is hidden.

**Verification method:** Engine unit tests for each invariant. Reconciliation
test against at least 2 known matches with published scorecards.

**Phase dependency:** Phase 03.

**Coverage gate:** >= 90% for engine modules (set in Phase 03).

---

### AC-04 — Evidence traceability

**Requirement:** Every key event displayed to the fan can be traced to a
stable `source_event_id` and a recorded dataset `revision_id`.

**Preconditions:** Engine has processed a valid interval.

**Action:** Fan views the key events list in the explanation.

**Expected result:**
- Every displayed event has a `source_event_id` of the form
  `{match_id}:{innings_index}:{over_index}:{delivery_index}`.
- Every event has an associated `revision_id` (Cricsheet file hash or version).
- These identifiers are available in the API response even if not shown
  in the default UI view.

**Pass rule:** No event in the response lacks a `source_event_id` and
`revision_id`. Spot-check: manually trace 3 events from the API response
back to the Cricsheet source file.

**Fail rule:** Any event appears without a traceable identifier.

**Verification method:** API response schema validation. Manual trace spot-check.

**Phase dependency:** Phase 02 (event schema), Phase 03 (engine).

---

### AC-05 — Perspective personalization does not alter authoritative facts

**Requirement:** Selecting a team or player lens changes which events are
emphasized and how the explanation is framed, but does not alter authoritative
match facts (scores, wickets, chronology).

**Preconditions:** A valid interval with at least one wicket and one boundary.

**Action:** Fan selects "show from [Team A]'s perspective." The same interval
is displayed with altered emphasis.

**Expected result:**
- All score values and wicket counts in the response are identical to the
  neutral-perspective response.
- Event order (chronology) is unchanged.
- Contextual framing and emphasis may differ (this is intended).
- No event that occurred is omitted from the evidence; only emphasis changes.

**Pass rule:** Automated comparison of score and wicket values between neutral
and team-perspective responses for the same interval shows zero divergence.

**Fail rule:** A score or wicket value differs between perspectives for the
same interval.

**Verification method:** Integration test comparing canonical facts across
perspective variants.

**Phase dependency:** Phase 05 (orchestration), Phase 06 (UI).

---

### AC-06 — Context retrieval carries provenance and satisfies sport/language filters

**Requirement:** Every contextual knowledge item returned by Qdrant carries
mandatory provenance metadata (`doc_id`, `source_name`, `source_url`,
`license`), and retrieval queries correctly apply sport and language filters.

**Preconditions:** A cricket knowledge corpus is ingested with mandatory
metadata fields. A valid interval has been processed.

**Action:** The retrieval layer queries Qdrant with sport=cricket and a language
filter. A football query is also submitted to verify filter isolation.

**Expected result:**
- All returned items carry `doc_id`, `source_name`, `source_url`, `license`.
- Cricket query returns only cricket-tagged documents.
- Football query returns no cricket-tagged documents (and vice versa).
- Recall@10 >= 80% on the known-relevant question set (Phase 04 gate).

**Pass rule:** Zero cross-sport contamination in query results. All mandatory
metadata fields present on every returned item.

**Fail rule:** A football document appears in a cricket query result. Any
returned item lacks a mandatory metadata field.

**Verification method:** Retrieval evaluation set (Phase 04). Integration test
for cross-sport filter isolation.

**Phase dependency:** Phase 04.

---

### AC-07 — AI explanation verification

**Requirement:** The AI explanation step uses structured output and is rejected
(triggering deterministic fallback) when it contains score claims that
contradict the authoritative engine output, evidence IDs that do not exist
in the evidence packet, or other checkable factual conflicts.

**Preconditions:** Engine output and evidence packet are available. LLM is
configured.

**Action:** The explanation module calls the LLM. The verification step checks
the result.

**Expected result:**
- A correct explanation: passes verification and is returned to the fan.
- An explanation with a fabricated score (test case: injected): fails
  verification and triggers deterministic fallback.
- An explanation citing a nonexistent doc_id: fails verification.

**Pass rule:**
- At least one injected-error test case fails verification and activates fallback.
- Verification does not incorrectly reject correct explanations in normal operation.

**Limitation:** Verification confirms that referenced evidence IDs exist in
the packet and that cited score values match the engine output. It does not
prove that every natural-language sentence is semantically accurate. That
distinction must be stated explicitly in the product specification.

**Fail rule:** A fabricated score claim passes verification and reaches the fan.
An explanation with a nonexistent evidence ID reaches the fan.

**Verification method:** Integration test with injected LLM output containing
known errors. Verification module unit tests.

**Phase dependency:** Phase 05.

---

### AC-08 — Deterministic fallback

**Requirement:** The main catch-up workflow returns a useful, clearly labelled
deterministic summary when the LLM is disabled, times out, or the verification
step fails.

**Preconditions:** Engine output and evidence packet are available. LLM is
either disabled (`SKIP_LLM_IN_TESTS=true`) or returns invalid output.

**Action:** Fan requests an interval catch-up. LLM is unavailable.

**Expected result:**
- The fan receives a structured summary containing:
  - start state, end state, state difference;
  - list of key events with source IDs;
  - a label: "AI explanation unavailable — deterministic summary."
- The summary is returned within the configured `REQUEST_TIMEOUT_SECONDS`.
- No error page or blank response is shown.

**Pass rule:** Fallback response produced and correctly labelled. Score and
wicket values match engine output.

**Fail rule:** Fan sees an error page, a blank response, or an unlabelled
AI output when the LLM is unavailable.

**Verification method:** Integration test with `SKIP_LLM_IN_TESTS=true`.

**Phase dependency:** Phase 05.

---

### AC-09 — Historical replay disclosure

**Requirement:** The UI explicitly identifies that the data is a historical
replay. No live-feed status is implied.

**Preconditions:** A historical match is displayed.

**Action:** Fan views the match context or explanation page.

**Expected result:**
- The UI shows a visible replay/historical indicator (e.g., "Historical match —
  [date]").
- No "LIVE" badge, real-time ticker, or language implying current play.

**Pass rule:** Historical indicator is visible on every page where match data
is displayed. Manual review by a second person confirms no live-data language.

**Fail rule:** Any live-data language or badge appears for a historical match.

**Verification method:** Manual UI review. Can be extended to an automated
accessibility/content check in Phase 06.

**Phase dependency:** Phase 06.

---

### AC-10 — Language quality gate

**Requirement:** A language option is displayed to users only after its
output has passed a defined manual quality review for cricket terminology,
player names, numerical values, and meaning preservation.

**Decision:** English is the baseline. Tamil is the first additional candidate
[see ADR-008]. Tamil is NOT displayed as a supported language until the
review passes.

**Preconditions:** Tamil output has been generated for at least 10 test
intervals by the LLM.

**Action:** A reviewer with cricket Tamil knowledge reviews the output.

**Quality review checklist:**
- Cricket-specific terms are translated consistently and correctly.
- Player names and team names are transliterated appropriately (not translated).
- Numerical values (runs, wickets, overs) are correct.
- The meaning of the English original is preserved, not paraphrased into
  something different.
- No English cricket terms appear untranslated where a Tamil equivalent exists.

**Pass rule:** The reviewer approves >= 8 of 10 test interval outputs with
no critical factual errors.

**Fail rule:** < 8 pass, or any output contains a factual error in numerical
values. Tamil is withheld from production until the gate passes.

**Verification method:** Manual review session. Results recorded in
`docs/evaluation/language-review-tamil.md` (created when review occurs).

**Phase dependency:** Phase 05 (LLM), Phase 09 (language evaluation).

---

### AC-11 — Response latency

**Requirement:** End-to-end response time is measured and reported honestly.
The 30-second fan outcome is a target, not a current measured result.

**Measurement definition:**
- **Start:** Fan submits the interval request (browser or API call timestamp).
- **End:** Fan's browser renders the complete explanation or fallback (or the
  API response is received in a test context).
- **Measured components (separate):** engine processing, Qdrant retrieval,
  LLM call (when available), verification, network round-trip.

**Target:** Complete response (AI or fallback) within 30 seconds for a
T20-length interval on reference hardware. This target requires validation —
it is not claimed as met.

**Pass rule:** Measured median latency <= 30 seconds across 10 test requests
on a local development machine. Each component latency is reported separately.

**Fail rule:** Median > 30 seconds, or no measurement is taken (the target
cannot be claimed without a test).

**Verification method:** Timed integration test (Phase 05/06). Latency
instrumentation in the backend.

**Phase dependency:** Phase 06 (end-to-end), Phase 07 (optimization if needed).

---

### AC-12 — Usability (formative test)

**Requirement:** At least 3 real cricket fans attempt the complete journey
(match selection → interval specification → receive explanation) without
assistance from the product team. Observations are reported honestly.

**Preconditions:** A working end-to-end system (Phase 06 complete).
Fan participants have consented.

**Action:** Unassisted fan task sessions.

**Expected result:**
- Each participant completes the journey or the point of failure is identified.
- Task completion rate and observed difficulties are recorded.
- No participant needed to be told what to do next (unassisted test).

**Pass rule:** At least 3 sessions completed. Observations are documented.
This is a formative (learning) test — there is no minimum completion rate
required for the first session. Results inform Phase 09 refinements.

**Fail rule:** Zero sessions completed, or observations are not honestly recorded.

**Verification method:** Usability session record in `docs/evaluation/usability-sessions.md`
(created in Phase 09).

**Phase dependency:** Phase 09.

**Note:** A 3-person sample is not statistically representative. It is a
minimum viable formative signal. Do not generalize findings beyond what the
data supports.

---

## ENG — Deterministic Engine Correctness Criteria

| ID | Criterion | Phase | Test location |
|---|---|---|---|
| ENG-01 | All INV-01 through INV-11 invariants hold for every test fixture | Phase 03 | `backend/tests/match_engine/` |
| ENG-02 | Engine is deterministic: identical input always produces identical output | Phase 03 | `backend/tests/match_engine/test_determinism.py` |
| ENG-03 | Edge cases EC-01 through EC-10 produce specified behaviour | Phase 03 | `backend/tests/match_engine/test_edge_cases.py` |
| ENG-04 | Reconciliation mismatch is detected and reported for at least one test fixture with a known discrepancy | Phase 03 | `backend/tests/match_engine/test_reconciliation.py` |
| ENG-05 | Engine functions without network access | Phase 03 | CI: network-disabled test run |

---

## RET — Retrieval Criteria

| ID | Criterion | Phase | Test location |
|---|---|---|---|
| RET-01 | Recall@10 >= 80% on known-relevant question set | Phase 04 | `tests/evaluation/` |
| RET-02 | Cross-sport filter isolation: cricket query returns 0 football documents | Phase 04 | `tests/evaluation/test_filter_isolation.py` |
| RET-03 | All retrieved items carry mandatory metadata fields | Phase 04 | `tests/evaluation/test_metadata_completeness.py` |
| RET-04 | doc_id is deterministic: same content always produces same ID | Phase 04 | `tests/evaluation/test_doc_id_stability.py` |

---

## AI — AI Output Quality Criteria

| ID | Criterion | Phase | Verification |
|---|---|---|---|
| AI-01 | Fabricated score claim fails verification | Phase 05 | Integration test with injected error |
| AI-02 | Nonexistent doc_id citation fails verification | Phase 05 | Integration test with injected error |
| AI-03 | AI output never mutates authoritative engine output | Phase 05 | Integration test: compare engine state pre/post LLM |
| AI-04 | Correct explanations pass verification in normal operation | Phase 05 | Integration test: 10 known-good intervals |

---

## OPS — Operational Criteria

| ID | Criterion | Phase | Verification |
|---|---|---|---|
| OPS-01 | Fallback activates correctly when LLM is disabled | Phase 05 | `SKIP_LLM_IN_TESTS=true` integration test |
| OPS-02 | Fallback is clearly labelled as non-AI-generated | Phase 05 | Manual UI review + content check |
| OPS-03 | Historical replay indicator is visible on all match pages | Phase 06 | Manual UI review |
| OPS-04 | Median end-to-end latency measured and documented | Phase 06 | Timed integration test |
| OPS-05 | System usable without an LLM API key | Phase 05 | Integration test with no API key configured |

---

## SCALE — Future Scale Objectives (deferred)

These are NOT first-release criteria. They are future targets with no current
validation method.

| ID | Objective | Why deferred |
|---|---|---|
| SCL-01 | Support 50,000 concurrent users | No load test method or infrastructure defined |
| SCL-02 | Sub-5-second response on production CDN | Production infrastructure not yet designed |
| SCL-03 | Real-time live match data | Requires licensed feed not in scope |

Do not reference SCALE criteria in first-release claims.

---

## Traceability Table

| Criterion | Phase produced | Test location | ADR reference |
|---|---|---|---|
| AC-01 | Phase 06 | `tests/integration/test_match_selection.py` | ADR-006 |
| AC-02 | Phase 02/03 | `tests/contracts/`, `backend/tests/` | ADR-003 |
| AC-03 | Phase 03 | `backend/tests/match_engine/` | ADR-003 |
| AC-04 | Phase 02/03 | `backend/tests/`, `tests/contracts/` | ADR-003, ADR-004 |
| AC-05 | Phase 05/06 | `tests/integration/test_perspective.py` | ADR-005 |
| AC-06 | Phase 04 | `tests/evaluation/` | ADR-004 |
| AC-07 | Phase 05 | `tests/integration/test_verification.py` | ADR-005 |
| AC-08 | Phase 05 | `tests/integration/test_fallback.py` | ADR-005 |
| AC-09 | Phase 06 | Manual UI review | ADR-006 |
| AC-10 | Phase 09 | `docs/evaluation/language-review-tamil.md` | ADR-008 |
| AC-11 | Phase 06/07 | Timed integration test | ADR-002 |
| AC-12 | Phase 09 | `docs/evaluation/usability-sessions.md` | — |
| ENG-01 through ENG-05 | Phase 03 | `backend/tests/match_engine/` | ADR-003 |
| RET-01 through RET-04 | Phase 04 | `tests/evaluation/` | ADR-004 |
| AI-01 through AI-04 | Phase 05 | `tests/integration/test_verification.py` | ADR-005 |
| OPS-01 through OPS-05 | Phase 05/06 | Mixed | ADR-005 |
