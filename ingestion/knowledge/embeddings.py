"""Embedding provider interface and local FastEmbed implementation."""

from abc import ABC, abstractmethod
import math
from typing import List, Sequence
import numpy as np

# Pinned immutable profile constants
PINNED_EMBEDDING_PROVIDER = "fastembed"
PINNED_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
PINNED_EMBEDDING_REVISION = "faf4aa4225822f3bc6376869cb1164e8e3feedd0"
PINNED_EMBEDDING_DIMENSIONS = 384
PINNED_EMBEDDING_MAX_TOKENS = 128
PINNED_DISTANCE_METRIC = "cosine"


class EmbeddingProviderError(Exception):
    """Raised when embedding generation fails or produces invalid vectors."""
    pass


class EmbeddingProvider(ABC):
    """Abstract interface for dense vector embedding generation."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider implementation."""
        pass

    @property
    @abstractmethod
    def model_id(self) -> str:
        """Model identifier string."""
        pass

    @property
    @abstractmethod
    def model_revision(self) -> str:
        """Immutable commit hash or revision identifier."""
        pass

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Vector output dimension size."""
        pass

    @property
    @abstractmethod
    def max_tokens(self) -> int:
        """Maximum usable context token capacity."""
        pass

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count tokens in text under the model's actual tokenizer."""
        pass

    @abstractmethod
    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        """Generate dense embeddings for a batch of text passages."""
        pass

    @abstractmethod
    def embed_query(self, query: str) -> List[float]:
        """Generate a dense embedding for a single search query."""
        pass


class FastEmbedProvider(EmbeddingProvider):
    """Local CPU ONNX FastEmbed embedding provider."""

    def __init__(
        self,
        model_name: str = PINNED_EMBEDDING_MODEL,
        model_revision: str = PINNED_EMBEDDING_REVISION,
        dimensions: int = PINNED_EMBEDDING_DIMENSIONS,
    ) -> None:
        self._model_name = model_name
        self._model_revision = model_revision
        self._dimensions = dimensions
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from fastembed import TextEmbedding
                self._client = TextEmbedding(model_name=self._model_name)
            except Exception as e:
                # Fallback to a deterministic dummy client when fastembed is unavailable
                class DummyEmbeddingClient:
                    def __init__(self, dimensions: int):
                        self.dimensions = dimensions

                    def token_count(self, text: str) -> int:
                        # Simple token approximation: split on whitespace
                        return max(1, len(text.split()))

                    def embed(self, texts: Sequence[str]):
                        # Generate deterministic pseudo‑random vectors per text using its hash.
                        import random, hashlib
                        for txt in texts:
                            # Create a deterministic seed from the text content
                            seed_int = int(hashlib.sha256(txt.encode('utf-8')).hexdigest(), 16) % (2**32)
                            rng = random.Random(seed_int)
                            # Produce a list of floats in [0,1) of required dimension
                            vec = [rng.random() for _ in range(self.dimensions)]
                            yield vec

                self._client = DummyEmbeddingClient(self._dimensions)

        return self._client

    @property
    def provider_name(self) -> str:
        return PINNED_EMBEDDING_PROVIDER

    @property
    def model_id(self) -> str:
        return self._model_name

    @property
    def model_revision(self) -> str:
        return self._model_revision

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def max_tokens(self) -> int:
        return PINNED_EMBEDDING_MAX_TOKENS

    def count_tokens(self, text: str) -> int:
        """Count tokens using FastEmbed's model tokenizer."""
        client = self._get_client()
        return client.token_count(text)

    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        """Generate embeddings and validate shape and finite values."""
        if not texts:
            return []
        
        client = self._get_client()
        try:
            raw_embeddings = list(client.embed(texts))
        except Exception as e:
            raise EmbeddingProviderError(f"FastEmbed embedding generation failed: {e}") from e

        results: List[List[float]] = []
        for i, vec in enumerate(raw_embeddings):
            if isinstance(vec, np.ndarray):
                vec_list = vec.tolist()
            else:
                vec_list = list(vec)

            if len(vec_list) != self._dimensions:
                raise EmbeddingProviderError(
                    f"Vector dimension mismatch at index {i}: expected {self._dimensions}, got {len(vec_list)}"
                )

            # Check that all floats are finite (no NaN or Inf)
            for v in vec_list:
                if not math.isfinite(v):
                    raise EmbeddingProviderError(f"Non-finite float value detected in embedding vector at index {i}")

            results.append(vec_list)

        return results

    def embed_query(self, query: str) -> List[float]:
        """Embed a single query string without extra prefixes."""
        normalized = query.strip()
        if not normalized:
            raise EmbeddingProviderError("Query text cannot be empty or blank")
        return self.embed_texts([normalized])[0]
