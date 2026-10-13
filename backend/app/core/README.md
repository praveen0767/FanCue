# backend/app/core/

Application startup, configuration, logging, and dependency injection.

Responsibilities:
- Load configuration from environment variables (via `python-dotenv`)
- Initialize structured logging
- Provide FastAPI dependency injection functions (e.g., Qdrant client, LLM client)
- Application lifespan event handlers (startup / shutdown)

**Phase 00: Not implemented. Implementation begins Phase 03.**
