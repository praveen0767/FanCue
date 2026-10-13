"""Evidence packet builder enriching match engine outputs with contextual knowledge."""

from typing import List, Optional

from backend.app.match_engine.cricket import CricketMatchEngine
from backend.app.schemas.common import LanguageCode, SportType
from backend.app.schemas.cricket import CricketCatchUpRequest
from backend.app.schemas.evidence import EvidenceFact, FactType, MatchEvidencePacket
from backend.app.schemas.retrieval import RetrievalQuery, RetrievalStatus, RetrievedPassage
from ingestion.knowledge.retrieve import RetrievalService


class EvidencePacketBuilder:
    """Builds and enriches canonical MatchEvidencePacket for catch-up requests."""

    def __init__(
        self,
        engine: CricketMatchEngine,
        retrieval_service: Optional[RetrievalService] = None,
    ) -> None:
        self.engine = engine
        self.retrieval_service = retrieval_service

    def build_packet(
        self,
        request: CricketCatchUpRequest,
    ) -> MatchEvidencePacket:
        """Construct full immutable evidence packet with engine facts and contextual passages."""
        # 1. Reconstruct deterministic match interval from engine
        state_before, state_after, delta, key_facts, base_packet = self.engine.reconstruct_interval(request)

        # 2. Ensure the canonical interval state delta fact is present.
        # The engine now emits this STATE_MILESTONE fact itself, so we only
        # build it here when working with an older engine packet that lacks it.
        delta_fact_id = f"fact_{self.engine.match_id}_inn{request.interval.innings}_delta_{request.interval.start_after_over}_{request.interval.end_after_over}"
        delta_fact = None if any(
            f.fact_id == delta_fact_id for f in base_packet.key_facts
        ) else EvidenceFact(
            fact_id=delta_fact_id,
            fact_type=FactType.STATE_MILESTONE,
            match_id=self.engine.match_id,
            source_revision=self.engine.provenance.dataset_revision,
            referenced_event_ids=[f"state_delta_{request.interval.start_after_over}_{request.interval.end_after_over}"],
            description=(
                f"Interval progression: {delta.runs_added} runs scored, {delta.wickets_lost} wickets fallen "
                f"in {delta.completed_overs_delta} completed overs (run rate: {delta.interval_run_rate:.2f} rpo)."
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

        all_facts: List[EvidenceFact] = list(base_packet.key_facts)
        if delta_fact is not None:
            all_facts = [delta_fact] + all_facts

        # 3. Retrieve eligible background knowledge passages if service available
        retrieved_passages: List[RetrievedPassage] = []
        retrieved_ids: List[str] = []

        if self.retrieval_service is not None:
            context_queries = self._determine_context_queries(delta, all_facts)
            for q_text in context_queries:
                q = RetrievalQuery(
                    query_text=q_text,
                    sport=SportType.CRICKET,
                    language=request.language,
                    limit=2,
                )
                res = self.retrieval_service.retrieve(q)
                if res.status == RetrievalStatus.SUCCESS:
                    for passage in res.passages:
                        if passage.doc_id not in retrieved_ids:
                            retrieved_ids.append(passage.doc_id)
                            retrieved_passages.append(passage)

        # Cap retrieved passages to small token-bounded set (max 3 passages)
        final_passages = retrieved_passages[:3]
        final_ids = [p.doc_id for p in final_passages]

        # 4. Construct enriched MatchEvidencePacket
        return MatchEvidencePacket(
            packet_id=base_packet.packet_id,
            match_id=base_packet.match_id,
            sport=base_packet.sport,
            interval_summary=base_packet.interval_summary,
            state_before=state_before,
            state_after=state_after,
            state_delta=delta,
            key_facts=all_facts,
            retrieved_knowledge_ids=final_ids,
            retrieved_passages=final_passages,
            provenance=base_packet.provenance,
        )

    def _determine_context_queries(
        self,
        delta,
        facts: List[EvidenceFact],
    ) -> List[str]:
        """Construct targeted queries based on actual interval events."""
        queries: List[str] = []

        # Wickets occurred
        if delta.wickets_lost > 0:
            queries.append("Why do wickets disrupt batting tempo and scoring rates?")
            queries.append("Difference between a batter dismissal and bowler wicket")

        # Runs scored with 0 wickets (strong partnership)
        if delta.runs_added >= 30 and delta.wickets_lost == 0:
            queries.append("How does an enduring partnership stabilize an innings and build pressure?")

        # Extras conceded
        if delta.extras_added > 0:
            queries.append("Why do wides and no-balls require the bowler to re-bowl the delivery?")

        # Base interval delta query
        queries.append("What does a score-state delta tell a returning fan about an interval?")

        return queries[:2]
