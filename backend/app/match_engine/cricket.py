"""Authoritative deterministic cricket match engine."""

from typing import Dict, List, Optional, Tuple

from backend.app.adapters.cricket.identifiers import generate_packet_id
from backend.app.adapters.cricket.normalizer import (
    normalize_innings_deliveries,
    normalize_match_descriptor,
)
from backend.app.adapters.cricket.parser import load_cricsheet_json
from backend.app.match_engine.errors import (
    InningsIndexOutOfBoundsError,
    OverBoundaryNotFoundError,
    ReconciliationError,
)
from backend.app.match_engine.intervals import (
    extract_key_facts,
    filter_interval_deliveries,
)
from backend.app.match_engine.state import (
    calculate_state_delta,
    calculate_state_snapshot,
    calculate_final_innings_snapshot,
)
from backend.app.schemas.common import MatchDescriptor, SportType
from backend.app.schemas.cricket import (
    CricketCatchUpRequest,
    CricketDeliveryEvent,
    CricketScoreSnapshot,
    CricketStateDelta,
)
from backend.app.schemas.evidence import EvidenceFact, FactType, MatchEvidencePacket
from backend.app.schemas.provenance import SourceProvenance


class CricketMatchEngine:
    """Pure, deterministic state reconstruction engine for cricket matches."""

    def __init__(
        self,
        raw_data: Dict,
        match_id: str,
        provenance: SourceProvenance,
    ):
        self.raw_data = raw_data
        self.match_id = match_id
        self.provenance = provenance
        self.descriptor: MatchDescriptor = normalize_match_descriptor(
            raw_data=raw_data,
            match_id=match_id,
            source_id=provenance.source_id,
            source_revision=provenance.dataset_revision,
        )
        self._innings_deliveries: Dict[int, List[CricketDeliveryEvent]] = {}

    @classmethod
    def from_fixture(
        cls,
        file_path: str,
        match_id: str,
        provenance: SourceProvenance,
        expected_sha256: Optional[str] = None,
    ) -> "CricketMatchEngine":
        """Factory creating engine from a raw Cricsheet JSON file."""
        data = load_cricsheet_json(file_path=file_path, expected_sha256=expected_sha256)
        return cls(raw_data=data, match_id=match_id, provenance=provenance)

    @property
    def match_descriptor(self) -> MatchDescriptor:
        """Property alias for canonical match descriptor (used by orchestration layer)."""
        return self.descriptor

    def get_match_descriptor(self) -> MatchDescriptor:
        """Return canonical match descriptor."""
        return self.descriptor

    def get_innings_events(self, innings_index: int) -> List[CricketDeliveryEvent]:
        """Return normalized delivery events for specified innings."""
        total_innings = len(self.raw_data.get("innings", []))
        if innings_index < 0 or innings_index >= total_innings:
            raise InningsIndexOutOfBoundsError(
                f"Innings index {innings_index} does not exist (available: 0 to {total_innings - 1}).",
                context={"innings_index": innings_index, "total_innings": total_innings},
            )

        if innings_index not in self._innings_deliveries:
            self._innings_deliveries[innings_index] = normalize_innings_deliveries(
                raw_data=self.raw_data,
                match_id=self.match_id,
                innings_index=innings_index,
            )

        return self._innings_deliveries[innings_index]

    def validate_boundary_availability(self, innings_index: int, boundary: int) -> None:
        """Confirm that a boundary exists within recorded match progression.
        
        boundary = -1 is always valid (innings start).
        boundary >= 0 must not exceed max recorded over in the innings.
        """
        if boundary == -1:
            return

        events = self.get_innings_events(innings_index)
        if not events:
            raise OverBoundaryNotFoundError(
                f"No events found for innings {innings_index}.",
                context={"innings_index": innings_index},
            )

        max_over = max(d.over for d in events)
        if boundary > max_over:
            raise OverBoundaryNotFoundError(
                f"Requested boundary after_over {boundary} exceeds maximum recorded over {max_over} "
                f"for innings {innings_index}.",
                context={
                    "requested_boundary": boundary,
                    "max_recorded_over": max_over,
                    "innings_index": innings_index,
                },
            )

    def reconstruct_interval(
        self,
        request: CricketCatchUpRequest,
    ) -> Tuple[
        CricketScoreSnapshot,
        CricketScoreSnapshot,
        CricketStateDelta,
        List[EvidenceFact],
        MatchEvidencePacket,
    ]:
        """Reconstruct states, deltas, and evidence packet for a fan request.
        
        Returns:
            Tuple of (state_before, state_after, state_delta, key_facts, evidence_packet)
        """
        innings_idx = request.interval.innings
        start_bound = request.interval.start_after_over
        end_bound = request.interval.end_after_over

        # Validate boundaries
        self.validate_boundary_availability(innings_idx, start_bound)
        self.validate_boundary_availability(innings_idx, end_bound)

        deliveries = self.get_innings_events(innings_idx)

        # 1. Deterministic snapshots
        state_before = calculate_state_snapshot(deliveries, start_bound)
        state_after = calculate_state_snapshot(deliveries, end_bound)

        # 2. Extract interval deliveries
        interval_delivs = filter_interval_deliveries(deliveries, start_bound, end_bound)

        # 3. Calculate deterministic delta
        delta = calculate_state_delta(state_before, state_after, interval_delivs)

        # 4. Extract atomic key facts
        facts = extract_key_facts(
            match_id=self.match_id,
            innings_index=innings_idx,
            source_revision=self.provenance.dataset_revision,
            interval_deliveries=interval_delivs,
        )

        # 4b. Deterministic state-milestone fact. Located in the ENGINE (not the
        # enrichment layer) so that every packet — including engine-only packets
        # used by the deterministic fallback — carries a citable, authoritative
        # STATE_MILESTONE fact for interval-delta claims.
        delta_fact = self._build_state_milestone_fact(
            innings_idx, start_bound, end_bound, state_before, state_after, delta,
        )
        facts = [delta_fact] + facts
        # 5. Assemble Evidence Packet
        packet_id = generate_packet_id(
            match_id=self.match_id,
            innings_index=innings_idx,
            start_after_over=start_bound,
            end_after_over=end_bound,
        )
        human_start = "innings start" if start_bound == -1 else f"over {start_bound + 1}"
        human_end = f"over {end_bound + 1}"
        interval_summary = f"Innings {innings_idx}: After {human_start} through {human_end}"

        packet = MatchEvidencePacket(
            packet_id=packet_id,
            match_id=self.match_id,
            sport=SportType.CRICKET,
            interval_summary=interval_summary,
            state_before=state_before,
            state_after=state_after,
            state_delta=delta,
            key_facts=facts,
            retrieved_knowledge_ids=[],  # Filled in Phase 04 by Qdrant
            provenance=self.provenance,
        )

        return state_before, state_after, delta, facts, packet

    def reconstruct_completed_innings(self, innings_index: int) -> CricketScoreSnapshot:
        """Calculate the authoritative end-of-innings state, correctly
        representing partial final overs (e.g. 48.2 overs for an innings
        that ended after 2 legal balls in the 49th over).
        """
        deliveries = self.get_innings_events(innings_index)
        if not deliveries:
            return CricketScoreSnapshot(runs=0, wickets=0, overs_completed=0)
        return calculate_final_innings_snapshot(deliveries)

    def _build_state_milestone_fact(
        self,
        innings_idx: int,
        start_bound: int,
        end_bound: int,
        state_before: CricketScoreSnapshot,
        state_after: CricketScoreSnapshot,
        delta: CricketStateDelta,
    ) -> EvidenceFact:
        """Build the deterministic STATE_MILESTONE evidence fact for an interval.

        Inputs come exclusively from the engine's own snapshot/delta output, so
        the fact is always consistent with the authoritative state.
        """
        fact_id = (
            f"fact_{self.match_id}_inn{innings_idx}_"
            f"delta_{start_bound}_{end_bound}"
        )
        return EvidenceFact(
            fact_id=fact_id,
            fact_type=FactType.STATE_MILESTONE,
            match_id=self.match_id,
            source_revision=self.provenance.dataset_revision,
            referenced_event_ids=[f"state_delta_{start_bound}_{end_bound}"],
            description=(
                f"Interval progression: {delta.runs_added} runs scored, "
                f"{delta.wickets_lost} wickets fallen in "
                f"{delta.completed_overs_delta} completed "
                f"{'' if delta.completed_overs_delta == 1 else 'overs'} "
                f"(run rate: {delta.interval_run_rate:.2f} rpo)."
            ),
            structured_payload={
                "runs_added": delta.runs_added,
                "wickets_lost": delta.wickets_lost,
                "completed_overs_delta": delta.completed_overs_delta,
                "legal_balls_added": delta.legal_balls_added,
                "extras_added": delta.extras_added,
                "interval_run_rate": delta.interval_run_rate,
                "start_runs": state_before.runs,
                "end_runs": state_after.runs,
                "start_wickets": state_before.wickets,
                "end_wickets": state_after.wickets,
            },
        )

    def get_innings_target(self, innings_index: int) -> Optional[Dict]:
        """Return the authoritative target recorded by the SOURCE for an innings.

        Returns the raw target dict ({
            "overs", "runs"}) when the source itself records one, otherwise None.
        The engine NEVER synthesises a revised DLS target: if the source does not
        carry target information, callers must display no target at all.
        """
        innings_list = self.raw_data.get("innings", [])
        if innings_index < 0 or innings_index >= len(innings_list):
            raise InningsIndexOutOfBoundsError(
                f"Innings index {innings_index} does not exist "
                f"(available: 0 to {len(innings_list) - 1}).",
                context={"innings_index": innings_index},
            )
        target = innings_list[innings_index].get("target")
        if not target:
            return None
        return {
            "overs": int(target["overs"]),
            "runs": int(target["runs"]),
        }

    def reconcile_innings(
        self,
        innings_index: int,
        expected_runs: int,
        expected_wickets: int,
        expected_overs: Optional[int] = None,
        expected_legal_balls_in_over: Optional[int] = None,
    ) -> bool:
        """Reconcile calculated innings totals against independent scorecard figures.
        
        expected_legal_balls_in_over, when supplied, additionally reconciles the
        partial-final-over display (an innings which ended mid-over). Under the
        engine convention: overs_completed counts ONLY fully completed overs and
        legal_balls_in_over records balls of the partial final over (e.g. an
        innings chasing 352 that reached its target with 2 legal balls of the
        49th over reconciles as overs=48, legal_balls_in_over=2, display 48.2).
        
        Raises:
            ReconciliationError: If calculated values do not match expected scorecard totals.
        """
        snapshot = self.reconstruct_completed_innings(innings_index)

        if snapshot.runs != expected_runs:
            raise ReconciliationError(
                f"Innings {innings_index} run reconciliation failed. "
                f"Calculated: {snapshot.runs}, Expected: {expected_runs}.",
                context={
                    "calculated_runs": snapshot.runs,
                    "expected_runs": expected_runs,
                    "innings_index": innings_index,
                },
            )

        if snapshot.wickets != expected_wickets:
            raise ReconciliationError(
                f"Innings {innings_index} wicket reconciliation failed. "
                f"Calculated: {snapshot.wickets}, Expected: {expected_wickets}.",
                context={
                    "calculated_wickets": snapshot.wickets,
                    "expected_wickets": expected_wickets,
                    "innings_index": innings_index,
                },
            )

        if expected_overs is not None and snapshot.overs_completed != expected_overs:
            raise ReconciliationError(
                f"Innings {innings_index} overs reconciliation failed. "
                f"Calculated: {snapshot.overs_completed}, Expected: {expected_overs}.",
                context={
                    "calculated_overs": snapshot.overs_completed,
                    "expected_overs": expected_overs,
                    "innings_index": innings_index,
                },
            )

        if (
            expected_legal_balls_in_over is not None
            and snapshot.legal_balls_in_over != expected_legal_balls_in_over
        ):
            raise ReconciliationError(
                f"Innings {innings_index} partial-over reconciliation failed. "
                f"Calculated: {snapshot.legal_balls_in_over} legal balls in final over, "
                f"Expected: {expected_legal_balls_in_over}.",
                context={
                    "calculated_legal_balls_in_over": snapshot.legal_balls_in_over,
                    "expected_legal_balls_in_over": expected_legal_balls_in_over,
                    "innings_index": innings_index,
                },
            )

        return True
