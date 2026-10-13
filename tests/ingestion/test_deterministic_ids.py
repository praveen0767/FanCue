"""Tests for deterministic identifier generation and text normalization."""

from ingestion.knowledge.ids import (
    compute_sha256,
    generate_chunk_id,
    generate_doc_id,
    generate_point_uuid,
    normalize_text_canonical,
)


def test_normalize_text_canonical_whitespace_and_newlines():
    raw = "  Line 1  \r\n\r\n\r\nLine 2 \r\n   "
    normalized = normalize_text_canonical(raw)
    assert normalized == "Line 1\n\nLine 2"


def test_compute_sha256_stability():
    t1 = "Deterministic cricket body text."
    t2 = "Deterministic cricket body text."
    h1 = compute_sha256(t1)
    h2 = compute_sha256(t2)
    assert h1 == h2
    assert len(h1) == 64


def test_generate_doc_id_deterministic():
    logical_id = "over_concept"
    sha = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    doc_id_1 = generate_doc_id(logical_id, sha)
    doc_id_2 = generate_doc_id(logical_id, sha)
    assert doc_id_1 == doc_id_2
    assert doc_id_1 == "doc_over_concept_e3b0c44298fc"


def test_generate_chunk_id_deterministic():
    doc_id = "doc_over_concept_e3b0c44298fc"
    chunk_sha = "abcdef0123456789"
    cid1 = generate_chunk_id(doc_id, 0, chunk_sha)
    cid2 = generate_chunk_id(doc_id, 0, chunk_sha)
    assert cid1 == cid2
    assert cid1 == "doc_over_concept_e3b0c44298fc_c0_abcdef01"


def test_generate_point_uuid_deterministic():
    model = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    chunk_id = "doc_over_concept_e3b0c44298fc_c0_abcdef01"
    uuid1 = generate_point_uuid(model, chunk_id)
    uuid2 = generate_point_uuid(model, chunk_id)
    assert uuid1 == uuid2
    assert len(uuid1) == 36


def test_text_changes_produce_distinct_ids():
    text_a = "Original version of text."
    text_b = "Updated version of text with new facts."
    sha_a = compute_sha256(text_a)
    sha_b = compute_sha256(text_b)
    assert sha_a != sha_b

    doc_a = generate_doc_id("concept", sha_a)
    doc_b = generate_doc_id("concept", sha_b)
    assert doc_a != doc_b
