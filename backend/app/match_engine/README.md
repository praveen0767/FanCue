# backend/app/match_engine/

Deterministic match state reconstruction and state-difference calculation.

This is the **single authoritative source of match facts** in FanCue.
No other module may write or mutate match state.

Responsibilities:
- Accept normalized sport events from a sport adapter
- Reconstruct match state at any given event boundary
- Calculate the state difference between two state snapshots (the interval)
- Return read-only state objects to downstream components

Determinism requirement:
- Same input events must always produce the same output state.
- All functions must be pure (no side effects, no external calls).
- Every edge case must have a corresponding unit test.

**Phase 00: Not implemented. Implementation begins Phase 03.**
