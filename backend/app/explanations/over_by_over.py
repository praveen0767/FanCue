"""Build a concise, fully source-grounded over-by-over cricket story."""

from collections import defaultdict
from typing import Dict, List

from backend.app.match_engine.cricket import CricketMatchEngine
from backend.app.match_engine.state import NON_WICKET_DISMISSALS, calculate_state_snapshot
from backend.app.schemas.cricket import CricketCatchUpRequest
from backend.app.schemas.explanation import CricketBallStory, CricketOverStory


def _wicket_details(delivery) -> List[str]:
    """List true dismissals only; retired-hurt/not-out records are not wickets."""
    return [
        f"{w.player_out} ({w.kind})"
        for w in (delivery.wickets or [])
        if w.kind.strip().lower() not in NON_WICKET_DISMISSALS
    ]


def _ball_story(delivery, wickets: List[str]) -> CricketBallStory:
    extras = delivery.extras
    wides = extras.wides if extras else 0
    no_balls = extras.noballs if extras else 0
    byes = extras.byes if extras else 0
    leg_byes = extras.legbyes if extras else 0
    batter_runs = delivery.runs.batter
    total_runs = delivery.runs.total

    if wickets:
        event_label = "WICKET"
        display = "W"
    elif no_balls:
        event_label = "NO BALL"
        display = f"Nb+{total_runs}"
    elif wides:
        event_label = "WIDE"
        display = f"Wd+{total_runs}"
    elif batter_runs == 6:
        event_label = "SIX"
        display = "6"
    elif batter_runs == 4:
        event_label = "FOUR"
        display = "4"
    elif byes:
        event_label = "BYES"
        display = f"B+{total_runs}"
    elif leg_byes:
        event_label = "LEG BYES"
        display = f"Lb+{total_runs}"
    elif batter_runs:
        event_label = "RUNS"
        display = str(total_runs)
    elif total_runs:
        event_label = "EXTRAS"
        display = f"E+{total_runs}"
    else:
        event_label = "DOT"
        display = "·"

    return CricketBallStory(
        delivery_number=delivery.delivery_in_over,
        display=display,
        event_label=event_label,
        batter=delivery.batter,
        bowler=delivery.bowler,
        runs_off_bat=batter_runs,
        total_runs=total_runs,
        extras=delivery.runs.extras,
        is_legal=delivery.legal_ball_number > 0,
        wicket_detail=", ".join(wickets) if wickets else None,
    )


def build_over_by_over(
    engine: CricketMatchEngine,
    request: CricketCatchUpRequest,
) -> List[CricketOverStory]:
    """Summarize every over intersecting the requested (start, end] interval.

    All scores and events are computed from normalized source deliveries. The
    summary deliberately avoids model-generated or speculative match psychology.
    """
    interval = request.interval
    all_deliveries = engine.get_innings_events(interval.innings)
    deliveries_by_over: Dict[int, list] = defaultdict(list)

    for delivery in all_deliveries:
        if interval.start_after_over < delivery.over <= interval.end_after_over:
            deliveries_by_over[delivery.over].append(delivery)

    stories: List[CricketOverStory] = []
    for over_index in sorted(deliveries_by_over):
        over_deliveries = sorted(
            deliveries_by_over[over_index],
            key=lambda item: item.delivery_in_over,
        )
        wicket_events = [
            detail
            for delivery in over_deliveries
            for detail in _wicket_details(delivery)
        ]
        over_runs = sum(item.runs.total for item in over_deliveries)
        over_extras = sum(item.runs.extras for item in over_deliveries)
        legal_balls = sum(1 for item in over_deliveries if item.legal_ball_number > 0)
        snapshot = calculate_state_snapshot(all_deliveries, over_index)

        balls: List[CricketBallStory] = []
        highlights: List[str] = []
        for delivery in over_deliveries:
            wickets = _wicket_details(delivery)
            balls.append(_ball_story(delivery, wickets))
            if wickets:
                highlights.extend(f"WICKET — {detail}" for detail in wickets)
            elif delivery.runs.batter == 6:
                highlights.append(f"SIX — {delivery.batter} off {delivery.bowler}")
            elif delivery.runs.batter == 4:
                highlights.append(f"FOUR — {delivery.batter} off {delivery.bowler}")

        if over_runs >= 15:
            highlights.append(f"Big over — {over_runs} runs")
        if not highlights:
            highlights.append(f"{over_runs} runs from {legal_balls} legal balls")

        if wicket_events:
            wicket_word = "wicket" if len(wicket_events) == 1 else "wickets"
            recap = (
                f"{over_runs} runs on the board, but {len(wicket_events)} "
                f"{wicket_word} fell."
            )
        elif legal_balls == 6 and over_runs == 0:
            recap = "A maiden over — six legal balls, no runs conceded."
        elif over_runs >= 15:
            recap = f"A big over: {over_runs} runs added without losing a wicket."
        else:
            run_word = "run" if over_runs == 1 else "runs"
            recap = f"The batters added {over_runs} {run_word} without losing a wicket."

        stories.append(
            CricketOverStory(
                over_number=over_index + 1,
                runs=over_runs,
                wickets=len(wicket_events),
                extras=over_extras,
                legal_balls=legal_balls,
                score_after_runs=snapshot.runs,
                score_after_wickets=snapshot.wickets,
                run_rate_after=snapshot.run_rate,
                recap=recap,
                highlights=highlights[:12],
                balls=balls,
            )
        )

    return stories
