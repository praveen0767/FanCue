"""Deterministic identifier generation for cricket events, facts, and packets."""


def generate_delivery_event_id(
    match_id: str,
    innings_index: int,
    over_index: int,
    delivery_in_over: int,
) -> str:
    """Produce a deterministic, content-addressed event identifier for a single delivery.
    
    Format: {match_id}_inn{innings_index}_ov{over_index}_d{delivery_in_over}
    Example: '1529229_inn0_ov2_d3'
    """
    return f"{match_id}_inn{innings_index}_ov{over_index}_d{delivery_in_over}"


def generate_fact_id(
    match_id: str,
    innings_index: int,
    over_index: int,
    fact_type: str,
    disambiguator: str,
) -> str:
    """Produce a deterministic identifier for an atomic evidence fact.
    
    Format: fact_{match_id}_inn{innings_index}_ov{over_index}_{fact_type}_{disambiguator}
    Example: 'fact_1529229_inn0_ov2_wicket_shubman_gill'
    """
    clean_disambiguator = disambiguator.lower().replace(" ", "_")
    return f"fact_{match_id}_inn{innings_index}_ov{over_index}_{fact_type}_{clean_disambiguator}"


def generate_packet_id(
    match_id: str,
    innings_index: int,
    start_after_over: int,
    end_after_over: int,
) -> str:
    """Produce a deterministic identifier for a match interval evidence packet.
    
    Format: pkt_{match_id}_inn{innings_index}_{start_after_over}_{end_after_over}
    Example: 'pkt_1529229_inn0_14_22'
    """
    return f"pkt_{match_id}_inn{innings_index}_{start_after_over}_{end_after_over}"
