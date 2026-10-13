"""Golden test suite reconciling real Cricsheet fixtures against independent scorecards."""

from datetime import datetime, timezone
import os
import pytest

from backend.app.match_engine.cricket import CricketMatchEngine
from backend.app.match_engine.errors import (
    InningsIndexOutOfBoundsError,
    OverBoundaryNotFoundError,
    ReconciliationError,
)
from backend.app.schemas.cricket import (
    CricketCatchUpRequest,
    CricketInterval,
)
from backend.app.schemas.provenance import (
    PermittedUse,
    SourceProvenance,
)

FIXTURE_1529229 = os.path.abspath("data/raw/1529229.json")
SHA256_1529229 = "8163493c726d43e0865b6041c06bfa85f764d908e337d510108cdcf36e66c12f"

FIXTURE_1552779 = os.path.abspath("data/raw/1552779.json")
SHA256_1552779 = "99b2df4d4ebcaa328834ec101776a201c679b5d89b1a604241c504b0d9bb3e2b"


@pytest.fixture
def provenance_1529229():
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


@pytest.fixture
def provenance_1552779():
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


def test_reconcile_fixture_1529229_odi(provenance_1529229):
    """Reconcile Match 1529229 (India vs West Indies ODI) against official scorecard totals.
    
    Scorecard Ground Truth:
    - Innings 0 (India): 351/7 in 50.0 overs
    - Innings 1 (West Indies): 352/5 in 49.0 overs
    """
    engine = CricketMatchEngine.from_fixture(
        file_path=FIXTURE_1529229,
        match_id="1529229",
        provenance=provenance_1529229,
        expected_sha256=SHA256_1529229,
    )

    # Innings 0 reconciliation
    assert engine.reconcile_innings(
        innings_index=0,
        expected_runs=351,
        expected_wickets=7,
        expected_overs=50,
    )

    # Innings 1 reconciliation
    # The chase ended at over index 48 (0-based), 2 legal balls into that over
    # → engine correctly reports overs_completed=48, legal_balls_in_over=2 (48.2)
    assert engine.reconcile_innings(
        innings_index=1,
        expected_runs=352,
        expected_wickets=5,
        expected_overs=48,
        expected_legal_balls_in_over=2,
    )


def test_reconcile_fixture_1552779_t20(provenance_1552779):
    """Reconcile Match 1552779 (India vs Pakistan T20 Final) against official scorecard totals.
    
    Scorecard Ground Truth:
    - Innings 0 (India): 211/6 in 20.0 overs
    - Innings 1 (Pakistan): 192/6 in 20.0 overs
    """
    engine = CricketMatchEngine.from_fixture(
        file_path=FIXTURE_1552779,
        match_id="1552779",
        provenance=provenance_1552779,
        expected_sha256=SHA256_1552779,
    )

    # Innings 0 reconciliation
    assert engine.reconcile_innings(
        innings_index=0,
        expected_runs=211,
        expected_wickets=6,
        expected_overs=20,
    )

    # Innings 1 reconciliation
    assert engine.reconcile_innings(
        innings_index=1,
        expected_runs=192,
        expected_wickets=6,
        expected_overs=20,
    )


def test_scenario_a_interval_reconstruction_match_1529229(provenance_1529229):
    """Test Scenario A interval: India innings 0, overs 15 to 22.
    
    Start boundary: after over 14 (human: after 15 overs completed) -> India 59/2
    End boundary: after over 21 (human: after 22 overs completed) -> India 124/2
    Interval delta: +65 runs, 0 wickets lost, 42 legal balls (7 completed overs).
    """
    engine = CricketMatchEngine.from_fixture(
        file_path=FIXTURE_1529229,
        match_id="1529229",
        provenance=provenance_1529229,
    )
    request = CricketCatchUpRequest(
        match_id="1529229",
        interval=CricketInterval(innings=0, start_after_over=14, end_after_over=21),
    )
    state_before, state_after, delta, facts, packet = engine.reconstruct_interval(request)

    # Start boundary: end of over 14 (15 completed overs)
    assert state_before.runs == 59
    assert state_before.wickets == 2
    assert state_before.overs_completed == 15

    # End boundary: end of over 21 (22 completed overs)
    assert state_after.runs == 124
    assert state_after.wickets == 2
    assert state_after.overs_completed == 22

    # Delta: overs 15 to 22 (7 overs)
    assert delta.runs_added == 65
    assert delta.wickets_lost == 0
    assert delta.completed_overs_delta == 7
    assert delta.legal_balls_added == 42
    assert delta.interval_run_rate == round(65 / 7, 2)

    # Evidence packet
    assert packet.packet_id == "pkt_1529229_inn0_14_21"
    assert packet.state_delta.runs_added == 65


def test_reconciliation_failure_raises_reconciliation_error(provenance_1529229):
    """Asserting wrong expected scores raises ReconciliationError."""
    engine = CricketMatchEngine.from_fixture(
        file_path=FIXTURE_1529229,
        match_id="1529229",
        provenance=provenance_1529229,
    )
    with pytest.raises(ReconciliationError) as exc:
        engine.reconcile_innings(innings_index=0, expected_runs=999, expected_wickets=7)
    assert "run reconciliation failed" in str(exc.value)

    with pytest.raises(ReconciliationError) as exc:
        engine.reconcile_innings(innings_index=0, expected_runs=351, expected_wickets=9)
    assert "wicket reconciliation failed" in str(exc.value)

    with pytest.raises(ReconciliationError) as exc:
        engine.reconcile_innings(innings_index=0, expected_runs=351, expected_wickets=7, expected_overs=20)
    assert "overs reconciliation failed" in str(exc.value)


def test_boundary_out_of_bounds_raises_error(provenance_1529229):
    """Requesting boundary exceeding match progression raises OverBoundaryNotFoundError."""
    engine = CricketMatchEngine.from_fixture(
        file_path=FIXTURE_1529229,
        match_id="1529229",
        provenance=provenance_1529229,
    )
    request = CricketCatchUpRequest(
        match_id="1529229",
        interval=CricketInterval(innings=0, start_after_over=0, end_after_over=99),
    )
    with pytest.raises(OverBoundaryNotFoundError):
        engine.reconstruct_interval(request)


def test_innings_out_of_bounds_raises_error(provenance_1529229):
    """Requesting non-existent innings index raises InningsIndexOutOfBoundsError."""
    engine = CricketMatchEngine.from_fixture(
        file_path=FIXTURE_1529229,
        match_id="1529229",
        provenance=provenance_1529229,
    )
    with pytest.raises(InningsIndexOutOfBoundsError):
        engine.get_innings_events(innings_index=5)


def test_engine_descriptor_and_sentinel_boundary(provenance_1529229):
    """Verify get_match_descriptor and sentinel boundary validation."""
    engine = CricketMatchEngine.from_fixture(
        file_path=FIXTURE_1529229,
        match_id="1529229",
        provenance=provenance_1529229,
    )
    desc = engine.get_match_descriptor()
    assert desc.match_id == "1529229"

    # Sentinel boundary -1 should validate without error
    engine.validate_boundary_availability(innings_index=0, boundary=-1)


def test_engine_empty_innings_handling(provenance_1529229):
    """Verify engine handling of an empty innings."""
    raw_mock = {
        "meta": {"data_version": "1.3.0"},
        "info": {"teams": ["Team A", "Team B"], "dates": ["2026-10-01"]},
        "innings": [{"team": "Team A", "overs": []}],
    }
    engine = CricketMatchEngine(raw_mock, "mock_1", provenance_1529229)
    snap = engine.reconstruct_completed_innings(0)
    assert snap.runs == 0
    assert snap.overs_completed == 0

    with pytest.raises(OverBoundaryNotFoundError):
        engine.validate_boundary_availability(0, boundary=5)

