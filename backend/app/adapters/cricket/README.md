# backend/app/adapters/cricket/

Cricket-specific event parser, normalizer, and state reconstruction logic.

This adapter is the only location for cricket-specific business logic.
It consumes Cricsheet JSON format and produces normalized events and state
snapshots consumed by the match engine.

Cricket concepts handled here (and only here):
- Innings, overs, deliveries
- Legal-ball counting (excludes wides and no-balls)
- Runs (batting, extras: wides, no-balls, byes, leg-byes, penalties)
- Wickets and partnerships
- DLS-affected matches (documented as limitation if not handled)

See: https://cricsheet.org/format/json/

**Phase 00: Not implemented. Implementation begins Phase 03.**
