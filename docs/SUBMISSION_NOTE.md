# FanCue — Dream11 FDE Intern Submission

Fans step away mid-match and return to a scoreboard that shows what the score is, not what changed while they were gone. FanCue lets a fan select a historical cricket match and missed whole-over interval, then returns the score delta, consequential moments, and inspectable ball-level evidence.

A deterministic engine reconstructs runs, wickets, legal balls, extras, and interval changes from recorded Cricsheet deliveries. A configured Groq-hosted LLM can draft the narrative; a rules-based verifier checks supported claims, and a fact-based deterministic summary is used when generation is disabled, unavailable, or rejected.

**Honest scope:** FanCue replays historical matches. The near-live integration provides match discovery and aggregate scorecards, not a delivery-by-delivery live recap. Live ball-by-ball catch-up would require a licensed feed.

**AI tools used:** Groq-hosted `openai/gpt-oss-20b` for optional narrative generation; Google Antigravity for AI-assisted development; Google Stitch for UI design. Qdrant was used for development retrieval experiments, but `render.yaml` sets `FANCUE_RETRIEVAL_ENABLED=false`; retrieval is off in the current source-controlled Render configuration.

**Validation:** CI tests do not establish that the live Vercel-to-Render user journey succeeds. The deployed browser path, actual Render secret values, and first-click cold-start experience still require a manual check using [the acceptance runbook](PUBLIC_DEMO_ACCEPTANCE.md).
