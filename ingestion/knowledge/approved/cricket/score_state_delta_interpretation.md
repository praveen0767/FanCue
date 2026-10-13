---
id: score_state_delta_interpretation
title: "Interpreting Score-State Deltas"
sport: cricket
language: en
topic: score_interpretation
knowledge_type: interval_interpretation
review_status: approved
source_type: fancue_authored
source_name: "FanCue Interval Specification"
source_url: "https://github.com/fancue/fancue"
source_revision: "1.0.0"
citation_locator: "FanCue Phase 01 Semantics"
license: "CC-BY-4.0"
permitted_use: open_attribution
source_check_status: verified
document_revision: "1.0.0"
effective_from: "2026-10-11"
effective_to: null
---

# Interpreting Score-State Deltas

A score-state delta is the exact mathematical difference between two authoritative match states bounding a historical interval.

In FanCue, an interval is defined by an exclusive start boundary (state after over `start_after_over`) and an inclusive end boundary (state after over `end_after_over`). The delta computes:
1. `runs_delta`: runs scored during the interval (end runs minus start runs).
2. `wickets_delta`: wickets fallen during the interval (end wickets minus start wickets).
3. `overs_completed_delta`: whole overs bowled during the interval.
4. `deliveries_count`: total physical deliveries, including illegal balls.
5. `legal_deliveries_count`: count of fair balls completing overs.
6. `interval_run_rate`: runs scored per over across the selected interval.

A score-state delta answers what happened mechanically while the fan was away. It forms the foundational ground truth upon which any subsequent narrative explanation must strictly rely.
