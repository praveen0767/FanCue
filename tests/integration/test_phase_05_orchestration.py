"""
Phase 05 Fixture-Backed Orchestration Integration Tests.

Exercises the complete pipeline (engine → evidence builder → fake LLM → verifier
→ fallback) using both real Cricsheet fixtures and at least two intervals each.

No external LLM or network calls are made.
JSON Schema validation is performed for each canonical response.
"""

import json
import os
from datetime import datetime, timezone

import jsonschema
import pytest

from backend.app.ai.models import AICandidateClaim, AIExplanationDraft
from backend.app.ai.provider import DeterministicFakeProvider, LLMUnavailableError
from backend.app.match_engine.cricket import CricketMatchEngine
from backend.app.orchestration.cricket_catchup import CricketCatchUpOrchestrator
from backend.app.schemas.cricket import CricketCatchUpRequest, CricketInterval
from backend.app.schemas.explanation import (
    ClaimType,
    FallbackReason,
    GenerationMode,
    VerificationStatus,
)
from backend.app.schemas.provenance import PermittedUse, SourceProvenance

# ─── Paths ───────────────────────────────────────────────────────────────────

FIXTURE_1529229 = os.path.abspath("data/raw/1529229.json")
SHA256_1529229 = "8163493c726d43e0865b6041c06bfa85f764d908e337d510108cdcf36e66c12f"

FIXTURE_1552779 = os.path.abspath("data/raw/1552779.json")
SHA256_1552779 = "99b2df4d4ebcaa328834ec101776a201c679b5d89b1a604241c504b0d9bb3e2b"

SCHEMA_PATH = os.path.abspath("contracts/cricket_catchup_response.schema.json")

# ─── Authoritative expected values (derived by running engine, confirmed in Phase 03) ─

# Match 1529229, Innings 0:
#   Interval 15-22 (start_after_over=14, end_after_over=21): +65r, 0w, 7ov — Phase 03 verified
#   Interval 30-35 (start_after_over=29, end_after_over=34): +44r, 0w, 5ov — probed in Phase 05
EXPECTED_1529229_INN0_14_21 = dict(before_runs=59, before_wickets=2, after_runs=124, after_wickets=2,
                                   delta_runs=65, delta_wickets=0, delta_overs=7)
EXPECTED_1529229_INN0_29_34 = dict(before_runs=172, before_wickets=4, after_runs=216, after_wickets=4,
                                   delta_runs=44, delta_wickets=0, delta_overs=5)

# Match 1552779, Innings 0:
#   Interval 5-10 (start_after_over=4, end_after_over=9):   +51r, 1w, 5ov — probed in Phase 05
#   Interval 12-18 (start_after_over=11, end_after_over=17): +48r, 2w, 6ov — probed in Phase 05
EXPECTED_1552779_INN0_4_9 = dict(before_runs=63, before_wickets=2, after_runs=114, after_wickets=3,
                                  delta_runs=51, delta_wickets=1, delta_overs=5)
EXPECTED_1552779_INN0_11_17 = dict(before_runs=124, before_wickets=3, after_runs=172, after_wickets=5,
                                   delta_runs=48, delta_wickets=2, delta_overs=6)


# ─── Schema fixture ──────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def response_schema():
    """Load the canonical JSON Schema for CricketCatchUpResponse."""
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def validate_against_schema(response, schema):
    """Serialize a Pydantic response and validate against the JSON Schema.

    Raises jsonschema.ValidationError if the response does not conform.
    """
    data = json.loads(response.model_dump_json())
    jsonschema.validate(instance=data, schema=schema)


# ─── Shared provenance fixtures ───────────────────────────────────────────────

@pytest.fixture(scope="module")
def prov_1529229():
    return SourceProvenance(
        source_id="cricsheet_historical_odi",
        source_name="Cricsheet",
        source_url="https://cricsheet.org/",
        retrieved_at=datetime.now(timezone.utc),
        dataset_revision="1",
        source_format="json",
        source_format_version="1.3.0",
        file_sha256=SHA256_1529229,
        license_name="ODC-By-1.0",
        license_url="http://opendatacommons.org/licenses/by/1.0/",
        attribution_text="Data provided by Cricsheet under ODC-By v1.0.",
        permitted_use=PermittedUse.OPEN_ATTRIBUTION,
    )


@pytest.fixture(scope="module")
def prov_1552779():
    return SourceProvenance(
        source_id="cricsheet_historical_t20",
        source_name="Cricsheet",
        source_url="https://cricsheet.org/",
        retrieved_at=datetime.now(timezone.utc),
        dataset_revision="1",
        source_format="json",
        source_format_version="1.3.0",
        file_sha256=SHA256_1552779,
        license_name="ODC-By-1.0",
        license_url="http://opendatacommons.org/licenses/by/1.0/",
        attribution_text="Data provided by Cricsheet under ODC-By v1.0.",
        permitted_use=PermittedUse.OPEN_ATTRIBUTION,
    )


@pytest.fixture(scope="module")
def engine_1529229(prov_1529229):
    return CricketMatchEngine.from_fixture(FIXTURE_1529229, "1529229", prov_1529229)


@pytest.fixture(scope="module")
def engine_1552779(prov_1552779):
    return CricketMatchEngine.from_fixture(FIXTURE_1552779, "1552779", prov_1552779)


# ─── Helper ──────────────────────────────────────────────────────────────────

def _assert_state(response, ex: dict):
    """Assert engine-authoritative state and delta against probed expected values."""
    assert response.state_before.runs == ex["before_runs"], \
        f"before.runs: {response.state_before.runs} != {ex['before_runs']}"
    assert response.state_before.wickets == ex["before_wickets"]
    assert response.state_after.runs == ex["after_runs"]
    assert response.state_after.wickets == ex["after_wickets"]
    assert response.state_delta.runs_added == ex["delta_runs"]
    assert response.state_delta.wickets_lost == ex["delta_wickets"]
    assert response.state_delta.completed_overs_delta == ex["delta_overs"]


def _assert_evidence_integrity(response, expected_match_id):
    """Assert the evidence packet is present, non-empty, and correctly scoped."""
    pkt = response.evidence_packet
    assert pkt is not None, "Evidence packet must be attached to every response"
    assert pkt.match_id == expected_match_id
    assert len(pkt.key_facts) > 0, "Evidence packet must contain at least the delta fact"
    # Packet state must equal response state (not mutated by provider)
    assert pkt.state_delta.runs_added == response.state_delta.runs_added
    assert pkt.state_before.runs == response.state_before.runs
    assert pkt.state_after.runs == response.state_after.runs


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURE 1529229 — ODI India vs West Indies
# ═══════════════════════════════════════════════════════════════════════════════


class TestFixture1529229:
    """Integration suite for match 1529229 (ODI)."""

    # ── Interval 1: overs 15-22 (start_after_over=14, end_after_over=21) ──

    def test_1529229_interval_14_21_valid_draft(self, engine_1529229, response_schema):
        """Valid AI draft: DeterministicFakeProvider returns well-grounded claims; verifier accepts them."""
        request = CricketCatchUpRequest(
            match_id="1529229",
            interval=CricketInterval(innings=0, start_after_over=14, end_after_over=21),
        )
        orchestrator = CricketCatchUpOrchestrator(
            engine=engine_1529229,
            retrieval_service=None,
            skip_llm=False,  # uses default DeterministicFakeProvider
        )
        response = orchestrator.catch_up(request)

        assert response.match.match_id == "1529229"
        assert response.interval.start_after_over == 14
        assert response.interval.end_after_over == 21

        _assert_state(response, EXPECTED_1529229_INN0_14_21)
        _assert_evidence_integrity(response, "1529229")

        assert response.explanation.generation_mode == GenerationMode.LLM_VERIFIED
        assert response.explanation.verification_status == VerificationStatus.VERIFIED
        assert len(response.explanation.claims) >= 1

        # Claims retain traceable fact references — none must have empty citations
        for claim in response.explanation.claims:
            assert len(claim.cited_fact_ids) > 0 or len(claim.cited_knowledge_ids) > 0, \
                f"Verified claim {claim.claim_id!r} must cite at least one fact or knowledge ID"

        validate_against_schema(response, response_schema)

    def test_1529229_interval_14_21_fabricated_draft_triggers_fallback(self, engine_1529229, response_schema):
        """Fabricated AI draft for interval 14-21: verifier rejects, fallback engaged."""
        request = CricketCatchUpRequest(
            match_id="1529229",
            interval=CricketInterval(innings=0, start_after_over=14, end_after_over=21),
        )
        fake_provider = DeterministicFakeProvider(
            preset_draft=AIExplanationDraft(
                summary="Fabricated summary claiming 300 runs.",
                claims=[
                    AICandidateClaim(
                        claim_id="claim_fab",
                        claim_type=ClaimType.SCORE_DELTA,
                        text="300 runs were added for 5 wickets in 7 overs.",
                        cited_fact_ids=["fact_NONEXISTENT"],
                        claimed_runs=300,
                        claimed_wickets=5,
                        claimed_overs=7,
                    )
                ],
            )
        )
        orchestrator = CricketCatchUpOrchestrator(
            engine=engine_1529229,
            retrieval_service=None,
            llm_provider=fake_provider,
            skip_llm=False,
        )
        response = orchestrator.catch_up(request)

        _assert_state(response, EXPECTED_1529229_INN0_14_21)
        assert response.explanation.generation_mode == GenerationMode.DETERMINISTIC_FALLBACK
        assert "300" not in response.explanation.summary
        validate_against_schema(response, response_schema)

    def test_1529229_interval_14_21_provider_failure(self, engine_1529229, response_schema):
        """Provider failure for interval 14-21: LLMUnavailableError → deterministic fallback."""
        request = CricketCatchUpRequest(
            match_id="1529229",
            interval=CricketInterval(innings=0, start_after_over=14, end_after_over=21),
        )
        fake_provider = DeterministicFakeProvider(
            simulate_error=LLMUnavailableError("Simulated unavailability"),
        )
        orchestrator = CricketCatchUpOrchestrator(
            engine=engine_1529229,
            retrieval_service=None,
            llm_provider=fake_provider,
            skip_llm=False,
        )
        response = orchestrator.catch_up(request)

        _assert_state(response, EXPECTED_1529229_INN0_14_21)
        assert response.explanation.generation_mode == GenerationMode.DETERMINISTIC_FALLBACK
        assert response.explanation.fallback_reason == FallbackReason.LLM_ERROR
        validate_against_schema(response, response_schema)

    def test_1529229_interval_14_21_skip_llm(self, engine_1529229, response_schema):
        """SKIP_LLM_IN_TESTS=true path for interval 14-21: deterministic fallback without LLM."""
        request = CricketCatchUpRequest(
            match_id="1529229",
            interval=CricketInterval(innings=0, start_after_over=14, end_after_over=21),
        )
        orchestrator = CricketCatchUpOrchestrator(
            engine=engine_1529229,
            retrieval_service=None,
            skip_llm=True,
        )
        response = orchestrator.catch_up(request)

        _assert_state(response, EXPECTED_1529229_INN0_14_21)
        _assert_evidence_integrity(response, "1529229")
        assert response.explanation.generation_mode == GenerationMode.DETERMINISTIC_FALLBACK
        assert response.explanation.fallback_reason == FallbackReason.DISABLED
        validate_against_schema(response, response_schema)

    # ── Interval 2: overs 30-35 (start_after_over=29, end_after_over=34) ──

    def test_1529229_interval_29_34_valid_draft(self, engine_1529229, response_schema):
        """Valid AI draft for interval 29-34: verifier accepts grounded claims."""
        request = CricketCatchUpRequest(
            match_id="1529229",
            interval=CricketInterval(innings=0, start_after_over=29, end_after_over=34),
        )
        orchestrator = CricketCatchUpOrchestrator(
            engine=engine_1529229,
            retrieval_service=None,
            skip_llm=False,
        )
        response = orchestrator.catch_up(request)

        assert response.match.match_id == "1529229"
        _assert_state(response, EXPECTED_1529229_INN0_29_34)
        _assert_evidence_integrity(response, "1529229")

        assert response.explanation.generation_mode == GenerationMode.LLM_VERIFIED
        validate_against_schema(response, response_schema)

    def test_1529229_interval_29_34_skip_llm(self, engine_1529229, response_schema):
        """SKIP_LLM path for interval 29-34: valid deterministic response."""
        request = CricketCatchUpRequest(
            match_id="1529229",
            interval=CricketInterval(innings=0, start_after_over=29, end_after_over=34),
        )
        orchestrator = CricketCatchUpOrchestrator(
            engine=engine_1529229,
            retrieval_service=None,
            skip_llm=True,
        )
        response = orchestrator.catch_up(request)

        _assert_state(response, EXPECTED_1529229_INN0_29_34)
        assert response.explanation.generation_mode == GenerationMode.DETERMINISTIC_FALLBACK
        validate_against_schema(response, response_schema)


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURE 1552779 — T20 India vs Pakistan Final
# ═══════════════════════════════════════════════════════════════════════════════


class TestFixture1552779:
    """Integration suite for match 1552779 (T20)."""

    # ── Interval 1: overs 5-10 (start_after_over=4, end_after_over=9) ──

    def test_1552779_interval_4_9_valid_draft(self, engine_1552779, response_schema):
        """Valid AI draft for T20 interval 4-9: claims verified, response schema-valid."""
        request = CricketCatchUpRequest(
            match_id="1552779",
            interval=CricketInterval(innings=0, start_after_over=4, end_after_over=9),
        )
        orchestrator = CricketCatchUpOrchestrator(
            engine=engine_1552779,
            retrieval_service=None,
            skip_llm=False,
        )
        response = orchestrator.catch_up(request)

        assert response.match.match_id == "1552779"
        _assert_state(response, EXPECTED_1552779_INN0_4_9)
        _assert_evidence_integrity(response, "1552779")

        assert response.explanation.generation_mode == GenerationMode.LLM_VERIFIED
        validate_against_schema(response, response_schema)

    def test_1552779_interval_4_9_fabricated_draft(self, engine_1552779, response_schema):
        """Fabricated draft for T20 interval 4-9: fallback engaged."""
        request = CricketCatchUpRequest(
            match_id="1552779",
            interval=CricketInterval(innings=0, start_after_over=4, end_after_over=9),
        )
        fake_provider = DeterministicFakeProvider(
            preset_draft=AIExplanationDraft(
                summary="Fabricated T20 claim.",
                claims=[
                    AICandidateClaim(
                        claim_id="claim_bad",
                        claim_type=ClaimType.SCORE_DELTA,
                        text="500 runs were added for 10 wickets.",
                        cited_fact_ids=["fact_GHOST"],
                        claimed_runs=500,
                        claimed_wickets=10,
                    )
                ],
            )
        )
        orchestrator = CricketCatchUpOrchestrator(
            engine=engine_1552779,
            retrieval_service=None,
            llm_provider=fake_provider,
            skip_llm=False,
        )
        response = orchestrator.catch_up(request)

        _assert_state(response, EXPECTED_1552779_INN0_4_9)
        assert response.explanation.generation_mode == GenerationMode.DETERMINISTIC_FALLBACK
        assert "500" not in response.explanation.summary
        validate_against_schema(response, response_schema)

    def test_1552779_interval_4_9_skip_llm(self, engine_1552779, response_schema):
        """SKIP_LLM path for T20 interval 4-9."""
        request = CricketCatchUpRequest(
            match_id="1552779",
            interval=CricketInterval(innings=0, start_after_over=4, end_after_over=9),
        )
        orchestrator = CricketCatchUpOrchestrator(
            engine=engine_1552779,
            retrieval_service=None,
            skip_llm=True,
        )
        response = orchestrator.catch_up(request)

        _assert_state(response, EXPECTED_1552779_INN0_4_9)
        assert response.explanation.generation_mode == GenerationMode.DETERMINISTIC_FALLBACK
        validate_against_schema(response, response_schema)

    # ── Interval 2: overs 12-18 (start_after_over=11, end_after_over=17) ──

    def test_1552779_interval_11_17_valid_draft(self, engine_1552779, response_schema):
        """Valid AI draft for T20 interval 11-17: engine authority preserved."""
        request = CricketCatchUpRequest(
            match_id="1552779",
            interval=CricketInterval(innings=0, start_after_over=11, end_after_over=17),
        )
        orchestrator = CricketCatchUpOrchestrator(
            engine=engine_1552779,
            retrieval_service=None,
            skip_llm=False,
        )
        response = orchestrator.catch_up(request)

        assert response.match.match_id == "1552779"
        _assert_state(response, EXPECTED_1552779_INN0_11_17)
        _assert_evidence_integrity(response, "1552779")

        assert response.explanation.generation_mode == GenerationMode.LLM_VERIFIED
        validate_against_schema(response, response_schema)

    def test_1552779_interval_11_17_provider_failure(self, engine_1552779, response_schema):
        """Provider failure for T20 interval 11-17: fallback with correct engine facts."""
        request = CricketCatchUpRequest(
            match_id="1552779",
            interval=CricketInterval(innings=0, start_after_over=11, end_after_over=17),
        )
        fake_provider = DeterministicFakeProvider(
            simulate_error=LLMUnavailableError("Provider down"),
        )
        orchestrator = CricketCatchUpOrchestrator(
            engine=engine_1552779,
            retrieval_service=None,
            llm_provider=fake_provider,
            skip_llm=False,
        )
        response = orchestrator.catch_up(request)

        _assert_state(response, EXPECTED_1552779_INN0_11_17)
        assert response.explanation.generation_mode == GenerationMode.DETERMINISTIC_FALLBACK
        assert response.explanation.fallback_reason == FallbackReason.LLM_ERROR
        validate_against_schema(response, response_schema)

    def test_1552779_interval_11_17_skip_llm(self, engine_1552779, response_schema):
        """SKIP_LLM path for T20 interval 11-17: engine authority + fallback labelling."""
        request = CricketCatchUpRequest(
            match_id="1552779",
            interval=CricketInterval(innings=0, start_after_over=11, end_after_over=17),
        )
        orchestrator = CricketCatchUpOrchestrator(
            engine=engine_1552779,
            retrieval_service=None,
            skip_llm=True,
        )
        response = orchestrator.catch_up(request)

        _assert_state(response, EXPECTED_1552779_INN0_11_17)
        assert response.explanation.generation_mode == GenerationMode.DETERMINISTIC_FALLBACK
        assert response.explanation.fallback_reason == FallbackReason.DISABLED
        validate_against_schema(response, response_schema)


# ═══════════════════════════════════════════════════════════════════════════════
# JSON Schema parity — standalone schema-validation tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestJsonSchemaParity:
    """Validate that both verified and fallback responses conform to the JSON Schema contract."""

    def test_schema_file_exists(self):
        """Verify the schema file exists and is valid JSON."""
        assert os.path.exists(SCHEMA_PATH), f"Schema file missing: {SCHEMA_PATH}"
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            schema = json.load(f)
        assert "$schema" in schema or "type" in schema or "properties" in schema

    def test_verified_response_validates_against_schema(self, engine_1529229, response_schema):
        """A successfully verified response must pass JSON Schema validation."""
        request = CricketCatchUpRequest(
            match_id="1529229",
            interval=CricketInterval(innings=0, start_after_over=14, end_after_over=21),
        )
        orchestrator = CricketCatchUpOrchestrator(
            engine=engine_1529229,
            retrieval_service=None,
            skip_llm=False,
        )
        response = orchestrator.catch_up(request)

        assert response.explanation.generation_mode == GenerationMode.LLM_VERIFIED
        validate_against_schema(response, response_schema)

    def test_fallback_response_validates_against_schema(self, engine_1529229, response_schema):
        """A deterministic fallback response must pass JSON Schema validation."""
        request = CricketCatchUpRequest(
            match_id="1529229",
            interval=CricketInterval(innings=0, start_after_over=14, end_after_over=21),
        )
        orchestrator = CricketCatchUpOrchestrator(
            engine=engine_1529229,
            retrieval_service=None,
            skip_llm=True,
        )
        response = orchestrator.catch_up(request)

        assert response.explanation.generation_mode == GenerationMode.DETERMINISTIC_FALLBACK
        validate_against_schema(response, response_schema)

    def test_rejected_claims_not_in_verified_output(self, engine_1529229, response_schema):
        """Rejected claim text must not appear inside schema-valid verified claims list."""
        request = CricketCatchUpRequest(
            match_id="1529229",
            interval=CricketInterval(innings=0, start_after_over=14, end_after_over=21),
        )
        fake_provider = DeterministicFakeProvider(
            preset_draft=AIExplanationDraft(
                summary="Fabricated claims mixed with nothing valid.",
                claims=[
                    AICandidateClaim(
                        claim_id="claim_reject_this",
                        claim_type=ClaimType.SCORE_DELTA,
                        text="REJECTED_CONTENT: 999 runs were added.",
                        cited_fact_ids=["fact_GHOST"],
                        claimed_runs=999,
                    )
                ],
            )
        )
        orchestrator = CricketCatchUpOrchestrator(
            engine=engine_1529229,
            retrieval_service=None,
            llm_provider=fake_provider,
            skip_llm=False,
        )
        response = orchestrator.catch_up(request)

        # Validate schema first
        validate_against_schema(response, response_schema)

        # Rejected content must not appear in the final claims
        all_claim_texts = [c.text for c in response.explanation.claims]
        assert not any("REJECTED_CONTENT" in t for t in all_claim_texts)
        assert not any("999" in t for t in all_claim_texts)
