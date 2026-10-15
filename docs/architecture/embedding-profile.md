# FanCue Architecture: Embedding Profile Specification

> **Deployment scope:** This profile supports optional Qdrant contextual retrieval. Current Render configuration disables retrieval, so this embedding stack is not on the deployed catch-up critical path.

> **Document ID:** ARCH-009  
> **Status:** Implemented & Pinned (Phase 04)  
> **Author:** Principal AI Systems Engineer  

---

## 1. Selected Profile

| Attribute | Specification |
|---|---|
| Model Name | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| Upstream Repository | Hugging Face: `Qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q` |
| Immutable Git Commit | `faf4aa4225822f3bc6376869cb1164e8e3feedd0` |
| Runtime Provider | FastEmbed (`fastembed==0.9.0`) |
| Execution Engine | ONNX Runtime CPU (`onnxruntime==1.31.0`) |
| Vector Dimension | 384 |
| Distance Metric | Cosine Similarity |
| Usable Context Length | 128 input tokens |
| Target Chunk Budget | 70–100 tokens (max ceiling 120 tokens) |
| License | Apache-2.0 |

---

## 2. Selection Rationale & Hardware Footprint

1. **Local Self-Containment:** Runs entirely on local CPU via optimized quantized ONNX weights (220 MB total disk footprint). Requires zero external API keys (no OpenAI, Cohere, or Google embedding charges).
2. **Deterministic Output:** Generates reproducible floating-point vectors on local hardware.
3. **Multilingual Architecture:** Supports 50+ languages, enabling future evaluation of Tamil catch-up notes without swapping model weights or collections.
4. **No Artificial Query Prefixes:** Does not require prompt engineering prefixes such as `query:` or `passage:`, reducing cognitive complexity and error modes.

---

## 3. Output Validation & Safety

The `FastEmbedProvider` wrapper in `ingestion/knowledge/embeddings.py` enforces:
1. Exact vector dimension assertions (`len(vec) == 384`).
2. Finite float verification (`math.isfinite(val)` for every float).
3. Non-empty text guarantees.
