# FanCue Knowledge Ingestion & Retrieval Pipeline

> **Subsystem:** Ingestion / Knowledge Retrieval  
> **Status:** Phase 04 Completed  
> **Owner:** Retrieval & AI Systems Engineering  

---

## 1. Overview

The FanCue Knowledge pipeline manages curated sports domain knowledge, generates dense vector embeddings, and enables source-attributed semantic retrieval from Qdrant.

It provides contextual grounding (rules, scoring mechanics, interval interpretations) for AI explanation generation in Phase 05, while strictly preserving the boundary that **deterministic match truth is established solely by the match engine, never by Qdrant or language models**.

---

## 2. Directory Structure

```
ingestion/knowledge/
├── README.md               # This documentation
├── sources.yml             # Upstream official sources registry (MCC Laws, ICC Playing Conditions, Cricsheet)
├── approved/               # Reviewed & approved knowledge notes eligible for production
│   └── cricket/            # 23 atomic notes (terminology, interval interpretation, format context)
├── drafts/                 # Staging & experimental knowledge notes (dev collection only)
│   └── cricket/            # 2 draft notes (Super Over tie-breaker, Tamil glossary)
├── evaluation/             # Retrieval evaluation datasets
│   └── cricket_eval_queries.json  # 24 labelled queries (21 in-scope, 3 negative/leakage tests)
├── ids.py                  # Deterministic content-addressed SHA-256 and UUIDv5 identifiers
├── loader.py               # Markdown and YAML frontmatter parser
├── validator.py            # Source governance, URL validity, and review status policy enforcer
├── chunker.py              # Semantic markdown chunker with token limit enforcement (120 token ceiling)
├── embeddings.py           # EmbeddingProvider abstraction & local FastEmbed ONNX implementation
├── qdrant_store.py         # Qdrant client adapter with payload filtering
├── ingest.py               # Ingestion orchestrator with dry-run and apply modes
├── retrieve.py             # Typed retrieval service with sport and review_status filtering
├── evaluate.py             # Precision & isolation evaluation harness (HitRate@3, MRR@5)
└── cli.py                  # Operational CLI (validate, preview, ingest, retrieve, evaluate)
```

---

## 3. Embedding Profile

| Parameter | Value |
|---|---|
| Provider | FastEmbed (Local CPU ONNX) |
| Model ID | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| Immutable Revision | `faf4aa4225822f3bc6376869cb1164e8e3feedd0` |
| Output Dimensions | 384 |
| Distance Metric | Cosine |
| Sequence Length | 128 max tokens (Chunk ceiling: 120 tokens, Target: 95 tokens) |
| License | Apache-2.0 |

---

## 4. Collections and Governance Gates

| Collection Name | Eligible Content | Review Status Required | Drafts Allowed? |
|---|---|---|---|
| `fancue_cricket_knowledge_v1` | Production-ready corpus | `approved` | **STRICTLY NO** |
| `fancue_cricket_knowledge_dev_v1` | Staging & development | `approved` (+ `draft` opt-in) | Yes (with `--allow-draft`) |

---

## 5. CLI Operations

### Validate Corpus and Sources
```bash
python -m ingestion.knowledge.cli validate
```

### Preview Semantic Chunking and Token Counts
```bash
python -m ingestion.knowledge.cli preview
```

### Dry-Run Ingestion (Default)
```bash
python -m ingestion.knowledge.cli ingest --collection fancue_cricket_knowledge_dev_v1
```

### Apply Ingestion to Dev Collection
```bash
python -m ingestion.knowledge.cli ingest --apply --collection fancue_cricket_knowledge_dev_v1
```

### Execute Single Retrieval Query
```bash
python -m ingestion.knowledge.cli retrieve "What is Current Run Rate?" --collection fancue_cricket_knowledge_dev_v1
```

### Run Retrieval Evaluation Suite
```bash
python -m ingestion.knowledge.cli evaluate --collection fancue_cricket_knowledge_dev_v1
```
