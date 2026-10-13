"""Contract tests for knowledge document and chunk metadata schemas."""

import json
from pathlib import Path
import pytest
from pydantic import ValidationError

from backend.app.schemas.common import LanguageCode, SportType
from backend.app.schemas.knowledge import (
    KnowledgeChunk,
    KnowledgeChunkPayload,
    KnowledgeDocumentFrontmatter,
    KnowledgeSourceType,
    KnowledgeType,
    ReviewStatus,
    SourceCheckStatus,
)
from backend.app.schemas.provenance import PermittedUse


def test_valid_knowledge_frontmatter():
    fm = KnowledgeDocumentFrontmatter(
        id="over_concept",
        title="The Over in Cricket",
        sport=SportType.CRICKET,
        language=LanguageCode.EN,
        topic="cricket_terminology",
        knowledge_type=KnowledgeType.TERMINOLOGY,
        review_status=ReviewStatus.APPROVED,
        source_type=KnowledgeSourceType.OFFICIAL_REFERENCE,
        source_name="MCC Laws of Cricket",
        source_url="https://lawsofcricket.lords.org/",
        source_revision="2026-10-01",
        citation_locator="MCC Law 17",
        license="CC-BY-4.0",
        permitted_use=PermittedUse.OPEN_ATTRIBUTION,
        source_check_status=SourceCheckStatus.VERIFIED,
        document_revision="1.0.0",
        effective_from="2026-10-01",
    )
    assert fm.id == "over_concept"
    assert fm.review_status == ReviewStatus.APPROVED


def test_frontmatter_invalid_id_pattern():
    with pytest.raises(ValidationError):
        KnowledgeDocumentFrontmatter(
            id="Invalid-ID-With-Hyphens!",
            title="Invalid",
            sport=SportType.CRICKET,
            topic="test",
            knowledge_type=KnowledgeType.TERMINOLOGY,
            source_name="MCC",
            source_url="https://lawsofcricket.lords.org/",
            source_revision="2026",
        )


def test_frontmatter_forbids_extra_fields():
    with pytest.raises(ValidationError):
        KnowledgeDocumentFrontmatter(
            id="over_concept",
            title="The Over",
            sport=SportType.CRICKET,
            topic="rules",
            knowledge_type=KnowledgeType.RULES,
            source_name="MCC",
            source_url="https://example.com",
            source_revision="1",
            unexpected_field="disallowed",
        )


def test_valid_knowledge_chunk_payload():
    payload = KnowledgeChunkPayload(
        doc_id="doc_over_concept_abcdef123456",
        source_name="MCC Laws of Cricket",
        source_url="https://lawsofcricket.lords.org/",
        license="CC-BY-4.0",
        language=LanguageCode.EN,
        sport=SportType.CRICKET,
        topic="cricket_terminology",
        chunk_index=0,
        ingestion_date="2026-10-11T12:00:00Z",
        permitted_use=PermittedUse.OPEN_ATTRIBUTION,
        logical_doc_id="over_concept",
        document_revision="1.0.0",
        source_revision="2026-10-01",
        content_sha256="a" * 64,
        chunk_sha256="b" * 64,
        chunker_version="1.0.0",
        embedding_model="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        embedding_model_revision="faf4aa4225822f3bc6376869cb1164e8e3feedd0",
        embedding_dimensions=384,
        source_type=KnowledgeSourceType.OFFICIAL_REFERENCE,
        knowledge_type=KnowledgeType.TERMINOLOGY,
        section_title="The Over in Cricket",
        citation_locator="MCC Law 17",
        review_status=ReviewStatus.APPROVED,
        source_check_status=SourceCheckStatus.VERIFIED,
        active=True,
        text="An over consists of six legal deliveries bowled from one end.",
    )
    assert payload.doc_id.startswith("doc_over_concept_")
    assert payload.embedding_dimensions == 384


def test_chunk_payload_invalid_sha256():
    with pytest.raises(ValidationError):
        KnowledgeChunkPayload(
            doc_id="doc_over_concept_abcdef123456",
            source_name="MCC",
            source_url="https://lawsofcricket.lords.org/",
            license="CC-BY-4.0",
            language=LanguageCode.EN,
            sport=SportType.CRICKET,
            topic="cricket_terminology",
            chunk_index=0,
            ingestion_date="2026-10-11T12:00:00Z",
            permitted_use=PermittedUse.OPEN_ATTRIBUTION,
            logical_doc_id="over_concept",
            document_revision="1.0.0",
            source_revision="2026-10-01",
            content_sha256="invalid_short_hash",
            chunk_sha256="b" * 64,
            chunker_version="1.0.0",
            embedding_model="test",
            embedding_model_revision="test_rev",
            source_type=KnowledgeSourceType.OFFICIAL_REFERENCE,
            knowledge_type=KnowledgeType.TERMINOLOGY,
            section_title="Section",
            review_status=ReviewStatus.APPROVED,
            source_check_status=SourceCheckStatus.VERIFIED,
            active=True,
            text="Passage text here.",
        )


def test_knowledge_schema_contract_json_exists():
    schema_path = Path("contracts/knowledge.schema.json")
    assert schema_path.is_file(), "contracts/knowledge.schema.json must exist."
    with open(schema_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "$defs" in data or "properties" in data
