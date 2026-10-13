"""Tests for source attribution, URL validation, and registry consistency."""

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
from ingestion.knowledge.loader import RawKnowledgeDocument
from ingestion.knowledge.validator import (
    KnowledgeValidationError,
    validate_document_governance,
)


def make_raw_doc(
    source_url: str = "https://lawsofcricket.lords.org/",
    source_name: str = "MCC Laws of Cricket",
    license: str = "CC-BY-4.0",
    review_status: ReviewStatus = ReviewStatus.APPROVED,
    is_draft: bool = False,
) -> RawKnowledgeDocument:
    fm = KnowledgeDocumentFrontmatter(
        id="test_doc",
        title="Test Document",
        sport=SportType.CRICKET,
        language=LanguageCode.EN,
        topic="cricket_terminology",
        knowledge_type=KnowledgeType.TERMINOLOGY,
        review_status=review_status,
        source_type=KnowledgeSourceType.OFFICIAL_REFERENCE,
        source_name=source_name,
        source_url=source_url,
        source_revision="2026-10-01",
        license=license,
        permitted_use=PermittedUse.OPEN_ATTRIBUTION,
        source_check_status=SourceCheckStatus.VERIFIED,
        document_revision="1.0.0",
    )
    return RawKnowledgeDocument(
        filepath="ingestion/knowledge/approved/test_doc.md",
        frontmatter=fm,
        body="This is a test body.",
        is_draft=is_draft,
    )


def test_validate_document_governance_valid():
    doc = make_raw_doc()
    registry = {
        "sources": [
            {
                "source_id": "mcc_laws",
                "source_name": "MCC Laws of Cricket",
                "canonical_url": "https://lawsofcricket.lords.org/",
            }
        ]
    }
    # Should not raise
    validate_document_governance(doc, sources_registry=registry)


def test_validate_document_governance_invalid_url():
    doc = make_raw_doc(source_url="not_a_valid_url")
    with pytest.raises(KnowledgeValidationError, match="invalid source_url"):
        validate_document_governance(doc)


def test_validate_document_governance_missing_license():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        make_raw_doc(license=" ")


def test_validate_document_governance_unregistered_source():
    doc = make_raw_doc(source_url="https://unregistered-source.com/foo", source_name="Unknown Blog")
    registry = {
        "sources": [
            {
                "source_id": "mcc_laws",
                "source_name": "MCC Laws of Cricket",
                "canonical_url": "https://lawsofcricket.lords.org/",
            }
        ]
    }
    with pytest.raises(KnowledgeValidationError, match="does not match any audited entry"):
        validate_document_governance(doc, sources_registry=registry)


def test_validate_document_governance_draft_location_status_mismatch():
    doc = make_raw_doc(review_status=ReviewStatus.APPROVED, is_draft=True)
    with pytest.raises(KnowledgeValidationError, match="located in drafts/ directory must have review_status='draft'"):
        validate_document_governance(doc)
