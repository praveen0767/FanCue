"""Retrieval library and query execution engine for Qdrant knowledge lookup."""

from typing import List, Optional

from backend.app.schemas.common import LanguageCode, SportType
from backend.app.schemas.knowledge import ReviewStatus
from backend.app.schemas.retrieval import (
    RetrievalQuery,
    RetrievalResult,
    RetrievalStatus,
    RetrievedPassage,
)
from ingestion.knowledge.embeddings import EmbeddingProvider, FastEmbedProvider
from ingestion.knowledge.qdrant_store import (
    DEV_COLLECTION_NAME,
    PROD_COLLECTION_NAME,
    QdrantStore,
    QdrantStoreError,
)


class RetrievalService:
    """Library service providing contextual knowledge retrieval from Qdrant."""

    def __init__(
        self,
        collection_name: str = DEV_COLLECTION_NAME,
        embedder: Optional[EmbeddingProvider] = None,
        store: Optional[QdrantStore] = None,
        allow_draft: bool = False,
    ) -> None:
        self.collection_name = collection_name
        self.embedder = embedder or FastEmbedProvider()
        self.store = store or QdrantStore()
        self.allow_draft = allow_draft

    def retrieve(self, query: RetrievalQuery) -> RetrievalResult:
        """Execute typed semantic retrieval with strict sport and status filtering."""
        # 1. Validate query constraints
        if not query.query_text or len(query.query_text.strip()) < 3:
            return RetrievalResult(
                query=query,
                passages=[],
                status=RetrievalStatus.FAILED,
                error_detail="Query text must be at least 3 characters long.",
            )

        # 2. Determine allowed review statuses
        allowed_statuses = [ReviewStatus.APPROVED.value]
        if self.allow_draft:
            allowed_statuses.append(ReviewStatus.DRAFT.value)

        # 3. Generate query embedding
        try:
            query_vector = self.embedder.embed_query(query.query_text)
        except Exception as e:
            return RetrievalResult(
                query=query,
                passages=[],
                status=RetrievalStatus.FAILED,
                error_detail=f"Embedding generation failed: {e}",
            )

        # 4. Execute filtered search
        target_topic = query.target_topics[0] if (query.target_topics and len(query.target_topics) > 0) else None

        try:
            hits = self.store.search_similar(
                collection_name=self.collection_name,
                query_vector=query_vector,
                sport=query.sport.value,
                language=query.language.value,
                allowed_review_statuses=allowed_statuses,
                topic=target_topic,
                limit=query.limit,
            )
        except QdrantStoreError as e:
            return RetrievalResult(
                query=query,
                passages=[],
                status=RetrievalStatus.FAILED,
                error_detail=f"Qdrant vector search failed: {e}",
            )
        except Exception as e:
            return RetrievalResult(
                query=query,
                passages=[],
                status=RetrievalStatus.FAILED,
                error_detail=f"Unexpected retrieval error: {e}",
            )

        # 5. Handle empty result sets
        if not hits:
            # Check if collection is empty or if filter excluded all items
            try:
                total_in_coll = self.store.count_points(self.collection_name)
                if total_in_coll == 0:
                    return RetrievalResult(
                        query=query,
                        passages=[],
                        status=RetrievalStatus.EMPTY_RESULT,
                        error_detail=f"Collection '{self.collection_name}' contains no points.",
                    )
                else:
                    return RetrievalResult(
                        query=query,
                        passages=[],
                        status=RetrievalStatus.FILTER_EMPTY,
                        error_detail=f"No passages matched filters (sport='{query.sport}', language='{query.language}').",
                    )
            except Exception:
                return RetrievalResult(
                    query=query,
                    passages=[],
                    status=RetrievalStatus.FILTER_EMPTY,
                    error_detail="No passages matched search criteria.",
                )

        # 6. Format retrieved passages
        passages: List[RetrievedPassage] = []
        for hit in hits:
            payload = hit.payload or {}
            score = max(0.0, min(1.0, float(hit.score)))

            passage = RetrievedPassage(
                doc_id=payload.get("doc_id", "unknown_doc"),
                sport=SportType(payload.get("sport", query.sport.value)),
                language=LanguageCode(payload.get("language", query.language.value)),
                topic=payload.get("topic", "general"),
                content=payload.get("text", ""),
                source_name=payload.get("source_name", "Unknown Source"),
                source_url=payload.get("source_url", "https://fancue.org"),
                license=payload.get("license", "CC-BY-4.0"),
                score=round(score, 4),
            )
            passages.append(passage)

        return RetrievalResult(
            query=query,
            passages=passages,
            status=RetrievalStatus.SUCCESS,
            error_detail=None,
        )
