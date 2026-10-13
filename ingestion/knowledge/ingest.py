"""Orchestrator for knowledge base validation, chunking, embedding, and idempotent upsert."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.app.schemas.knowledge import KnowledgeChunk, ReviewStatus
from ingestion.knowledge.chunker import chunk_document
from ingestion.knowledge.embeddings import EmbeddingProvider, FastEmbedProvider
from ingestion.knowledge.loader import (
    RawKnowledgeDocument,
    load_knowledge_corpus,
    load_sources_registry,
)
from ingestion.knowledge.qdrant_store import (
    DEV_COLLECTION_NAME,
    PROD_COLLECTION_NAME,
    QdrantStore,
)
from ingestion.knowledge.validator import (
    check_collection_eligibility,
    validate_document_governance,
)


@dataclass
class IngestionReport:
    """Detailed summary report emitted by the ingestion pipeline."""
    target_collection: str
    is_dry_run: bool
    allow_draft: bool
    manifest_version: str
    documents_discovered: int = 0
    documents_accepted: int = 0
    documents_rejected: int = 0
    rejection_reasons: Dict[str, str] = field(default_factory=dict)
    chunks_generated: int = 0
    chunks_embedded: int = 0
    points_upserted: int = 0
    points_total_after: int = 0
    execution_status: str = "pending"
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None


def run_ingestion(
    target_collection: str = DEV_COLLECTION_NAME,
    dry_run: bool = True,
    allow_draft: bool = False,
    corpus_base_dir: str = "ingestion/knowledge",
    sources_registry_path: str = "ingestion/knowledge/sources.yml",
    embedder: Optional[EmbeddingProvider] = None,
    store: Optional[QdrantStore] = None,
) -> IngestionReport:
    """Execute the end-to-end knowledge ingestion pipeline."""
    registry = load_sources_registry(sources_registry_path)
    manifest_version = registry.get("version", "1.0.0")

    report = IngestionReport(
        target_collection=target_collection,
        is_dry_run=dry_run,
        allow_draft=allow_draft,
        manifest_version=manifest_version,
    )

    # 1. Discover all documents (approved + drafts)
    raw_docs = load_knowledge_corpus(corpus_base_dir, include_drafts=True)
    report.documents_discovered = len(raw_docs)

    accepted_docs: List[RawKnowledgeDocument] = []

    # 2. Validate governance and collection eligibility
    for doc in raw_docs:
        doc_id = doc.logical_id
        try:
            validate_document_governance(doc, sources_registry=registry)
            check_collection_eligibility(
                doc,
                target_collection=target_collection,
                allow_draft=allow_draft,
            )
            accepted_docs.append(doc)
            report.documents_accepted += 1
        except Exception as e:
            report.documents_rejected += 1
            report.rejection_reasons[doc_id] = str(e)

    if not accepted_docs:
        report.execution_status = "no_eligible_documents"
        report.completed_at = datetime.now(timezone.utc).isoformat()
        return report

    # 3. Initialize embedder
    if embedder is None:
        embedder = FastEmbedProvider()

    # 4. Semantic chunking
    all_chunks: List[KnowledgeChunk] = []
    ingestion_time = datetime.now(timezone.utc).isoformat()

    for doc in accepted_docs:
        chunks = chunk_document(doc, embedder=embedder, ingestion_date=ingestion_time)
        all_chunks.extend(chunks)

    report.chunks_generated = len(all_chunks)

    # If dry run, stop before embedding computation and Qdrant writes
    if dry_run:
        report.execution_status = "dry_run_success"
        report.completed_at = datetime.now(timezone.utc).isoformat()
        return report

    # 5. Embed chunks
    texts = [c.payload.text for c in all_chunks]
    embeddings = embedder.embed_texts(texts)
    report.chunks_embedded = len(embeddings)

    # 6. Initialize store and collection
    if store is None:
        store = QdrantStore()

    store.ensure_collection(
        collection_name=target_collection,
        vector_size=embedder.dimensions,
    )

    # 7. Idempotent upsert
    points_count = store.upsert_chunks(
        collection_name=target_collection,
        chunks=all_chunks,
        embeddings=embeddings,
    )
    report.points_upserted = points_count
    report.points_total_after = store.count_points(target_collection)

    report.execution_status = "applied_success"
    report.completed_at = datetime.now(timezone.utc).isoformat()
    return report
