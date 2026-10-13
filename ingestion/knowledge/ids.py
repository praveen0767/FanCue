"""Deterministic identifier generators for knowledge documents, chunks, and vector points."""

import hashlib
import re
import uuid
from typing import Tuple

# Fixed DNS UUID namespace for FanCue vector points
FANCUE_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def normalize_text_canonical(text: str) -> str:
    """Normalize text deterministically.
    
    Strips trailing whitespace on each line, normalizes CRLF to LF, collapses redundant blank lines.
    """
    lines = [line.strip() for line in text.replace("\r\n", "\n").split("\n")]
    normalized = "\n".join(lines).strip()
    # Collapse multiple consecutive empty lines to a single empty line
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized


def compute_sha256(text: str) -> str:
    """Compute hex SHA-256 hash of normalized text string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def generate_doc_id(logical_doc_id: str, content_sha256: str) -> str:
    """Generate deterministic document identity for specific content revision."""
    return f"doc_{logical_doc_id}_{content_sha256[:12]}"


def generate_chunk_id(doc_id: str, chunk_index: int, chunk_sha256: str) -> str:
    """Generate deterministic chunk identifier."""
    return f"{doc_id}_c{chunk_index}_{chunk_sha256[:8]}"


def generate_point_uuid(embedding_model: str, chunk_id: str) -> str:
    """Generate deterministic UUIDv5 for Qdrant point from model profile and chunk ID."""
    name_str = f"fancue:v1:{embedding_model}:{chunk_id}"
    return str(uuid.uuid5(FANCUE_NAMESPACE, name_str))
