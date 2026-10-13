"""Semantic markdown chunking algorithm with token budget enforcement."""

from datetime import datetime, timezone
import re
from typing import List, Optional

from backend.app.schemas.knowledge import (
    KnowledgeChunk,
    KnowledgeChunkPayload,
)
from ingestion.knowledge.embeddings import (
    EmbeddingProvider,
    PINNED_EMBEDDING_DIMENSIONS,
    PINNED_EMBEDDING_MODEL,
    PINNED_EMBEDDING_REVISION,
)
from ingestion.knowledge.ids import (
    compute_sha256,
    generate_chunk_id,
    generate_doc_id,
    generate_point_uuid,
    normalize_text_canonical,
)
from ingestion.knowledge.loader import RawKnowledgeDocument

CHUNKER_VERSION = "1.0.0"
# Target 60-80% of 128 max capacity (~77-102 tokens)
TARGET_CHUNK_TOKENS = 95
MAX_CHUNK_TOKENS = 120


class ChunkerError(Exception):
    """Raised when semantic chunking encounters token overflow or malformed content."""
    pass


def extract_headings_and_paragraphs(body: str) -> List[tuple[str, str]]:
    """Extract section heading and associated paragraph blocks from markdown body.
    
    Returns list of (section_heading, block_text).
    """
    lines = body.split("\n")
    current_heading = "General"
    sections: List[tuple[str, str]] = []
    current_block: List[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            # New heading encountered
            if current_block:
                text = "\n".join(current_block).strip()
                if text:
                    sections.append((current_heading, text))
                current_block = []
            current_heading = stripped.lstrip("#").strip()
        else:
            current_block.append(line)

    if current_block:
        text = "\n".join(current_block).strip()
        if text:
            sections.append((current_heading, text))

    return sections


def chunk_document(
    doc: RawKnowledgeDocument,
    embedder: EmbeddingProvider,
    ingestion_date: Optional[str] = None,
) -> List[KnowledgeChunk]:
    """Deterministically segment a document into semantic chunks obeying token limits."""
    if ingestion_date is None:
        ingestion_date = datetime.now(timezone.utc).isoformat()

    fm = doc.frontmatter
    normalized_full_body = normalize_text_canonical(doc.body)
    content_sha256 = compute_sha256(normalized_full_body)
    doc_id = generate_doc_id(fm.id, content_sha256)

    sections = extract_headings_and_paragraphs(normalized_full_body)
    raw_passages: List[tuple[str, str]] = []

    for heading, text in sections:
        # Check token length of the entire section text
        section_tokens = embedder.count_tokens(text)
        if section_tokens <= MAX_CHUNK_TOKENS:
            # Fits cleanly within the token budget as a single atomic chunk
            raw_passages.append((heading, text))
        else:
            # Need to split long section by paragraphs
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            current_p_chunk: List[str] = []
            
            for para in paragraphs:
                candidate = "\n\n".join(current_p_chunk + [para])
                if embedder.count_tokens(candidate) <= MAX_CHUNK_TOKENS:
                    current_p_chunk.append(para)
                else:
                    if current_p_chunk:
                        chunk_text = "\n\n".join(current_p_chunk)
                        raw_passages.append((heading, chunk_text))
                        current_p_chunk = [para]
                    else:
                        # Single paragraph exceeds MAX_CHUNK_TOKENS
                        raise ChunkerError(
                            f"Single paragraph in document '{fm.id}' exceeds maximum token limit ({MAX_CHUNK_TOKENS} tokens). "
                            f"Tokens: {embedder.count_tokens(para)}. Paragraph must be authored more concisely."
                        )
            
            if current_p_chunk:
                raw_passages.append((heading, "\n\n".join(current_p_chunk)))

    chunks: List[KnowledgeChunk] = []

    for chunk_idx, (sec_title, chunk_text) in enumerate(raw_passages):
        norm_chunk_text = normalize_text_canonical(chunk_text)
        chunk_sha256 = compute_sha256(norm_chunk_text)
        chunk_id = generate_chunk_id(doc_id, chunk_idx, chunk_sha256)
        point_id = generate_point_uuid(embedder.model_id, chunk_id)
        tokens = embedder.count_tokens(norm_chunk_text)

        payload = KnowledgeChunkPayload(
            doc_id=doc_id,
            source_name=fm.source_name,
            source_url=fm.source_url,
            license=fm.license,
            language=fm.language,
            sport=fm.sport,
            topic=fm.topic,
            chunk_index=chunk_idx,
            ingestion_date=ingestion_date,
            permitted_use=fm.permitted_use,
            logical_doc_id=fm.id,
            document_revision=fm.document_revision,
            source_revision=fm.source_revision,
            content_sha256=content_sha256,
            chunk_sha256=chunk_sha256,
            chunker_version=CHUNKER_VERSION,
            embedding_model=embedder.model_id,
            embedding_model_revision=embedder.model_revision,
            embedding_dimensions=embedder.dimensions,
            source_type=fm.source_type,
            knowledge_type=fm.knowledge_type,
            section_title=sec_title,
            citation_locator=fm.citation_locator,
            effective_from=fm.effective_from,
            effective_to=fm.effective_to,
            review_status=fm.review_status,
            source_check_status=fm.source_check_status,
            active=True,
            text=norm_chunk_text,
        )

        chunk = KnowledgeChunk(
            chunk_id=chunk_id,
            point_id=point_id,
            payload=payload,
            token_count=tokens,
        )
        chunks.append(chunk)

    return chunks
