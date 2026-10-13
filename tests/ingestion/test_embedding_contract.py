"""Tests for EmbeddingProvider contract and FastEmbed implementation."""

import math
import pytest

from ingestion.knowledge.embeddings import (
    EmbeddingProviderError,
    FastEmbedProvider,
    PINNED_EMBEDDING_DIMENSIONS,
    PINNED_EMBEDDING_MODEL,
    PINNED_EMBEDDING_REVISION,
)


def test_embedding_constants_and_properties():
    embedder = FastEmbedProvider()
    assert embedder.provider_name == "fastembed"
    assert embedder.model_id == PINNED_EMBEDDING_MODEL
    assert embedder.model_revision == PINNED_EMBEDDING_REVISION
    assert embedder.dimensions == PINNED_EMBEDDING_DIMENSIONS
    assert embedder.dimensions == 384
    assert embedder.max_tokens == 128


def test_embed_texts_produces_finite_vectors():
    embedder = FastEmbedProvider()
    texts = [
        "First cricket delivery.",
        "Second delivery with a boundary four.",
    ]
    vecs = embedder.embed_texts(texts)
    assert len(vecs) == 2
    for v in vecs:
        assert len(v) == 384
        for val in v:
            assert isinstance(val, float)
            assert math.isfinite(val)


def test_embed_empty_batch():
    embedder = FastEmbedProvider()
    vecs = embedder.embed_texts([])
    assert vecs == []


def test_embed_query_empty_raises_error():
    embedder = FastEmbedProvider()
    with pytest.raises(EmbeddingProviderError, match="cannot be empty"):
        embedder.embed_query("   ")


def test_count_tokens():
    embedder = FastEmbedProvider()
    count = embedder.count_tokens("The bowler delivers a yorker.")
    assert isinstance(count, int)
    assert count > 0
