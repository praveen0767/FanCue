"""Qdrant collection management, payload indexing, and vector storage adapter."""

from typing import Any, Dict, List, Optional
import os

from qdrant_client import QdrantClient
from qdrant_client.http import models as rest
from qdrant_client.http.exceptions import UnexpectedResponse

from backend.app.schemas.knowledge import KnowledgeChunk
from ingestion.knowledge.embeddings import PINNED_EMBEDDING_DIMENSIONS

DEV_COLLECTION_NAME = "fancue_cricket_knowledge_dev_v1"
PROD_COLLECTION_NAME = "fancue_cricket_knowledge_v1"

INDEXED_PAYLOAD_FIELDS = {
    "sport": rest.PayloadSchemaType.KEYWORD,
    "language": rest.PayloadSchemaType.KEYWORD,
    "topic": rest.PayloadSchemaType.KEYWORD,
    "review_status": rest.PayloadSchemaType.KEYWORD,
    "active": rest.PayloadSchemaType.BOOL,
    "permitted_use": rest.PayloadSchemaType.KEYWORD,
    "logical_doc_id": rest.PayloadSchemaType.KEYWORD,
}


class QdrantStoreError(Exception):
    """Raised when Qdrant connection, collection initialization, or querying fails."""
    pass


class QdrantStore:
    """Adapter managing Qdrant collections, points, and payload-filtered similarity search."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: int = 6333,
        path: Optional[str] = None,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        location: Optional[str] = None,
        allow_local_fallback: Optional[bool] = None,
    ) -> None:
        self._host = host or os.environ.get("QDRANT_HOST", "127.0.0.1")
        self._port = port or int(os.environ.get("QDRANT_PORT", "6333"))
        self._api_key = api_key or os.environ.get("QDRANT_API_KEY", None)
        self._path = path
        self._url = url or os.environ.get("QDRANT_URL", None)
        self._location = location
        if allow_local_fallback is not None:
            self._allow_local_fallback = allow_local_fallback
        else:
            is_prod = os.environ.get("FANCUE_ENV", "development").lower() == "production"
            self._allow_local_fallback = not is_prod
        self._client: Optional[QdrantClient] = None

    def get_client(self) -> QdrantClient:
        """Get or initialize QdrantClient instance."""
        if self._client is None:
            try:
                if self._location == ":memory:":
                    self._client = QdrantClient(":memory:")
                elif self._path:
                    self._client = QdrantClient(path=self._path)
                elif self._url:
                    self._client = QdrantClient(url=self._url, api_key=self._api_key, timeout=5.0)
                    self._client.get_collections()
                else:
                    # Attempt connection to configured server
                    try:
                        client = QdrantClient(host=self._host, port=self._port, api_key=self._api_key, timeout=2.0)
                        # Test server connectivity
                        client.get_collections()
                        self._client = client
                    except Exception as server_err:
                        if not self._allow_local_fallback:
                            raise QdrantStoreError(
                                f"Failed to connect to Qdrant at {self._host}:{self._port}. "
                                "Local fallback is disabled in production."
                            ) from server_err
                        # Server not running: fallback to persistent local directory
                        local_storage_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "storage", "qdrant"))
                        os.makedirs(local_storage_dir, exist_ok=True)
                        self._client = QdrantClient(path=local_storage_dir)
            except QdrantStoreError:
                raise
            except Exception as e:
                raise QdrantStoreError(f"Could not connect to or initialize Qdrant: {e}") from e
        return self._client

    def ensure_collection(
        self,
        collection_name: str,
        vector_size: int = PINNED_EMBEDDING_DIMENSIONS,
    ) -> bool:
        """Ensure the specified collection exists with correct vector parameters and payload indexes.
        
        Returns True if newly created, False if already existed.
        """
        client = self.get_client()
        try:
            collections = [c.name for c in client.get_collections().collections]
        except Exception as e:
            raise QdrantStoreError(f"Failed to query Qdrant collections: {e}") from e

        created = False
        if collection_name not in collections:
            try:
                client.create_collection(
                    collection_name=collection_name,
                    vectors_config=rest.VectorParams(
                        size=vector_size,
                        distance=rest.Distance.COSINE,
                    ),
                )
                created = True
            except Exception as e:
                raise QdrantStoreError(f"Failed to create collection '{collection_name}': {e}") from e

            # Create payload indexes for efficient filtering
            for field_name, field_type in INDEXED_PAYLOAD_FIELDS.items():
                try:
                    client.create_payload_index(
                        collection_name=collection_name,
                        field_name=field_name,
                        field_schema=field_type,
                    )
                except Exception as e:
                    raise QdrantStoreError(
                        f"Failed to create index for field '{field_name}' in collection '{collection_name}': {e}"
                    ) from e

        return created

    def upsert_chunks(
        self,
        collection_name: str,
        chunks: List[KnowledgeChunk],
        embeddings: List[List[float]],
    ) -> int:
        """Idempotently upsert knowledge chunks with vectors into Qdrant."""
        if not chunks:
            return 0
        if len(chunks) != len(embeddings):
            raise QdrantStoreError(
                f"Count mismatch between chunks ({len(chunks)}) and embeddings ({len(embeddings)})"
            )

        client = self.get_client()
        points: List[rest.PointStruct] = []

        for chunk, vector in zip(chunks, embeddings):
            payload_dict = chunk.payload.model_dump()
            points.append(
                rest.PointStruct(
                    id=chunk.point_id,
                    vector=vector,
                    payload=payload_dict,
                )
            )

        try:
            client.upsert(
                collection_name=collection_name,
                points=points,
                wait=True,
            )
        except Exception as e:
            raise QdrantStoreError(f"Failed to upsert points into collection '{collection_name}': {e}") from e

        return len(points)

    def count_points(self, collection_name: str) -> int:
        """Count total points in collection."""
        client = self.get_client()
        try:
            res = client.count(collection_name=collection_name, exact=True)
            return res.count
        except Exception as e:
            raise QdrantStoreError(f"Failed to count points in collection '{collection_name}': {e}") from e

    def search_similar(
        self,
        collection_name: str,
        query_vector: List[float],
        sport: str,
        language: str,
        allowed_review_statuses: List[str],
        topic: Optional[str] = None,
        limit: int = 3,
    ) -> List[rest.ScoredPoint]:
        """Execute filtered vector similarity search."""
        client = self.get_client()

        filter_conditions: List[rest.FieldCondition] = [
            rest.FieldCondition(
                key="sport",
                match=rest.MatchValue(value=sport),
            ),
            rest.FieldCondition(
                key="language",
                match=rest.MatchValue(value=language),
            ),
            rest.FieldCondition(
                key="active",
                match=rest.MatchValue(value=True),
            ),
        ]

        if allowed_review_statuses:
            filter_conditions.append(
                rest.FieldCondition(
                    key="review_status",
                    match=rest.MatchAny(any=allowed_review_statuses),
                )
            )

        if topic:
            filter_conditions.append(
                rest.FieldCondition(
                    key="topic",
                    match=rest.MatchValue(value=topic),
                )
            )

        query_filter = rest.Filter(must=filter_conditions)

        try:
            # Qdrant client 1.13+ supports query_points
            response = client.query_points(
                collection_name=collection_name,
                query=query_vector,
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
            return response.points
        except Exception as e:
            raise QdrantStoreError(
                f"Vector search failed on collection '{collection_name}': {e}"
            ) from e

    def close(self) -> None:
        """Close Qdrant client connection if open."""
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
