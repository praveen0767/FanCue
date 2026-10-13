"""Tests for retrieval filtering: sport isolation, language boundaries, and review status."""

import pytest

from backend.app.schemas.common import LanguageCode, SportType
from backend.app.schemas.retrieval import RetrievalQuery, RetrievalStatus
from ingestion.knowledge.embeddings import FastEmbedProvider
from ingestion.knowledge.ingest import run_ingestion
from ingestion.knowledge.qdrant_store import QdrantStore
from ingestion.knowledge.retrieve import RetrievalService


@pytest.fixture(scope="module")
def seeded_store():
    store = QdrantStore(location=":memory:")
    embedder = FastEmbedProvider()
    coll = "test_filter_collection"

    # Ingest both approved and draft documents into test collection
    run_ingestion(
        target_collection=coll,
        dry_run=False,
        allow_draft=True,
        embedder=embedder,
        store=store,
    )
    return store, embedder, coll


def test_cricket_query_returns_cricket_only(seeded_store):
    store, embedder, coll = seeded_store
    service = RetrievalService(collection_name=coll, embedder=embedder, store=store, allow_draft=True)

    query = RetrievalQuery(
        query_text="What is an over in cricket?",
        sport=SportType.CRICKET,
        language=LanguageCode.EN,
        limit=3,
    )
    result = service.retrieve(query)
    assert result.status == RetrievalStatus.SUCCESS
    assert len(result.passages) > 0
    for p in result.passages:
        assert p.sport == SportType.CRICKET


def test_football_query_returns_no_cross_sport_leakage(seeded_store):
    store, embedder, coll = seeded_store
    service = RetrievalService(collection_name=coll, embedder=embedder, store=store, allow_draft=True)

    query = RetrievalQuery(
        query_text="What is an offside in football?",
        sport=SportType.FOOTBALL,
        language=LanguageCode.EN,
        limit=3,
    )
    result = service.retrieve(query)
    # Must return FILTER_EMPTY because only cricket content is indexed
    assert result.status in (RetrievalStatus.FILTER_EMPTY, RetrievalStatus.EMPTY_RESULT)
    assert len(result.passages) == 0


def test_draft_excluded_when_allow_draft_is_false(seeded_store):
    store, embedder, coll = seeded_store
    # Service configured WITHOUT draft access
    service = RetrievalService(collection_name=coll, embedder=embedder, store=store, allow_draft=False)

    query = RetrievalQuery(
        query_text="Super over tie break rules",
        sport=SportType.CRICKET,
        language=LanguageCode.EN,
        limit=5,
    )
    result = service.retrieve(query)
    for p in result.passages:
        # None of the returned passages may be from draft super over note
        assert "super_over_tiebreaker" not in p.doc_id


def test_tamil_draft_retrievable_when_allowed(seeded_store):
    store, embedder, coll = seeded_store
    service = RetrievalService(collection_name=coll, embedder=embedder, store=store, allow_draft=True)

    query = RetrievalQuery(
        query_text="கிரிக்கெட் இன்னிங்ஸ் மற்றும் ஓவர் விளக்கம்",
        sport=SportType.CRICKET,
        language=LanguageCode.TA,
        limit=3,
    )
    result = service.retrieve(query)
    assert result.status == RetrievalStatus.SUCCESS
    assert len(result.passages) > 0
    assert result.passages[0].language == LanguageCode.TA
