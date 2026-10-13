"""End-to-end orchestration service for cricket match interval catch-up."""

from datetime import datetime, timezone
import os
import time
from typing import Dict, List, Optional

from backend.app.ai.prompt_templates import SYSTEM_PROMPT, build_explanation_prompt
from backend.app.ai.provider import (
    DeterministicFakeProvider,
    LLMProvider,
    LLMTimeoutError,
    LLMUnavailableError,
)
from backend.app.explanations.deterministic_fallback import build_deterministic_fallback
from backend.app.match_engine.cricket import CricketMatchEngine
from backend.app.orchestration.evidence_builder import EvidencePacketBuilder
from backend.app.schemas.common import MatchMode
from backend.app.schemas.cricket import CricketCatchUpRequest
from backend.app.schemas.explanation import (
    CricketCatchUpResponse,
    ExplanationPayload,
    FallbackReason,
    GenerationMode,
    VerificationStatus,
)
from backend.app.verification.claim_verifier import ClaimVerifier
from ingestion.knowledge.retrieve import RetrievalService


class CricketCatchUpOrchestrator:
    """Orchestrates interval reconstruction, context retrieval, AI generation, and verification."""

    def __init__(
        self,
        engine: CricketMatchEngine,
        retrieval_service: Optional[RetrievalService] = None,
        llm_provider: Optional[LLMProvider] = None,
        verifier: Optional[ClaimVerifier] = None,
        skip_llm: Optional[bool] = None,
    ) -> None:
        self.engine = engine
        self.evidence_builder = EvidencePacketBuilder(engine, retrieval_service=retrieval_service)
        self.llm_provider = llm_provider or DeterministicFakeProvider()
        self.verifier = verifier or ClaimVerifier()
        # Honor explicit parameter first, fall back to environment variable
        if skip_llm is not None:
            self.skip_llm = skip_llm
        else:
            self.skip_llm = os.environ.get("SKIP_LLM_IN_TESTS", "false").lower() in ("true", "1")

    def catch_up(
        self,
        request: CricketCatchUpRequest,
    ) -> CricketCatchUpResponse:
        """Process catch-up request through the bounded verification lifecycle."""
        t_start = time.perf_counter()
        warnings: List[str] = []

        # 1. Assemble and enrich canonical evidence packet
        packet = self.evidence_builder.build_packet(request)

        # 2. Decide whether to execute LLM or jump straight to deterministic fallback
        explanation_payload: Optional[ExplanationPayload] = None

        if self.skip_llm:
            explanation_payload = build_deterministic_fallback(
                packet,
                fallback_reason=FallbackReason.DISABLED,
            )
            warnings.append("LLM generation skipped by configuration; deterministic fallback engaged.")
        else:
            try:
                # 3. Generate structured draft via provider
                prompt = build_explanation_prompt(packet)
                draft = self.llm_provider.generate_explanation(
                    prompt=prompt,
                    system_prompt=SYSTEM_PROMPT,
                    timeout_seconds=30.0,
                )

                # 4. Deterministic Claim Verification
                verification_report = self.verifier.verify(draft, packet)

                if verification_report.is_verified:
                    explanation_payload = ExplanationPayload(
                        summary=draft.summary,
                        claims=verification_report.verified_claims,
                        generation_mode=GenerationMode.LLM_VERIFIED,
                        verification_status=VerificationStatus.VERIFIED,
                        fallback_reason=FallbackReason.NONE,
                    )
                else:
                    # Verification failed: suppress hallucinated claims and engage fallback
                    primary_rejection = (
                        verification_report.rejected_claims[0].reason.value
                        if verification_report.rejected_claims
                        else "unsupported_claims"
                    )
                    reason = (
                        FallbackReason.FACT_MISMATCH
                        if "mismatch" in primary_rejection
                        else FallbackReason.UNSUPPORTED_CLAIMS
                    )
                    explanation_payload = build_deterministic_fallback(
                        packet,
                        fallback_reason=reason,
                    )
                    warnings.append(
                        f"AI claims failed deterministic verification ({primary_rejection}); "
                        f"engaged deterministic fallback."
                    )

            except LLMTimeoutError as e:
                explanation_payload = build_deterministic_fallback(
                    packet,
                    fallback_reason=FallbackReason.TIMEOUT,
                )
                warnings.append(f"LLM call timed out: {e}")
            except (LLMUnavailableError, Exception) as e:
                explanation_payload = build_deterministic_fallback(
                    packet,
                    fallback_reason=FallbackReason.LLM_ERROR,
                )
                # Sanitized: only the exception TYPE is recorded. Provider error
                # messages may embed configuration or prompt material, so the
                # raw message never enters the response's warnings.
                warnings.append(
                    f"LLM call failed or provider unavailable ({type(e).__name__}); "
                    f"deterministic fallback engaged."
                )

        # 5. Assemble final canonical response
        state_before = packet.state_before
        state_after = packet.state_after
        delta = packet.state_delta

        return CricketCatchUpResponse(
            match=self.engine.match_descriptor,
            interval=request.interval,
            state_before=state_before,
            state_after=state_after,
            state_delta=delta,
            evidence_packet=packet,
            explanation=explanation_payload,
            language=request.language,
            mode=MatchMode.REPLAY,
            generated_at=datetime.now(timezone.utc),
            warnings=warnings,
        )
