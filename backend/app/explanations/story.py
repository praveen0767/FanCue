"""Phase 1 — deterministic, evidence-grounded story presentation functions.

Design contract (enforced by backend/tests/test_story_functions.py):

- Every number in an output card/headline derives from authoritative engine
  facts (evidence packet state and fact payloads). No value is estimated.
- No player intentions, momentum claims, or subjective match psychology are
  ever emitted (AGENTS.md §2 non-goals; a numeric threshold may support a
  descriptive label only).
- Identical inputs yield identical outputs.

Chapter windows use USER-FACING 1-based over numbers for display semantics
(the engine's internal 0-based convention applies only to request contracts,
see backend/app/schemas/cricket.py CricketInterval).
"""

from typing import Dict, List, Optional

from backend.app.match_engine.cricket import CricketMatchEngine
from backend.app.schemas.evidence import FactType, MatchEvidencePacket

# Window-length cap: no single chapter window spans more than ten overs.
MAX_WINDOW_OVERS = 10

# Regulation innings lengths by format (authority: ICC playing conditions).
_REGULATION_OVERS = {"T20": 20, "ODI": 50}

# Fact display priority for story beats (lower = selected first).
BEAT_PRIORITY = {
    "wicket": 0,
    "big_over": 1,
    "six": 2,
    "maiden": 3,
}


def _allotted_overs(engine: CricketMatchEngine, innings: int) -> Optional[int]:
    """Authoritative innings length: the source-recorded target overs when the
    innings is a chase, otherwise the format's regulation limit. None when the
    format is not T20/ODI."""
    fmt = engine.descriptor.format.upper()
    regulation = _REGULATION_OVERS.get(fmt)
    if regulation is None:
        return None
    try:
        target = engine.get_innings_target(innings)
    except Exception:
        # Unknown innings index → documented limitation, never fabricated windows.
        return None
    if target is not None:
        return target["overs"]
    return regulation


def _available_overs(engine: CricketMatchEngine, innings: int, allotted: int) -> int:
    """Display overs actually available: never beyond what the source records."""
    events = engine.get_innings_events(innings)
    if not events:
        return 0
    max_recorded = max(d.over for d in events)   # 0-based index
    # User-facing overs touched by recorded play (partial over counts as touched).
    return min(allotted, max_recorded + 1)


def chapters(match: CricketMatchEngine, innings: int) -> List[Dict]:
    """Deterministic T20/ODI chapter phase windows for one innings.

    Args:
        match: CricketMatchEngine (raw data + descriptor) for the fixture.
        innings: 0-based innings index.

    Returns:
        Ordered list of chapter dicts:
            {"kind": str, "start_over": int, "end_over": int}
        with USER-FACING 1-based inclusive over numbers. Windows are clamped to
        available overs, deduplicated (first occurrence wins), and no window
        exceeds MAX_WINDOW_OVERS.

    Generates:
        - powerplay: opening phase (T20: overs 1-6, ODI: overs 1-10).
        - middle_overs: phase between powerplay and death, capped to the final
          MAX_WINDOW_OVERS overs of the middle phase.
        - death (20-over formats) / final_overs (50-over): closing phase.
        - last_three / last_five / last_six: trailing windows where meaningful
          (only when at least that many overs are available).

    Failure behaviour: returns [] (documented limitation, never fabricated
    windows) for non-T20/ODI formats, unknown innings indices, or innings with
    no recorded deliveries.
    """
    allotted = _allotted_overs(match, innings)
    if allotted is None:
        return []
    available = _available_overs(match, innings, allotted)
    if available == 0:
        return []

    windows: List[Dict] = []

    def add(kind: str, start: int, end: int) -> None:
        """Append a clamped, deduplicated window."""
        end = min(end, available)
        if end - start + 1 < 1 or end < start:
            return
        windows.append({"kind": kind, "start_over": start, "end_over": end})

    # Powerplay
    if match.descriptor.format.upper() == "T20":
        pp_end = 6
        death_span = 5
    else:
        pp_end = 10
        death_span = 10
    add("powerplay", 1, pp_end)

    # Middle overs, capped at MAX_WINDOW_OVERS (keep the most recent overs)
    middle_start = pp_end + 1
    middle_end = available - death_span
    if middle_end >= middle_start:
        capped_start = max(middle_start, middle_end - MAX_WINDOW_OVERS + 1)
        add("middle_overs", capped_start, middle_end)

    # Death / final phase (only when actually available)
    death_start = available - death_span + 1
    if death_start > pp_end:
        add("death" if match.descriptor.format.upper() == "T20" else "final_overs",
            death_start, available)

    # Trailing windows where meaningful
    for kind, span in (("last_three", 3), ("last_five", 5), ("last_six", 6)):
        if available >= span:
            add(kind, available - span + 1, available)

    # Deduplicate identical spans (first occurrence wins), preserving order.
    deduped: List[Dict] = []
    seen = set()
    for w in windows:
        span = (w["start_over"], w["end_over"])
        if span in seen:
            continue
        seen.add(span)
        deduped.append(w)
    return deduped


def _beat_from_fact(fact, kind: str) -> Optional[Dict]:
    """Map an EvidenceFact to a story-beat card; None when unmappable."""
    payload = fact.structured_payload
    over = payload.get("over")
    if over is None:
        # STATE_MILESTONE facts carry no over; they are not event cards.
        return None
    return {
        "kind": kind,
        "over": int(over),
        "text": fact.description,
        "fact_id": fact.fact_id,
    }


def story_beats(packet: MatchEvidencePacket) -> List[Dict]:
    """Return at most four supported event cards from an evidence packet.

    Documented fixed priority: wicket > big over > six > maiden. Bowling
    spells and top-scorer claims are NEVER fabricated — the packet contains
    no fact type that could support them.

    Cards are selected by priority up to four, then displayed in chronological
    order (by over, then priority within an over).
    """
    candidates: List[Dict] = []
    for fact in packet.key_facts:
        if fact.fact_type == FactType.WICKET:
            beat = _beat_from_fact(fact, "wicket")
        elif fact.fact_type == FactType.OVER_SUMMARY:
            runs = fact.structured_payload.get("runs", 0)
            beat = _beat_from_fact(
                fact, "big_over" if runs and int(runs) >= 15 else "maiden"
            )
        elif fact.fact_type == FactType.BOUNDARY:
            beat = _beat_from_fact(fact, "six")
        else:
            beat = None
        if beat is not None:
            candidates.append(beat)

    # Prioritised selection up to four cards.
    selected: List[Dict] = []
    for kind in sorted(BEAT_PRIORITY, key=BEAT_PRIORITY.get):
        for beat in candidates:
            if len(selected) >= 4:
                break
            if beat["kind"] == kind:
                selected.append(beat)
        if len(selected) >= 4:
            break

    # Chronological display order.
    selected.sort(key=lambda b: (b["over"], BEAT_PRIORITY[b["kind"]]))
    return selected


def headline(packet: MatchEvidencePacket, target: Optional[Dict] = None) -> str:
    """Deterministic headline from documented threshold signals.

    Signals (evaluated in order):
        1. target reached  — when an authoritative target dict
           {"overs", "runs"} is supplied and state_after.runs >= target runs.
        2. three or more wickets lost in the interval.
        3. interval run rate at least 25% above the pre-interval rate
           (pre-interval rate > 0).
        4. required-rate move of at least 1.0 — requires an authoritative target.

    Every emitted number equals an authoritative delta value exactly. When no
    signal fires, a neutral headline built from the interval delta is used.
    """
    delta = packet.state_delta
    wickets_word = "wicket" if delta.wickets_lost == 1 else "wickets"
    overs_word = "over" if delta.completed_overs_delta == 1 else "overs"
    base = (
        f"{delta.runs_added} {'run' if delta.runs_added == 1 else 'runs'} added for "
        f"{delta.wickets_lost} {wickets_word} across "
        f"{delta.completed_overs_delta} {overs_word}."
    )

    # Signal 1: target reached (requires authoritative target)
    if target is not None and packet.state_after.runs >= int(target["runs"]):
        return f"Target reached: {packet.state_after.runs}/{packet.state_after.wickets} after {packet.state_after.overs_completed} overs. {base}"

    # Signal 2: wicket-heavy interval
    if delta.wickets_lost >= 3:
        return f"{delta.wickets_lost} {wickets_word} fell during this stretch. {base}"

    # Signal 3: scoring tempo change of at least 25%
    prior_rate = packet.state_before.run_rate
    if prior_rate > 0 and delta.interval_run_rate >= prior_rate * 1.25:
        return (
            f"Scoring tempo rose — interval rate {delta.interval_run_rate:.2f} "
            f"against {prior_rate:.2f} before. {base}"
        )

    # Signal 4: required-rate move of at least 1.0 (authoritative target only)
    if target is not None:
        def _ball_rate(sp: int) -> Optional[float]:
            """Required-rate after sp overs elapsed, or None when the chase
            ended or balls ran out before that point."""
            elapsed = (sp + 1) * 6.0
            balls_total = int(target["overs"]) * 6
            if elapsed >= balls_total:
                return None
            runs_left = int(target["runs"]) - packet.state_after.runs if sp >= packet.state_delta.completed_overs_delta else int(target["runs"])
            if runs_left <= 0:
                return 0.0
            return round(runs_left / ((balls_total - elapsed) / 6.0), 2)
        end_window = delta.completed_overs_delta
        rate_start = _ball_rate(0)
        rate_end = _ball_rate(end_window)
        if rate_start is not None and rate_end is not None:
            if abs(rate_end - rate_start) >= 1.0:
                return (
                    f"Required rate moved from {rate_start:.2f} to {rate_end:.2f}. {base}"
                )

    return base


def required_rate_arc(
    packet: MatchEvidencePacket,
    target: Optional[Dict] = None,
) -> Optional[Dict]:
    """Chase required-rate arc computed ONLY from authoritative inputs.

    Args:
        packet: Evidence packet covering part of a chasing innings.
        target: Authoritative source target dict {"overs", "runs"}, or None.

    Returns:
        None when no authoritative target is supplied (never estimate),
        otherwise a dict:
            status                 'target_reached' | 'target_missed' | 'chasing'
            required_runs_start    runs needed at the interval's start boundary
            required_runs_end      runs needed at the interval's end boundary
            start_required_rate    required rpo at start (or None if 0 balls left)
            end_required_rate      required rpo at end (or None if 0 balls left)

    Zero-balls-remaining and completed chases are handled safely: a completed
    chase reports 'target_reached' with rate 0.0; a shortfall with no balls
    left reports 'target_missed' with no rates.
    """
    if target is None:
        return None

    target_runs = int(target["runs"])
    total_balls = int(target["overs"]) * 6
    balls_at_start = packet.state_before.overs_completed * 6
    balls_at_end = packet.state_after.overs_completed * 6

    runs_needed_start = target_runs - packet.state_before.runs
    runs_needed_end = target_runs - packet.state_after.runs

    if runs_needed_end <= 0:
        status = "target_reached"
    elif balls_at_end >= total_balls:
        status = "target_missed"
    else:
        status = "chasing"

    def _rate(balls_elapsed: int, runs_needed: int) -> Optional[float]:
        if runs_needed <= 0:
            return 0.0
        balls_left = total_balls - balls_elapsed
        if balls_left <= 0:
            return None
        return round(runs_needed / (balls_left / 6.0), 2)

    return {
        "status": status,
        "required_runs_start": max(runs_needed_start, 0),
        "required_runs_end": max(runs_needed_end, 0),
        "start_required_rate": _rate(balls_at_start, runs_needed_start),
        "end_required_rate": _rate(balls_at_end, runs_needed_end),
    }
