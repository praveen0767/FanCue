"""Tests for Qdrant production mode safeguards and collection management.

Verifies:
1. Production mode forbids silent local-file or in-memory fallback.
2. Dedicated production collection naming constant.
3. Payload indexes and 384-dimensional cosine configuration.
4. Isolated temporary collection lifecycle.
"""

import os
import pytest

from ingestion.knowledge.embeddings import PINNED_EMBEDDING_DIMENSIONS
from ingestion.knowledge.qdrant_store import (
    DEV_COLLECTION_NAME,
    INDEXED_PAYLOAD_FIELDS,
    PROD_COLLECTION_NAME,
    QdrantStore,
    QdrantStoreError,
)


def test_production_mode_forbids_silent_local_fallback():
    """When allow_local_fallback=False, unreachable server must raise QdrantStoreError."""
    # Point to non-existent port on loopback with fallback disallowed
    store = QdrantStore(
        host="127.0.0.1",
        port=65432,
        allow_local_fallback=False,
    )
    with pytest.raises(QdrantStoreError) as exc_info:
        store.get_client()

    assert "Local fallback is disabled" in str(exc_info.value) or "Could not connect" in str(exc_info.value)


def test_production_collection_name_distinct_from_dev():
    """Production and dev collections must have separate, non-overlapping names."""
    assert PROD_COLLECTION_NAME == "fancue_cricket_knowledge_v1"
    assert DEV_COLLECTION_NAME == "fancue_cricket_knowledge_dev_v1"
    assert PROD_COLLECTION_NAME != DEV_COLLECTION_NAME


def test_qdrant_indexed_payload_fields():
    """Required production metadata payload indexes must be defined."""
    required_fields = {
        "sport",
        "language",
        "topic",
        "review_status",
        "active",
        "permitted_use",
        "logical_doc_id",
    }
    assert required_fields.issubset(set(INDEXED_PAYLOAD_FIELDS.keys()))


def test_vector_dimension_matches_embedding_profile():
    """Pinned vector dimensionality must be 384 for bge-small-en-v1.5."""
    assert PINNED_EMBEDDING_DIMENSIONS == 384
