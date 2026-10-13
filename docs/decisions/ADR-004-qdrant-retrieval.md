# ADR-004 — Qdrant as Semantic Contextual Retrieval, Not Authoritative Score Store

**Status:** Accepted
**Date:** 2026-10-11
**Phase:** 00

---

## Context

FanCue needs to enrich deterministic match facts with contextual knowledge:
rules explanations, historical context, player background, tactical analysis.
This knowledge is unstructured, multilingual, and best retrieved by semantic
similarity rather than exact keyword match.

Additionally, a clear boundary must be drawn: Qdrant is for knowledge
retrieval, not for storing authoritative match state (scores, events).

---

## Decision

Qdrant is the **semantic knowledge retrieval component**. It stores ingested
contextual knowledge documents and serves similarity-search queries filtered
by sport and language. It is explicitly **not** the authoritative store for
dynamic match scores, event sequences, or any data that the deterministic
engine produces.

---

## Alternatives Considered

| Alternative | Reason rejected |
|---|---|
| PostgreSQL full-text search | Less capable for semantic similarity; does not support embedding-based retrieval. |
| Elasticsearch / OpenSearch | Higher operational footprint; Qdrant is purpose-built for vector search and simpler to operate. |
| In-memory vector store (FAISS) | No persistence; no metadata filtering; not suitable for a multi-session product. |
| Storing match scores in Qdrant | Qdrant is a vector store, not a relational or time-series database. Score data requires exact lookup, not approximate similarity. |
| Weaviate | Functionally comparable; Qdrant chosen for simpler API, Docker deployment, and active maintenance. |

---

## Consequences

- Every document ingested into Qdrant must carry mandatory provenance metadata
  (see AGENTS.md section 6).
- Retrieval queries must include sport and language filters. Cross-sport
  context bleed (cricket facts contaminating a football explanation) must be
  prevented by filter, not by prompt engineering alone.
- A swappable embedding-provider interface must be implemented so that the
  embedding model can be changed without re-architecting the retrieval layer.
- Retrieval results must include `doc_id`, `source_name`, and `source_url`
  so that explanation outputs can be traced to their evidence sources.
- Retrieval quality must be evaluated with known-relevant question sets
  before Phase 05 begins.
- Qdrant runs locally via Docker during development; a managed Qdrant Cloud
  instance is the planned production deployment (to be confirmed in Phase 07).

---

## Conditions for Revisiting

- If Qdrant''s filtering capabilities prove insufficient for multilingual
  or multi-topic queries at scale.
- If a managed embedding + retrieval service (e.g., Vertex AI Matching Engine)
  offers measurably better retrieval quality with acceptable operational cost.
- If the knowledge corpus grows to a size where Qdrant''s single-node
  capacity becomes a constraint (document a measured threshold, not a guess).
