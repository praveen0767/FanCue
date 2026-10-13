# FanCue Architecture: Knowledge Ingestion & Retrieval Pipeline

> **Document ID:** ARCH-008  
> **Status:** Implemented (Phase 04)  
> **Author:** Principal AI Systems Engineer / Retrieval Engineer  

---

## 1. System Context & Responsibilities

The Knowledge Ingestion and Retrieval Pipeline is responsible for providing **factual domain grounding** to the downstream AI explanation orchestrator (Phase 05).

### Core Invariants

1. **Match Truth Isolation:** Qdrant is strictly an auxiliary semantic knowledge store. It **never** stores live scores, dynamic match state, or replaces deterministic engine calculations.
2. **Deterministic Identifiers:** Every chunk ID and vector point UUID is deterministically generated from content hashes, ensuring idempotent repeated runs.
3. **Source Attribution & Provenance:** No passage is indexed without audited upstream provenance (MCC Laws, ICC Playing Conditions, Cricsheet spec, or CC-BY-4.0 FanCue notes).
4. **Editorial Review Gates:** Unapproved drafts are strictly barred from production collections (`fancue_cricket_knowledge_v1`).

---

## 2. Ingestion Pipeline Flow

```
[Markdown Note with YAML Frontmatter]
         │
         ▼
[Validator: validate_document_governance] ──► Checks URL, license, registry, review status
         │
         ▼
[Collection Eligibility Gate] ───────────────► Rejects drafts for prod; rejects rejected notes
         │
         ▼
[Text Normalizer: normalize_text_canonical] ──► Collapses line whitespace, canonical LF
         │
         ▼
[Semantic Chunker: chunk_document] ──────────► Parses markdown headers, enforces 120 token ceiling
         │
         ▼
[Deterministic ID Generator] ────────────────► Computes content_sha256, doc_id, chunk_id, UUIDv5
         │
         ▼
[Embedding Provider: FastEmbedProvider] ─────► Local CPU ONNX 384-dim dense vector generation
         │
         ▼
[Qdrant Store: QdrantStore.upsert_chunks] ───► Idempotent point upsert with typed payload
```

---

## 3. Metadata Payload Schema

Every point in Qdrant carries a strongly-typed payload complying with `backend/app/schemas/knowledge.py`:

```json
{
  "doc_id": "doc_over_concept_25a045f25f9a",
  "logical_doc_id": "over_concept",
  "document_revision": "1.0.0",
  "source_revision": "2026-10-01",
  "source_name": "MCC Laws of Cricket",
  "source_url": "https://lawsofcricket.lords.org/",
  "license": "CC-BY-4.0",
  "language": "en",
  "sport": "cricket",
  "topic": "cricket_terminology",
  "chunk_index": 0,
  "chunker_version": "1.0.0",
  "embedding_model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
  "embedding_model_revision": "faf4aa4225822f3bc6376869cb1164e8e3feedd0",
  "embedding_dimensions": 384,
  "source_type": "official_reference",
  "knowledge_type": "terminology",
  "section_title": "The Over in Cricket",
  "citation_locator": "MCC Law 17",
  "effective_from": "2026-10-01",
  "effective_to": null,
  "review_status": "approved",
  "source_check_status": "verified",
  "active": true,
  "text": "An over consists of a sequence of six legal deliveries bowled from one end..."
}
```

---

## 4. Retrieval API & Filtering

The retrieval library (`RetrievalService`) accepts typed `RetrievalQuery` objects.
Before relevance scoring, strict payload filters are applied:
- `sport`: Matches query sport (e.g. `cricket`). Prevents cross-sport contamination.
- `language`: Matches query language (e.g. `en` or `ta`).
- `active`: Must be `True`.
- `review_status`: `["approved"]` for standard queries; `["approved", "draft"]` only if `allow_draft=True`.

When no hits match the filter criteria, the service returns a `FILTER_EMPTY` status rather than fabricating matches or leaking passages from unrelated sports.
