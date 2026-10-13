# tests/evaluation/

Retrieval evaluation sets and evaluation runner.

Contains known-relevant question sets used to measure Qdrant retrieval quality.

Each question set includes:
- `question`: A natural-language query as a fan might ask
- `sport`: "cricket" or "football"
- `language`: ISO 639-1 code
- `expected_doc_ids`: List of document IDs expected in the top-K results

Evaluation metric: recall@10 — the proportion of expected documents
found in the top 10 retrieved results.

Target: >= 80% recall@10 before Phase 05 begins.

**Phase 00: No evaluation sets yet. Created in Phase 04.**
