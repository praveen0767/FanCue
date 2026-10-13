# FanCue Submission Note

FanCue is an AI-powered, evidence-grounded cricket match catch-up platform built with FastAPI and React/Vite.

### Architecture & Deterministic Design
Match state reconstruction is strictly deterministic. A Python sport engine processes authoritative Cricsheet ball-by-ball delivery ledgers (CC-BY 4.0), computing exact scores, over boundaries, extras, and wickets. The deterministic engine is the sole truth authority; AI never mutates match state.

### AI Boundaries & Verification
For historical intervals, FanCue retrieves contextual cricket knowledge via Qdrant and generates natural-language catch-ups with OpenAI GPT-4o-mini. Generated text passes an automated claim verifier auditing numeric claims, player names, and citations against inspectable evidence packets. If verification fails or the LLM is unreachable, FanCue serves an immediate, auditable deterministic fallback summary.

### Verified Functionality
- Full Historical Replay journey: fixture selection, interval definition, state delta calculation, and verified evidence-backed catch-up.
- Near-live match discovery via cached CricketData.org adapter displaying aggregate scorecards.

### Known Limitations
- Near-live matches do not support interval storytelling because external scorecards lack delivery-level ball-by-ball ledgers; honest notices inform the user.
- Production hosting configuration files (`render.yaml`, `vercel.json`) are validated, but public hosting credentials require provider environment configuration.
