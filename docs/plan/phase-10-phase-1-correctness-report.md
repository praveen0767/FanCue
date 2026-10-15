# Phase 10 / Phase 1 — Cricket Correctness, Evidence Integrity & Deterministic Story Engine

> **Historical correctness report (2026-10-15):** Test counts and Qdrant coverage below belong to this report's specific revision/environment. Current Render configuration selects Groq `openai/gpt-oss-20b` and disables Qdrant retrieval; these historical measurements are not production retrieval metrics.

**Status: COMPLETE — 262 passed, 0 failed**
**Date: 2026-10-13**
**Repository root:** `D:\FanCue`

---

## 1. Baseline (before Phase 1 changes)

```
Command : .venv\Scripts\python.exe -m pytest backend\tests\ -q --tb=short
Result  : 85 passed, 1 warning   Exit code: 0
Coverage: not measured
```

---

## 2. Defect Triage

### Defect 1 — Interval boundary (Probe 1)

**Verdict: NOT a bug — convention mis-reading documented.**

- Cricsheet `over` field is 0-indexed. `after_over=N` means "state after all deliveries of 0-based over N" = N+1 user-facing completed overs.
- `filter_interval_deliveries(deliveries, 24, 25)` returns exactly `{d.over == 25}`. Verified against raw JSON.
- Tests in `TestBoundaryConventionOnRealFixture` pin this convention; drift in either direction fails loudly.
- The previously failing `test_state_at_25_excludes_over_index_26` was using `request(14,25)` (11 overs) instead of `request(24,25)` (1 over). Fixed in test — not in engine.

### Defect 2 — Run-out / retired bowler credit (Probe 2)

**Verdict: CONFIRMED BUG — reproduced and fixed.**

| Dismissal kind            | Pre-fix              | Post-fix           |
|---------------------------|----------------------|--------------------|
| run out                   | "off bowling of X"   | no bowler field    |
| obstructing the field     | "off bowling of X"   | no bowler field    |
| retired out               | "off bowling of X"   | no bowler field    |
| retired hurt              | WICKET fact emitted  | no WICKET fact     |
| caught / bowled / lbw     | correct              | unchanged          |

Fix: `NON_BOWLER_CREDITED_DISMISSALS` frozenset in `intervals.py`; `NON_WICKET_DISMISSALS` in `state.py`.

### Defect 3 — Partial final over (Probe 3)

**Verdict: CONFIRMED ISSUE — new function added.**

- Pre-fix: innings 1 of 1529229 (WI won with 2 balls of over 48 bowled) showed `overs_completed=49`.
- Fix: `calculate_final_innings_snapshot(deliveries)` in `state.py` counts `legal_balls_in_over` in the final over.
- Reconciliation test updated: `expected_overs=48, expected_legal_balls_in_over=2`.
- Displays correctly as `48.2`.

### Defect 4 — Over indexing (Probe 4)

**Verdict: NOT a bug — confirmed correct, pinned by tests.**

---

## 3. Additional Bugs Found and Fixed

### Bug A — `_raw_stats`: wrong Cricsheet structure for wides/noballs

- `d["runs"]["extras"]` is an integer (total extras), not a dict.
- Extras detail (`wides`, `noballs`) lives at top-level `d["extras"]`.
- Fixed in `test_phase1_property_and_fallback.py::_raw_stats`.

### Bug B — Verifier: decimal run-rate false positive

- `"7.00 runs per over"` caused regex `\b(\d+)\s+(runs?)` to match `00` as "0 runs" (false numeric mismatch).
- Fix: negative lookbehind `(?<!\.)` added to `_DIGIT_UNIT_PATTERN`.

### Bug C — Verifier: bare "bet" not caught

- Pattern `\bbett?ing\b` matched "betting" but not "bet on this team".
- Fix: added `\bbet\b` to `PROHIBITED_SPECULATION_PATTERNS`.

### Bug D — Engine audit test: wide delivery arithmetic

- `_d(extras={"wides": 1}, total=1)` with default `batter_runs=1` → 1+1 != 1 → arithmetic error.
- Fix: `_d(batter_runs=0, extras={"wides": 1}, total=1)`.

---

## 4. Rule-Based Engine Audit — All Rules Verified

| Rule                                          | Status |
|-----------------------------------------------|--------|
| Wides do not count as legal balls             | PASS   |
| No-balls do not count as legal balls          | PASS   |
| Byes count as legal balls                     | PASS   |
| Leg-byes count as legal balls                 | PASS   |
| Non-boundary four != boundary fact            | PASS   |
| Retired hurt is NOT a wicket                  | PASS   |
| Retired out IS a wicket, not bowler-credited  | PASS   |
| Run out IS a wicket, not bowler-credited      | PASS   |
| Stumped IS a wicket                           | PASS   |
| Penalty runs in extras and total              | PASS   |
| DLS target only from source, never invented   | PASS   |
| Partial final over shows X.N notation        | PASS   |
| Missing bowler defaults to "Unknown"          | PASS   |

### Fixture Reconciliation

| Fixture    | Innings   | Runs | Wickets | Overs | Status |
|------------|-----------|------|---------|-------|--------|
| 1529229 ODI| 0 India   | 351  | 7       | 50.0  | PASS   |
| 1529229 ODI| 1 WI chase| 352  | 5       | 48.2  | PASS   |
| 1552779 T20| 0 India   | 211  | 6       | 20.0  | PASS   |
| 1552779 T20| 1 Pakistan| 192  | 6       | 20.0  | PASS   |

---

## 5. Golden Interval Test Set

**File:** `backend/tests/test_golden_intervals.py` — 40 tests, all pass.

All expected values independently derived from raw Cricsheet JSON via `scratch/generate_golden.py`, NOT from engine output as oracle.

---

## 6. Property Tests

**File:** `backend/tests/test_phase1_property_and_fallback.py` — 16 tests, all pass.

| Test                                        | Result |
|---------------------------------------------|--------|
| Fallback scenarios pass verifier (x6)       | PASS   |
| Fallback clearly labelled non-AI            | PASS   |
| Singular "1 wicket" formatting              | PASS   |
| Singular "1 over" / no "1 overs"           | PASS   |
| Determinism: identical requests identical   | PASS   |
| Interval additivity sweep (all windows)     | PASS   |
| Delta matches raw-JSON aggregation (sampled)| PASS   |

---

## 7. Deterministic Story Functions

**File:** `backend/app/domain/story.py` — 44 tests in `test_story_functions.py`, all pass.

- `chapters`: T20/ODI phase windows, clamped, deduplicated, <=10 overs
- `story_beats`: <=4 evidence-grounded event cards, fixed priority
- `headline`: deterministic — wicket cluster >=3 / high tempo >=8 rpo / neutral fallback
- `required_rate_arc`: safe handling of chase complete / balls exhausted / fractional overs

No invented momentum, psychology, or player intent.

---

## 8. Verifier Hardening

**File:** `backend/app/verification/claim_verifier.py`

| Guard                                        | Status |
|----------------------------------------------|--------|
| Markdown link detection                      | OK     |
| Prohibited speculation/psychology/betting    | OK — extended with bare `\bbet\b` and 8 new Phase 1 phrases |
| Prompt injection in retrieved passages       | OK     |
| Ghost-name (ALL_CAPS_UNDERSCORE)             | OK     |
| Numeric prose grounding                      | OK — decimal false-positive fixed |
| Player identity grounding from cited facts   | OK     |
| Event claim cites event-type facts           | OK     |
| Score-delta cites STATE_MILESTONE fact       | OK     |
| Draft-status knowledge documents rejected    | OK     |
| Missing fact / knowledge IDs rejected        | OK     |

---

## 9. Files Changed

| File | Change |
|------|--------|
| `backend/app/match_engine/intervals.py` | Added `NON_BOWLER_CREDITED_DISMISSALS`; wicket facts are dismissal-kind-aware |
| `backend/app/match_engine/state.py` | Added `calculate_final_innings_snapshot()` and `NON_WICKET_DISMISSALS` |
| `backend/app/match_engine/cricket.py` | `reconstruct_completed_innings` uses `calculate_final_innings_snapshot` |
| `backend/app/match_engine/__init__.py` | Exports new helpers |
| `backend/app/domain/__init__.py` | New: domain package init |
| `backend/app/domain/story.py` | New: chapters, story_beats, headline, required_rate_arc |
| `backend/app/verification/claim_verifier.py` | Extended prohibited patterns; fixed decimal false-positive; added bare bet pattern |
| `backend/tests/test_phase1_correctness.py` | New: 18 regression tests |
| `backend/tests/test_golden_intervals.py` | New: 40 golden interval tests |
| `backend/tests/test_story_functions.py` | New: 44 story function tests |
| `backend/tests/test_phase1_engine_audit.py` | Fixed: wide delivery test; single-over boundary assertion |
| `backend/tests/test_phase1_property_and_fallback.py` | Fixed: _raw_stats Cricsheet structure bug |
| `backend/tests/test_cricket_reconciliation.py` | Fixed: innings 1 expected_overs=48, expected_legal_balls_in_over=2 |

---

## 10. Full Test Results

```
Command : .venv\Scripts\python.exe -m pytest backend\tests\ --cov=backend\app --cov=ingestion -q
Result  : 262 passed, 0 failed, 2 warnings in 64.02s
Exit    : 0
```

| Module                              | Coverage |
|-------------------------------------|----------|
| match_engine/intervals.py           | 100%     |
| match_engine/state.py               | 98%      |
| match_engine/cricket.py             | 98%      |
| adapters/cricket/normalizer.py      | 100%     |
| schemas/evidence.py                 | 100%     |
| domain/story.py                     | 92%      |
| verification/claim_verifier.py      | 83%      |
| api/catchup.py                      | 90%      |
| ingestion/knowledge/qdrant_store.py | 46% (requires live Qdrant) |
| **TOTAL**                           | **84%**  |

---

## 11. Unresolved Items

| Item | Severity | Note |
|------|----------|------|
| StarletteDeprecationWarning | Low | Upstream; no impact |
| PytestRemovedIn10Warning | Low | Deprecation; tests pass |
| Qdrant store coverage 46% | Medium | Requires live Qdrant |
| LLM provider coverage 39% | Medium | Requires live API key |
| Super-over exclusion | Low | Not in current fixtures |

---

## 12. Phase 2 Safety Assessment

**Phase 2 is SAFE to begin.**

All acceptance gates met:
- 262 tests pass, 0 fail
- Engine scorecard reconciliation correct on both fixtures (including partial over 48.2)
- Interval boundary convention pinned and documented
- Run-out / retired bowler credit fixed
- Verifier rejects fabricated numbers, speculation, betting language
- Deterministic fallback passes verifier on all 6 scenarios
- Story functions produce only evidence-grounded output
- 84% overall backend coverage

Do NOT begin Phase 2 if any test regresses below 262 passed.
