"""Interval filtering and deterministic evidence fact extraction."""

from collections import defaultdict
from typing import List

from backend.app.adapters.cricket.identifiers import generate_fact_id
from backend.app.match_engine.errors import InvalidIntervalError
from backend.app.schemas.cricket import CricketDeliveryEvent
from backend.app.schemas.evidence import EvidenceFact, FactType

# Dismissal kinds that are considered a lost wicket but are NOT credited to
# the bowler under ICC Laws. For these, descriptions omit 'off bowling of' and
# the payload omits 'bowler'.
# Source: ICC Laws of Cricket — Law 38 (run out), Law 37 (obstructing the field),
#         Law 30.3 (retired out), Law 40 (timed out).
NON_BOWLER_CREDITED_DISMISSALS: frozenset = frozenset({
    "run out",
    "obstructing the field",
    "retired out",
    "timed out",
    "hit the ball twice",
})

# Dismissal-kind records that are NOT dismissals at all. Cricsheet reports them
# under 'wickets' even though no wicket has fallen (e.g. a batter leaving the
# field injured with permission). We use the same set the state engine uses so
# fact generation and state computation can never disagree.
from backend.app.match_engine.state import NON_WICKET_DISMISSALS  # noqa: E402


def filter_interval_deliveries(
    deliveries: List[CricketDeliveryEvent],
    start_after_over: int,
    end_after_over: int,
) -> List[CricketDeliveryEvent]:
    """Extract deliveries strictly within (start_after_over, end_after_over].
    
    Start boundary is exclusive; end boundary is inclusive.
    """
    if end_after_over <= start_after_over:
        raise InvalidIntervalError(
            f"end_after_over ({end_after_over}) must be strictly greater than "
            f"start_after_over ({start_after_over}).",
            context={"start_after_over": start_after_over, "end_after_over": end_after_over},
        )
    if start_after_over < -1:
        raise InvalidIntervalError(
            f"start_after_over ({start_after_over}) cannot be less than -1.",
            context={"start_after_over": start_after_over},
        )

    return [
        d for d in deliveries
        if start_after_over < d.over <= end_after_over
    ]


def extract_key_facts(
    match_id: str,
    innings_index: int,
    source_revision: str,
    interval_deliveries: List[CricketDeliveryEvent],
) -> List[EvidenceFact]:
    """Deterministically extract and rank key consequential evidence facts from interval deliveries.
    
    Includes:
    - Dismissal events (wickets)
    - Boundaries (sixes)
    - Consequential over summaries (high scoring overs >= 15 runs, maiden overs)
    """
    facts: List[EvidenceFact] = []

    # 1. Extract Wickets (only records that represent an actual dismissal
    # — 'retired hurt' / 'retired not out' entries produce no WICKET fact).
    for d in interval_deliveries:
        dismissed_records = [
            w for w in (d.wickets or [])
            if w.kind.strip().lower() not in NON_WICKET_DISMISSALS
        ]
        for w_idx, w in enumerate(dismissed_records):
                fact_id = generate_fact_id(
                    match_id=match_id,
                    innings_index=innings_index,
                    over_index=d.over,
                    fact_type="wicket",
                    disambiguator=f"{w.player_out}_{w_idx}",
                )

                # Determine whether this dismissal is credited to the bowler.
                # Run-outs, obstructing-the-field, retired, etc. are NOT.
                kind_normalised = w.kind.strip().lower()
                bowler_credited = kind_normalised not in NON_BOWLER_CREDITED_DISMISSALS

                if bowler_credited:
                    desc = (
                        f"WICKET: {w.player_out} was dismissed ({w.kind}) "
                        f"off bowling of {d.bowler} in over {d.over + 1}."
                    )
                    payload: dict = {
                        "player_out": w.player_out,
                        "bowler": d.bowler,
                        "kind": w.kind,
                        "over": d.over + 1,
                        "delivery": d.delivery_in_over,
                    }
                else:
                    desc = (
                        f"WICKET: {w.player_out} was dismissed ({w.kind}) "
                        f"in over {d.over + 1}."
                    )
                    payload = {
                        "player_out": w.player_out,
                        "kind": w.kind,
                        "over": d.over + 1,
                        "delivery": d.delivery_in_over,
                    }

                facts.append(
                    EvidenceFact(
                        fact_id=fact_id,
                        fact_type=FactType.WICKET,
                        match_id=match_id,
                        source_revision=source_revision,
                        referenced_event_ids=[d.event_id],
                        description=desc,
                        structured_payload=payload,
                    )
                )

    # 2. Extract Sixes
    for d in interval_deliveries:
        if d.runs.batter >= 6:
            fact_id = generate_fact_id(
                match_id=match_id,
                innings_index=innings_index,
                over_index=d.over,
                fact_type="boundary",
                disambiguator=f"six_d{d.delivery_in_over}",
            )
            desc = f"SIX: {d.batter} hit a 6 off {d.bowler} in over {d.over + 1}."
            facts.append(
                EvidenceFact(
                    fact_id=fact_id,
                    fact_type=FactType.BOUNDARY,
                    match_id=match_id,
                    source_revision=source_revision,
                    referenced_event_ids=[d.event_id],
                    description=desc,
                    structured_payload={
                        "batter": d.batter,
                        "bowler": d.bowler,
                        "runs": 6,
                        "over": d.over + 1,
                    },
                )
            )

    # 3. Over-level summaries (Maidens or big overs >= 15 runs)
    over_deliveries = defaultdict(list)
    for d in interval_deliveries:
        over_deliveries[d.over].append(d)

    for over_idx, ov_delivs in sorted(over_deliveries.items()):
        over_runs = sum(d.runs.total for d in ov_delivs)
        over_event_ids = [d.event_id for d in ov_delivs]

        if over_runs >= 15:
            fact_id = generate_fact_id(
                match_id=match_id,
                innings_index=innings_index,
                over_index=over_idx,
                fact_type="over_summary",
                disambiguator=f"big_over_{over_runs}runs",
            )
            desc = f"HIGH-SCORING OVER: Over {over_idx + 1} yielded {over_runs} runs."
            facts.append(
                EvidenceFact(
                    fact_id=fact_id,
                    fact_type=FactType.OVER_SUMMARY,
                    match_id=match_id,
                    source_revision=source_revision,
                    referenced_event_ids=over_event_ids,
                    description=desc,
                    structured_payload={
                        "over": over_idx + 1,
                        "runs": over_runs,
                    },
                )
            )
        elif over_runs == 0 and sum(1 for d in ov_delivs if d.legal_ball_number > 0) == 6:
            fact_id = generate_fact_id(
                match_id=match_id,
                innings_index=innings_index,
                over_index=over_idx,
                fact_type="over_summary",
                disambiguator="maiden",
            )
            bowler = ov_delivs[0].bowler if ov_delivs else "Unknown"
            desc = f"MAIDEN OVER: {bowler} bowled a maiden in over {over_idx + 1}."
            facts.append(
                EvidenceFact(
                    fact_id=fact_id,
                    fact_type=FactType.OVER_SUMMARY,
                    match_id=match_id,
                    source_revision=source_revision,
                    referenced_event_ids=over_event_ids,
                    description=desc,
                    structured_payload={
                        "over": over_idx + 1,
                        "bowler": bowler,
                        "runs": 0,
                    },
                )
            )

    return facts
