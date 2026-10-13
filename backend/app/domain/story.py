"""
Deterministic story functions for FanCue cricket catch-up.

These functions operate purely on authoritative evidence packet data
and pre-computed match states. They produce no prose, only structured
signals that the frontend or explanation layer can render.

RULES (enforced by design):
- No invented momentum, psychology, player intent, or speculation.
- Every number returned is derived from the evidence packet or delta.
- No DLS target inference — only display if authoritative target is in packet.
- No betting, prediction, or speculative language.
- Phase windows clamp to available overs; no window exceeds 10 overs.
- storyBeats returns at most 4 cards in chronological order.
- headline falls back to a neutral string when signals are absent.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from backend.app.schemas.cricket import CricketStateDelta
from backend.app.schemas.evidence import EvidenceFact, FactType, MatchEvidencePacket


# ── Phase window generation ────────────────────────────────────────────────────

# Max overs per window (inclusive range width)
MAX_WINDOW_OVERS = 10

# ODI phase definitions (user-facing over numbers, 1-indexed):
#   Powerplay: 1-10, Middle: 11-40, Death: 41-50
# T20 phase definitions:
#   Powerplay: 1-6, Middle: 7-15, Death: 16-20
_ODI_PHASES: List[Tuple[int, int, str]] = [
    (0, 9, "Powerplay"),       # overs 1-10 (0-indexed 0-9)
    (10, 39, "Middle"),        # overs 11-40
    (40, 49, "Death"),         # overs 41-50
]
_T20_PHASES: List[Tuple[int, int, str]] = [
    (0, 5, "Powerplay"),       # overs 1-6
    (6, 14, "Middle"),         # overs 7-15
    (15, 19, "Death"),         # overs 16-20
]


def chapters(
    match_format: str,
    innings_index: int,
    max_over_index: int,
    last_n_options: Optional[List[int]] = None,
) -> List[dict]:
    """Generate valid, non-overlapping chapter windows for the innings.

    Args:
        match_format: 'T20', 'ODI', or 'Test'. Unknown formats return empty list.
        innings_index: 0-based innings index (informational only, returned in windows).
        max_over_index: Maximum 0-indexed over recorded in the innings.
        last_n_options: Optional list of "last N overs" window sizes to include
                        (e.g. [3, 5, 6]). Defaults to [3, 5, 6] for T20, [5, 10] for ODI.

    Returns:
        List of dicts with keys:
            label (str): Human-readable name, e.g. "Powerplay" or "Last 5 overs".
            start_after_over (int): Exclusive start boundary.
            end_after_over (int): Inclusive end boundary.
            innings (int): innings_index.
        Windows are deduplicated and clamped to [0, max_over_index].
        Windows spanning more than MAX_WINDOW_OVERS are skipped.
    """
    fmt = match_format.upper()
    if fmt not in ("T20", "ODI", "TEST"):
        return []

    phases = _T20_PHASES if fmt == "T20" else _ODI_PHASES

    if last_n_options is None:
        last_n_options = [3, 5, 6] if fmt == "T20" else [5, 10]

    windows = []
    seen: set = set()

    def _add(label: str, start: int, end: int) -> None:
        """Add window after clamping and deduplication."""
        # Clamp to available overs
        start = max(start, -1)
        end = min(end, max_over_index)
        if end <= start:
            return
        width = end - start
        if width > MAX_WINDOW_OVERS:
            return  # too broad
        key = (start, end)
        if key in seen:
            return
        seen.add(key)
        windows.append({
            "label": label,
            "start_after_over": start,
            "end_after_over": end,
            "innings": innings_index,
        })

    # Phase-based windows
    for phase_start, phase_end, phase_name in phases:
        if phase_start > max_over_index:
            continue
        clamped_end = min(phase_end, max_over_index)
        span = clamped_end - phase_start + 1
        if span <= 0:
            continue
        # If the phase is wider than MAX_WINDOW_OVERS, split into first N and last N
        if span > MAX_WINDOW_OVERS:
            _add(f"{phase_name} (first {MAX_WINDOW_OVERS})", phase_start - 1, phase_start + MAX_WINDOW_OVERS - 1)
            _add(f"{phase_name} (last {MAX_WINDOW_OVERS})", clamped_end - MAX_WINDOW_OVERS, clamped_end)
        else:
            _add(phase_name, phase_start - 1, clamped_end)

    # Last-N windows (tail of innings)
    for n in last_n_options:
        if n <= 0 or n > MAX_WINDOW_OVERS:
            continue
        end = max_over_index
        start = end - n  # start_after_over is exclusive, so start = end - n
        if start < -1:
            start = -1
        label = f"Last {n} over{'s' if n != 1 else ''}"
        _add(label, start, end)

    return windows


# ── Story beats ────────────────────────────────────────────────────────────────

# Priority ordering for beat types (lower index = higher priority)
_BEAT_PRIORITY = [
    FactType.WICKET,
    FactType.STATE_MILESTONE,
    FactType.OVER_SUMMARY,
    FactType.BOUNDARY,
    FactType.PARTNERSHIP,
    FactType.MATCH_RESULT,
]

MAX_STORY_BEATS = 4


@dataclass(frozen=True)
class StoryBeat:
    """A supported, evidence-grounded story event card."""
    beat_type: str      # fact_type value string
    label: str          # Short headline for the card (≤80 chars)
    description: str    # Full canonical description from the evidence fact
    fact_id: str        # Backing fact_id
    over: Optional[int] = None  # 1-indexed over, if available


def story_beats(packet: MatchEvidencePacket) -> List[StoryBeat]:
    """Return at most MAX_STORY_BEATS supported event cards from the evidence packet.

    Selection rules:
    1. Only facts from packet.key_facts are eligible (no invention).
    2. Priority order: wicket > milestone > over_summary > boundary > partnership > result.
    3. Within each priority tier, chronological order is preserved.
    4. Result is at most MAX_STORY_BEATS cards.
    5. If no facts are available, returns an empty list — NOT a fabricated summary.

    Args:
        packet: Assembled MatchEvidencePacket with authoritative key_facts.

    Returns:
        Ordered list of StoryBeat dataclasses (chronological within priority order).
    """
    if not packet.key_facts:
        return []

    # Group facts by priority bucket maintaining original order within bucket
    priority_index = {ft: i for i, ft in enumerate(_BEAT_PRIORITY)}
    sorted_facts = sorted(
        packet.key_facts,
        key=lambda f: (priority_index.get(f.fact_type, len(_BEAT_PRIORITY)), 0)
    )

    beats = []
    for fact in sorted_facts:
        if len(beats) >= MAX_STORY_BEATS:
            break
        over = fact.structured_payload.get("over")  # 1-indexed if present
        label = _fact_to_label(fact)
        beats.append(StoryBeat(
            beat_type=fact.fact_type.value,
            label=label,
            description=fact.description,
            fact_id=fact.fact_id,
            over=int(over) if over is not None else None,
        ))

    return beats


def _fact_to_label(fact: EvidenceFact) -> str:
    """Generate a short label for a story beat from a fact payload."""
    p = fact.structured_payload
    if fact.fact_type == FactType.WICKET:
        player = p.get("player_out", "Unknown")
        kind = p.get("kind", "dismissed")
        over = p.get("over", "?")
        return f"{player} — {kind} (over {over})"
    elif fact.fact_type == FactType.BOUNDARY:
        batter = p.get("batter", "Unknown")
        runs = p.get("runs", "?")
        over = p.get("over", "?")
        return f"{batter} hits {runs} in over {over}"
    elif fact.fact_type == FactType.OVER_SUMMARY:
        over = p.get("over", "?")
        runs = p.get("runs", 0)
        if runs == 0:
            bowler = p.get("bowler", "Unknown")
            return f"Maiden — {bowler} (over {over})"
        return f"{runs} runs in over {over}"
    elif fact.fact_type == FactType.STATE_MILESTONE:
        return fact.description[:80]
    return fact.description[:80]


# ── Headline ──────────────────────────────────────────────────────────────────

# Thresholds for deterministic headline triggers
_WICKET_CLUSTER_THRESHOLD = 3          # ≥3 wickets → "X wickets fell"
_TEMPO_CHANGE_PCT_THRESHOLD = 0.25     # ≥25% change in run rate from start to interval
_REQUIRED_RATE_CHANGE_THRESHOLD = 1.0  # ≥1.0 rpo change in required rate
_HIGH_SCORING_RPO = 8.0                # ≥8 rpo considered high-tempo


def headline(packet: MatchEvidencePacket) -> str:
    """Return a short, deterministic headline string for the interval.

    Signals checked (in order of priority):
    1. Match result: target reached or not.
    2. Wicket cluster: ≥3 wickets in interval → "X wickets fell"
    3. High tempo: interval run rate ≥ _HIGH_SCORING_RPO and ≥3 overs
    4. Neutral: "Over X–Y: <runs> runs, <wickets> wicket(s)"

    Rules:
    - Every number must be derivable from packet.state_delta.
    - No invented narrative ("India searching", "dominance", etc.)
    - If signals are absent or delta is unavailable, return neutral.

    Args:
        packet: Assembled evidence packet with authoritative state_delta.

    Returns:
        Short headline string (≤120 chars).
    """
    delta = packet.state_delta
    if not isinstance(delta, CricketStateDelta):
        return _neutral_headline(packet)

    runs = delta.runs_added
    wickets = delta.wickets_lost
    overs = delta.completed_overs_delta
    rpo = delta.interval_run_rate

    # Signal 1: Match result (match_result fact present in packet)
    result_facts = [f for f in packet.key_facts if f.fact_type == FactType.MATCH_RESULT]
    if result_facts:
        return result_facts[0].description[:120]

    # Signal 2: Wicket cluster
    if wickets >= _WICKET_CLUSTER_THRESHOLD:
        wkt_word = "wicket" if wickets == 1 else "wickets"
        return f"{wickets} {wkt_word} fell — {runs} runs in {_overs_label(overs)}"

    # Signal 3: High scoring tempo
    if overs >= 3 and rpo >= _HIGH_SCORING_RPO:
        return f"{runs} runs in {_overs_label(overs)} at {rpo:.1f} rpo"

    # Default: neutral
    return _neutral_headline(packet)


def _neutral_headline(packet: MatchEvidencePacket) -> str:
    """Neutral headline from state delta."""
    delta = packet.state_delta
    if not isinstance(delta, CricketStateDelta):
        return "Match interval summary"
    runs = delta.runs_added
    wickets = delta.wickets_lost
    overs = delta.completed_overs_delta
    wkt_word = "wicket" if wickets == 1 else "wickets"
    ovs_label = _overs_label(overs)
    return f"{runs} runs, {wickets} {wkt_word} in {ovs_label}"


def _overs_label(overs: int) -> str:
    word = "over" if overs == 1 else "overs"
    return f"{overs} {word}"


# ── Required rate arc ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RequiredRateArc:
    """Authoritative chase arc — only produced when all source data is present."""
    runs_required: int
    balls_remaining: int
    required_rate: float         # runs per over (6 balls), rounded to 2 dp
    is_chase_complete: bool
    is_impossible: bool          # balls_remaining == 0 and runs_required > 0


def required_rate_arc(
    target: Optional[int],
    runs_scored: Optional[int],
    balls_remaining: Optional[int],
) -> Optional[RequiredRateArc]:
    """Calculate a chase arc from authoritative source values.

    Returns None (not an empty arc) when any required input is absent.
    Callers must display None as "Required rate: N/A — data not available"
    rather than inventing a value.

    Args:
        target: Authoritative target runs (must be from source, not DLS estimate).
        runs_scored: Runs scored by the chasing side so far.
        balls_remaining: Legal balls remaining in the innings.

    Returns:
        RequiredRateArc if all inputs are present, else None.
    """
    if target is None or runs_scored is None or balls_remaining is None:
        return None

    runs_required = target - runs_scored
    is_complete = runs_required <= 0
    is_impossible = balls_remaining == 0 and runs_required > 0

    if is_complete or is_impossible or balls_remaining == 0:
        rr = 0.0
    else:
        overs_remaining = balls_remaining / 6.0
        rr = round(runs_required / overs_remaining, 2)

    return RequiredRateArc(
        runs_required=max(0, runs_required),
        balls_remaining=balls_remaining,
        required_rate=rr,
        is_chase_complete=is_complete,
        is_impossible=is_impossible,
    )
