"""Evaluation test asserting Phase 04 quality gates on the fixed retrieval dataset."""

import pytest

from ingestion.knowledge.embeddings import FastEmbedProvider
from ingestion.knowledge.evaluate import evaluate_retrieval
from ingestion.knowledge.ingest import run_ingestion
from ingestion.knowledge.qdrant_store import QdrantStore
from ingestion.knowledge.retrieve import RetrievalService


@pytest.fixture(scope="module")
def eval_service():
    store = QdrantStore(location=":memory:")
    embedder = FastEmbedProvider()
    coll = "test_eval_collection"

    # Ingest approved corpus
    run_ingestion(
        target_collection=coll,
        dry_run=False,
        allow_draft=False,
        embedder=embedder,
        store=store,
    )
    return RetrievalService(
        collection_name=coll,
        embedder=embedder,
        store=store,
        allow_draft=False,
    )


def test_retrieval_quality_gates(eval_service):
    metrics = evaluate_retrieval(eval_service)

    # Acceptance Criteria Gates from Phase 04 prompt:
    # 1. At least 80% HitRate@3 on in-scope questions
    assert metrics["hit_rate_at_3"] >= 0.80, f"HitRate@3 was {metrics['hit_rate_at_3']}, expected >= 0.80"

    # 2. Zero cross-sport leakage
    assert metrics["wrong_sport_leakage"] == 0, "Wrong sport leakage must be 0"

    # 3. Zero wrong-language leakage
    assert metrics["wrong_language_leakage"] == 0, "Wrong language leakage must be 0"

    # 4. Zero draft leakage in production-eligible query path
    assert metrics["draft_leakage_count"] == 0, "Draft leakage count must be 0"

    # 5. Passed overall gate boolean
    assert metrics["passed_gate"] is True
