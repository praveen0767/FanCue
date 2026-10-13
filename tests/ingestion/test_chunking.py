"""Tests for semantic markdown chunking and token limits."""

import pytest

from backend.app.schemas.common import LanguageCode, SportType
from backend.app.schemas.knowledge import (
    KnowledgeDocumentFrontmatter,
    KnowledgeSourceType,
    KnowledgeType,
    ReviewStatus,
    SourceCheckStatus,
)
from backend.app.schemas.provenance import PermittedUse
from ingestion.knowledge.chunker import (
    ChunkerError,
    MAX_CHUNK_TOKENS,
    chunk_document,
    extract_headings_and_paragraphs,
)
from ingestion.knowledge.embeddings import FastEmbedProvider
from ingestion.knowledge.loader import RawKnowledgeDocument


def make_doc_with_body(body: str) -> RawKnowledgeDocument:
    fm = KnowledgeDocumentFrontmatter(
        id="chunk_test_doc",
        title="Chunk Test",
        sport=SportType.CRICKET,
        language=LanguageCode.EN,
        topic="cricket_terminology",
        knowledge_type=KnowledgeType.TERMINOLOGY,
        review_status=ReviewStatus.APPROVED,
        source_type=KnowledgeSourceType.FANCUE_AUTHORED,
        source_name="FanCue",
        source_url="https://fancue.org",
        source_revision="1.0.0",
        license="CC-BY-4.0",
        permitted_use=PermittedUse.OPEN_ATTRIBUTION,
        source_check_status=SourceCheckStatus.VERIFIED,
        document_revision="1.0.0",
    )
    return RawKnowledgeDocument(
        filepath="ingestion/knowledge/approved/test.md",
        frontmatter=fm,
        body=body,
        is_draft=False,
    )


def test_extract_headings_and_paragraphs():
    body = "# Section One\n\nParagraph one.\n\n## Section Two\n\nParagraph two."
    sections = extract_headings_and_paragraphs(body)
    assert len(sections) == 2
    assert sections[0][0] == "Section One"
    assert sections[0][1] == "Paragraph one."
    assert sections[1][0] == "Section Two"
    assert sections[1][1] == "Paragraph two."


def test_chunk_document_respects_token_budget():
    embedder = FastEmbedProvider()
    body = (
        "# Overview\n\n"
        "An over consists of six legal deliveries bowled from one end of the pitch.\n\n"
        "Illegal deliveries such as wides and no-balls do not count toward this total.\n\n"
        "# Strategy\n\n"
        "Bowlers must adapt their lengths based on fielding conditions and pitch characteristics."
    )
    doc = make_doc_with_body(body)
    chunks = chunk_document(doc, embedder=embedder)

    assert len(chunks) >= 1
    for c in chunks:
        assert c.token_count <= MAX_CHUNK_TOKENS
        assert c.payload.section_title in ("Overview", "Strategy")
        assert c.payload.doc_id.startswith("doc_chunk_test_doc_")


def test_chunk_document_raises_on_enormous_single_paragraph():
    embedder = FastEmbedProvider()
    # A single paragraph with hundreds of words
    huge_paragraph = "word " * 500
    doc = make_doc_with_body(huge_paragraph)
    with pytest.raises(ChunkerError, match="exceeds maximum token limit"):
        chunk_document(doc, embedder=embedder)
