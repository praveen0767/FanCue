"""Tests for review status gate enforcement across development and production collections."""

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
    DEV_COLLECTION_NAME,
    PROD_COLLECTION_NAME,
    KnowledgeValidationError,
    check_collection_eligibility,
)


def make_doc(review_status: ReviewStatus, is_draft: bool = False) -> RawKnowledgeDocument:
    fm = KnowledgeDocumentFrontmatter(
        id="policy_test_doc",
        title="Policy Test",
        sport=SportType.CRICKET,
        language=LanguageCode.EN,
        topic="cricket_terminology",
        knowledge_type=KnowledgeType.TERMINOLOGY,
        review_status=review_status,
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
        filepath="test.md",
        frontmatter=fm,
        body="Body text",
        is_draft=is_draft,
    )


def test_prod_collection_accepts_approved():
    doc = make_doc(ReviewStatus.APPROVED, is_draft=False)
    # Should not raise
    check_collection_eligibility(doc, target_collection=PROD_COLLECTION_NAME)


def test_prod_collection_strictly_rejects_drafts():
    doc = make_doc(ReviewStatus.DRAFT, is_draft=True)
    with pytest.raises(KnowledgeValidationError, match="strictly requires 'approved' status"):
        check_collection_eligibility(doc, target_collection=PROD_COLLECTION_NAME, allow_draft=True)


def test_prod_collection_strictly_rejects_rejected():
    doc = make_doc(ReviewStatus.REJECTED, is_draft=False)
    with pytest.raises(KnowledgeValidationError, match="cannot be indexed into any collection"):
        check_collection_eligibility(doc, target_collection=PROD_COLLECTION_NAME)


def test_dev_collection_rejects_draft_without_flag():
    doc = make_doc(ReviewStatus.DRAFT, is_draft=True)
    with pytest.raises(KnowledgeValidationError, match="requires explicit --allow-draft flag"):
        check_collection_eligibility(doc, target_collection=DEV_COLLECTION_NAME, allow_draft=False)


def test_dev_collection_accepts_draft_with_flag():
    doc = make_doc(ReviewStatus.DRAFT, is_draft=True)
    # Should not raise
    check_collection_eligibility(doc, target_collection=DEV_COLLECTION_NAME, allow_draft=True)
