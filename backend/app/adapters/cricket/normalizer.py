"""Normalizer converting raw Cricsheet JSON into FanCue canonical contracts."""

from typing import Any, Dict, List, Optional

from backend.app.adapters.cricket.errors import (
    CricsheetDeliveryArithmeticError,
    CricsheetFormatError,
    MissingCriticalFieldError,
)
from backend.app.adapters.cricket.identifiers import generate_delivery_event_id
from backend.app.schemas.common import (
    MatchDescriptor,
    MatchMode,
    SportType,
)
from backend.app.schemas.cricket import (
    CricketDeliveryEvent,
    CricketDeliveryExtras,
    CricketDeliveryRuns,
    CricketWicket,
)


def normalize_match_descriptor(
    raw_data: Dict[str, Any],
    match_id: str,
    source_id: str,
    source_revision: str,
) -> MatchDescriptor:
    """Extract and normalize match-level metadata into MatchDescriptor."""
    info = raw_data.get("info", {})
    teams = info.get("teams", [])
    if len(teams) < 2:
        raise MissingCriticalFieldError(
            "Cricsheet info.teams must contain at least 2 teams.",
            context={"teams": teams},
        )

    # Standardize match name: 'Team A vs Team B'
    match_name = f"{teams[0]} vs {teams[1]}"
    match_format = info.get("match_type", "ODI")
    dates = info.get("dates", [])
    date_str = dates[0] if dates else "2026-01-01"
    venue = info.get("venue")

    innings_count = len(raw_data.get("innings", []))
    supported_innings = list(range(innings_count))

    return MatchDescriptor(
        match_id=match_id,
        sport=SportType.CRICKET,
        name=match_name,
        format=match_format,
        teams=teams[:2],
        date=date_str,
        venue=venue,
        mode=MatchMode.REPLAY,
        source_id=source_id,
        source_revision=source_revision,
        supported_innings=supported_innings,
    )


def normalize_innings_deliveries(
    raw_data: Dict[str, Any],
    match_id: str,
    innings_index: int,
) -> List[CricketDeliveryEvent]:
    """Convert raw Cricsheet over/delivery groupings into canonical CricketDeliveryEvents.
    
    Args:
        raw_data: Validated Cricsheet root dictionary.
        match_id: Internal match identifier.
        innings_index: 0-based innings index to extract.
        
    Returns:
        Chronologically ordered list of normalized CricketDeliveryEvent instances.
    """
    innings_list = raw_data.get("innings", [])
    if innings_index < 0 or innings_index >= len(innings_list):
        raise CricsheetFormatError(
            f"Requested innings_index {innings_index} out of bounds (total innings: {len(innings_list)}).",
            context={"innings_index": innings_index, "total_innings": len(innings_list)},
        )

    inn = innings_list[innings_index]
    overs_data = inn.get("overs", [])
    normalized_events: List[CricketDeliveryEvent] = []

    for over_group in overs_data:
        over_index = over_group.get("over")
        if over_index is None:
            raise MissingCriticalFieldError(
                "Missing 'over' index in Cricsheet over group.",
                context={"over_group": over_group},
            )

        deliveries = over_group.get("deliveries", [])
        running_legal_balls = 0

        for d_idx, d in enumerate(deliveries, start=1):
            runs_dict = d.get("runs")
            if not runs_dict:
                raise MissingCriticalFieldError(
                    f"Missing 'runs' object in over {over_index}, delivery {d_idx}.",
                    context={"delivery": d},
                )

            batter_runs = runs_dict.get("batter", 0)
            extras_runs = runs_dict.get("extras", 0)
            total_runs = runs_dict.get("total", 0)

            # Enforce arithmetic verification
            if batter_runs + extras_runs != total_runs:
                raise CricsheetDeliveryArithmeticError(
                    f"Delivery arithmetic mismatch: batter ({batter_runs}) + extras ({extras_runs}) "
                    f"!= total ({total_runs}) in over {over_index}, delivery {d_idx}.",
                    context={
                        "over": over_index,
                        "delivery": d_idx,
                        "batter_runs": batter_runs,
                        "extras_runs": extras_runs,
                        "total_runs": total_runs,
                    },
                )

            # Determine legal ball count
            raw_extras = d.get("extras", {})
            wides = raw_extras.get("wides", 0)
            noballs = raw_extras.get("noballs", 0)
            is_legal = (wides == 0 and noballs == 0)

            if is_legal:
                running_legal_balls += 1
                legal_ball_number = running_legal_balls
            else:
                legal_ball_number = 0

            # Normalize extras
            extras_model = None
            if raw_extras:
                extras_model = CricketDeliveryExtras(
                    wides=raw_extras.get("wides", 0),
                    noballs=raw_extras.get("noballs", 0),
                    byes=raw_extras.get("byes", 0),
                    legbyes=raw_extras.get("legbyes", 0),
                    penalty=raw_extras.get("penalty", 0),
                )

            # Normalize dismissals
            wickets_model = None
            raw_wickets = d.get("wickets")
            if raw_wickets:
                wickets_model = []
                for w in raw_wickets:
                    fielders = []
                    for f in w.get("fielders", []):
                        if isinstance(f, dict) and "name" in f:
                            fielders.append(f["name"])
                        elif isinstance(f, str):
                            fielders.append(f)

                    wickets_model.append(
                        CricketWicket(
                            player_out=w.get("player_out", "Unknown"),
                            kind=w.get("kind", "dismissed"),
                            fielders=fielders if fielders else None,
                        )
                    )

            event_id = generate_delivery_event_id(
                match_id=match_id,
                innings_index=innings_index,
                over_index=over_index,
                delivery_in_over=d_idx,
            )

            event = CricketDeliveryEvent(
                event_id=event_id,
                match_id=match_id,
                innings=innings_index,
                over=over_index,
                delivery_in_over=d_idx,
                legal_ball_number=legal_ball_number,
                batter=d.get("batter", "Unknown"),
                bowler=d.get("bowler", "Unknown"),
                non_striker=d.get("non_striker", "Unknown"),
                runs=CricketDeliveryRuns(
                    batter=batter_runs,
                    extras=extras_runs,
                    total=total_runs,
                ),
                extras=extras_model,
                wickets=wickets_model,
            )
            normalized_events.append(event)

    return normalized_events
