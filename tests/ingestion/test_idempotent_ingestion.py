"""Tests verifying ingestion repeatability, point count idempotency, and dry-run safety."""

from ingestion.knowledge.embeddings import FastEmbedProvider
from ingestion.knowledge.ingest import run_ingestion
from ingestion.knowledge.qdrant_store import QdrantStore


def test_dry_run_makes_zero_writes():
    store = QdrantStore(location=":memory:")
    embedder = FastEmbedProvider()

    test_collection = "test_dry_run_collection"

    report = run_ingestion(
        target_collection=test_collection,
        dry_run=True,
        allow_draft=False,
        embedder=embedder,
        store=store,
    )

    assert report.is_dry_run is True
    assert report.execution_status == "dry_run_success"
    assert report.documents_accepted == 23
    assert report.chunks_generated > 0
    assert report.points_upserted == 0

    # Ensure collection was never created or populated in store
    collections = [c.name for c in store.get_client().get_collections().collections]
    assert test_collection not in collections


def test_idempotent_repeated_ingestion():
    store = QdrantStore(location=":memory:")
    embedder = FastEmbedProvider()

    test_collection = "test_idempotent_collection"

    # Run 1: Apply
    report_1 = run_ingestion(
        target_collection=test_collection,
        dry_run=False,
        allow_draft=False,
        embedder=embedder,
        store=store,
    )
    assert report_1.execution_status == "applied_success"
    initial_points = report_1.points_upserted
    assert initial_points > 0
    assert store.count_points(test_collection) == initial_points

    # Run 2: Apply identical corpus again
    report_2 = run_ingestion(
        target_collection=test_collection,
        dry_run=False,
        allow_draft=False,
        embedder=embedder,
        store=store,
    )
    assert report_2.execution_status == "applied_success"
    assert report_2.points_upserted == initial_points
    # Point count MUST NOT GROW
    final_points = store.count_points(test_collection)
    assert final_points == initial_points
