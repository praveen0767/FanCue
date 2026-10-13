# backend/app/adapters/football/

Football-specific event parser, normalizer, and state reconstruction logic.

This adapter is deferred to Phase 08. It must not share event types or scoring
logic with the cricket adapter.

Football concepts to be handled here:
- Match periods (first half, second half, extra time, penalties)
- Match clock (additive notation, e.g., 90+5)
- Goals and own-goals
- Yellow cards, red cards, second yellows
- Substitutions with player IDs

Candidate data source: StatsBomb Open Data (license review required)
See: https://github.com/statsbomb/open-data

**Phase 00: Not implemented. Implementation deferred to Phase 08.**
**Do not start football implementation before Phase 07 cricket gate passes.**
