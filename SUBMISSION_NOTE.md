# FanCue — Dream11 FDE Internship Submission

Fans often return to a cricket match mid-innings and see a score without the context of how it changed. FanCue lets a fan select a missed interval from a supported historical match and returns the score change, notable recorded events, and evidence behind them.

A deterministic engine computes match facts from Cricsheet delivery records. A Groq-hosted **openai/gpt-oss-20b** model drafts the explanation; a rules-based verifier checks supported numeric, player-name, and citation claims. If generation is unavailable or a draft is rejected, FanCue returns a deterministic, fact-based summary.

**Scope:** FanCue replays historical fixtures. Near-live discovery and scorecards are separate aggregate data; they do not provide live ball-by-ball catch-up. A real live delivery-by-delivery experience would require a licensed feed.

**AI tools:** Groq-hosted **openai/gpt-oss-20b** for narrative generation; Google Antigravity for AI-assisted development; Google Stitch for UI design. Qdrant retrieval is optional but disabled by the current Render blueprint, so it is not claimed as part of the deployed catch-up path.

**Validation status:** Automated CI passed on the recorded revision. The public Vercel-to-Render catch-up journey still requires a manual browser smoke test; public end-to-end acceptance is not claimed.
