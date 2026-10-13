# backend/app/api/

FastAPI routers and HTTP endpoint definitions.

This is a thin layer only. No business logic belongs here.
Responsibilities:
- Define API routes using FastAPI `APIRouter`
- Validate incoming request bodies against Pydantic schemas from `app/schemas/`
- Delegate all processing to domain services in other modules
- Return typed response models

**Phase 00: Not implemented. Implementation begins Phase 03.**
