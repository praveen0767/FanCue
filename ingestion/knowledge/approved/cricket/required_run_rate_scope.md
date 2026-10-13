---
id: required_run_rate_scope
title: "Required Run Rate (RRR) Scope and Limitations"
sport: cricket
language: en
topic: score_interpretation
knowledge_type: interval_interpretation
review_status: approved
source_type: official_reference
source_name: "ICC Men's One Day International Playing Conditions"
source_url: "https://www.icc-cricket.com/about/cricket/rules-and-regulations/playing-conditions"
source_revision: "2026-10-01"
citation_locator: "ICC Men's ODI Playing Conditions Clause 16"
license: "CC-BY-4.0"
permitted_use: open_attribution
source_check_status: verified
document_revision: "1.0.0"
effective_from: "2026-10-01"
effective_to: null
---

# Required Run Rate (RRR) Scope and Limitations

Required Run Rate (RRR) is the average number of runs per remaining over that the batting team must achieve to win a match when chasing a target.

The mathematical formula for Required Run Rate is:
`RRR = runs_needed_to_win / overs_remaining`
where `runs_needed_to_win = (first_innings_total + 1) - current_score`.

Crucially, Required Run Rate is strictly defined only during the second innings (the chase) in limited-overs matches or fourth innings in multi-innings matches. It is completely inapplicable and undefined during the first innings of a match because no target has yet been set.

When explaining match intervals, FanCue must never cite or report an RRR during the first innings, and must verify that both `runs_needed` and `overs_remaining` are non-zero before calculating an RRR during the second innings.
