"""Validation rules and review status governance for knowledge documents."""

from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from backend.app.schemas.knowledge import ReviewStatus
from ingestion.knowledge.loader import RawKnowledgeDocument


class KnowledgeValidationError(Exception):
    """Raised when knowledge document metadata fails domain governance checks."""
    pass


DEV_COLLECTION_NAME = "fancue_cricket_knowledge_dev_v1"
PROD_COLLECTION_NAME = "fancue_cricket_knowledge_v1"


def validate_document_governance(
    doc: RawKnowledgeDocument,
    sources_registry: Optional[Dict[str, Any]] = None,
) -> None:
    """Validate all source attribution and governance requirements for a document."""
    fm = doc.frontmatter

    # 1. Source URL validity
    parsed_url = urlparse(fm.source_url)
    if not (parsed_url.scheme in ("http", "https") and parsed_url.netloc):
        raise KnowledgeValidationError(
            f"Document '{fm.id}' has invalid source_url: '{fm.source_url}'. Must be a valid HTTP/HTTPS URL."
        )

    # 2. License check
    if not fm.license or len(fm.license.strip()) < 2:
        raise KnowledgeValidationError(f"Document '{fm.id}' is missing a valid license specification.")

    # 3. Source registry cross-check
    if sources_registry and "sources" in sources_registry:
        known_urls = [s.get("canonical_url") for s in sources_registry["sources"] if "canonical_url" in s]
        known_publishers = [s.get("source_name") for s in sources_registry["sources"] if "source_name" in s]
        
        # Verify source_url domain or source_name relates to an audited upstream source
        matched = any(
            fm.source_url.startswith(u) or u in fm.source_url for u in known_urls if u
        ) or any(
            p.lower() in fm.source_name.lower() or fm.source_name.lower() in p.lower() for p in known_publishers if p
        )
        if not matched:
            raise KnowledgeValidationError(
                f"Document '{fm.id}' source '{fm.source_name}' ({fm.source_url}) does not match any audited entry in sources.yml."
            )

    # 4. Review status consistency
    if doc.is_draft and fm.review_status != ReviewStatus.DRAFT:
        raise KnowledgeValidationError(
            f"Document '{fm.id}' located in drafts/ directory must have review_status='draft', got '{fm.review_status}'."
        )


def check_collection_eligibility(
    doc: RawKnowledgeDocument,
    target_collection: str,
    allow_draft: bool = False,
) -> None:
    """Enforce strict gate policy on collection eligibility.
    
    Rules:
    - Production collection: ONLY approved documents are eligible. Drafts are strictly forbidden.
    - Development collection: Approved documents allowed; drafts allowed only if allow_draft=True.
    - Rejected documents are NEVER eligible for any collection.
    """
    fm = doc.frontmatter

    if fm.review_status == ReviewStatus.REJECTED:
        raise KnowledgeValidationError(
            f"Document '{fm.id}' has review_status='rejected' and cannot be indexed into any collection."
        )

    if target_collection == PROD_COLLECTION_NAME:
        if fm.review_status != ReviewStatus.APPROVED:
            raise KnowledgeValidationError(
                f"Document '{fm.id}' has review_status='{fm.review_status}'. Production collection '{PROD_COLLECTION_NAME}' strictly requires 'approved' status."
            )
        if doc.is_draft:
            raise KnowledgeValidationError(
                f"Document '{fm.id}' is a draft file and cannot be indexed into production collection '{PROD_COLLECTION_NAME}'."
            )

    elif target_collection == DEV_COLLECTION_NAME:
        if fm.review_status == ReviewStatus.DRAFT and not allow_draft:
            raise KnowledgeValidationError(
                f"Document '{fm.id}' is in draft status. Development collection '{DEV_COLLECTION_NAME}' requires explicit --allow-draft flag to include drafts."
            )

    else:
        # Custom / test collection names
        if fm.review_status == ReviewStatus.DRAFT and not allow_draft:
            raise KnowledgeValidationError(
                f"Draft document '{fm.id}' requires allow_draft=True to be indexed."
            )
