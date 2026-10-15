# ADR-009: Production Deployment Architecture and Service Boundaries

- **Status:** Approved
- **Date:** 2026-10-12
- **Deciders:** FanCue Engineering
- **Consults:** AGENTS.md, ADR-002, ADR-004, ADR-005, ADR-007

---

## Context

FanCue has a local full-stack workflow with a deterministic cricket match engine, canonical evidence packet assembly, claim verification, deterministic fallback, FastAPI backend, and React/Vite frontend. Qdrant retrieval exists as an optional subsystem; the current Render blueprint disables it. This ADR records the intended deployment boundaries and is superseded where its provider settings differ from the current Render blueprint.

To support public or remote deployment without compromising match state authority, secret isolation, or determinism, a production deployment topology must be defined.

---

## Decision

We establish the following three-tier deployment topology:

```
[ Fan Browser ]
      │  HTTPS
      ▼
┌──────────────────────────┐
│  Static Frontend Host    │  Vite/React SPA (Vercel / Cloudflare Pages / Nginx)
│  (No secrets, CDN edge)  │  Build-time: VITE_API_BASE_URL
└─────────────┬────────────┘
              │  HTTPS REST
              ▼
┌──────────────────────────┐
│  Containerized Backend   │  FastAPI / Python 3.12 on uvicorn (Cloud Run / ECS / Fly)
│  (Stateless, Bundled Data)│  - Match Engines (Cricsheet fixtures in container)
│                          │  - Claim Verifier & Evidence Builder
│                          │  - In-memory sliding rate limiter on /catchup
└──────────┬────┬──────────┘
           │    │
           │    └──────────────────────┐
           ▼ (HTTPS)                   ▼ (HTTPS)
┌──────────────────────┐    ┌──────────────────────┐
│  Remote Qdrant Cloud │    │  LLM Provider API    │
│  Collection:         │    │  (OpenAI / Anthropic)│
│  fancue_cricket_     │    │  Strictly backend    │
│  knowledge_v1        │    │  auth; 30s timeout   │
└──────────────────────┘    └──────────────────────┘
```

### 1. Service Boundaries

| Component | Hosting Paradigm | Runtime Configuration | Access Policy |
|---|---|---|---|
| **Frontend** | Static SPA on CDN edge (Vercel, Cloudflare, S3+CloudFront, or Dockerized Nginx) | `VITE_API_BASE_URL` | Public HTTPS; Zero backend API keys or secrets in bundle. |
| **Backend API** | Stateless containerized Python 3.12 (`backend.app.main:app`) on Linux | `FANCUE_ENV=production`, `ALLOWED_ORIGINS=https://fan-cue.vercel.app`, `LLM_PROVIDER=groq`, `GROQ_API_KEY` | Public HTTPS behind TLS termination; exact-origin CORS allowlist; rate limiting. |
| **Vector DB** | Optional Qdrant contextual retrieval | Current Render setting: `FANCUE_RETRIEVAL_ENABLED=false`; enable only deliberately and revalidate before claiming production retrieval. | Not on the current production catch-up path. |
| **LLM Provider** | Groq API (current blueprint) | Model: `openai/gpt-oss-20b` (`GROQ_MODEL`) | Provider key remains server-side; live response behaviour still needs public smoke validation. |

### 2. Security Boundaries & Assumptions

1. **Deterministic Authority:**
   The deterministic match engine remains the sole truth authority for match scores. Neither the LLM nor the vector database can alter score state.
2. **Secret Isolation:**
   Provider keys (including `GROQ_API_KEY`) are stored strictly in server-side environment variables and are never forwarded to the frontend or included in build bundles.
3. **No Silent Storage Fallback in Production:**
   When `FANCUE_ENV=production`, `QdrantStore` must reject silent fallbacks to local directory or in-memory storage. Connection failure must raise `QdrantStoreError` and engage the graceful fallback path.
4. **Sanitized Public Responses:**
   API error responses use the structured `ErrorResponse` model with request correlation IDs. Tracebacks, SQL queries, prompt templates, and credentials are never returned to clients.
5. **CORS Hardening:**
   `ALLOWED_ORIGINS` must strictly match deployed frontend hostnames. Wildcard origins (`*`) and credentials sharing are forbidden.
6. **Rate Limiting & Proxy Trust:**
   The public `/catchup` endpoint is protected by an in-memory sliding-window client-IP rate limiter (60 requests/minute per client IP) returning `429 RATE_LIMIT_EXCEEDED` on breach.
   - *Trusted Proxy Awareness:* Arbitrary client-supplied `X-Forwarded-For` headers are explicitly distrusted and ignored unless the immediate peer connection originates from an authorized proxy in `TRUSTED_PROXIES`.
   - *Multi-Instance Limitation Disclosure:* In-memory rate limiting operates per container process. In a horizontally scaled cluster, edge rate limiting (e.g., Cloudflare WAF, API Gateway) or centralized token storage (e.g. Redis when justified under AGENTS.md §12) must be configured if strictly enforced global cross-instance limits are required.

### 3. Separation of Knowledge Collections

- **Development:** `fancue_cricket_knowledge_dev_v1`
- **Production:** `fancue_cricket_knowledge_v1`
Development test runs and CI checks must never mutate or clear the production knowledge collection.

---

## Consequences

### Positive
- Completely decoupled static frontend and stateless backend allows independent deployment, caching, and horizontal scaling.
- No heavy infrastructure (Redis, message queues, relational databases) required for Phase 09, honoring AGENTS.md §12.
- Deterministic fallback provides a non-LLM response path when generation fails; it does not guarantee total service availability.

### Negative / Limitations
- Single-instance in-memory rate limiting applies per container instance; distributed multi-instance deployment will require an edge gateway or Redis if uniform cross-instance rate limiting is demanded later.
- Match data updates require container redeployment (intentional for verified historical match data).
