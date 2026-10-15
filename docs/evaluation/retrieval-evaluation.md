# FanCue Evaluation: Retrieval Quality & Isolation Report

> **Production boundary:** These results are from the documented development collection (`fancue_cricket_knowledge_dev_v1`). The current Render configuration disables retrieval, so this report is not evidence that Qdrant is active in production or on the deployed catch-up path.

> **Document ID:** EVAL-004  
> **Evaluation Date:** 2026-10-11  
> **Status:** Accepted (Gate Passed)  
> **Target Collection:** `fancue_cricket_knowledge_dev_v1`  

---

## 1. Executive Summary

Phase 04 established a fixed evaluation benchmark (`ingestion/knowledge/evaluation/cricket_eval_queries.json`) comprising 24 test cases (21 in-scope domain queries and 3 negative/leakage queries).

The evaluation measured recall precision, rank order, and domain isolation against the 67 indexed chunks of the curated cricket knowledge base.

---

## 2. Benchmark Metrics

| Metric | Measured Value | Phase 04 Acceptance Target | Status |
|---|---|---|---|
| **HitRate@3** | **100.00%** | >= 80.0% | **PASSED** |
| **MRR@5** | **0.9524** | > 0.70 | **PASSED** |
| **Wrong Sport Leakage** | **0** | Exactly 0 | **PASSED** |
| **Wrong Language Leakage** | **0** | Exactly 0 | **PASSED** |
| **Draft Leakage in Prod Path** | **0** | Exactly 0 | **PASSED** |
| **Average Query Latency** | **~155 ms** | < 500 ms (CPU) | **PASSED** |

---

## 3. Detailed Query Breakdown

### Sample In-Scope Queries (Top Rank Hits)

1. **"What is the formula for current run rate?"**  
   - *Rank 1 Hit:* `doc_current_run_rate_formula_12208c6c2e9a` (Score: 0.6176)  
   - *Passage:* "`CRR = total_runs / overs_bowled`..."

2. **"Why do wides and no-balls require the bowler to re-bowl the delivery?"**  
   - *Rank 1 Hit:* `doc_wides_and_noballs_3447448060cf` (Score: 0.5891)  
   - *Passage:* "Both infractions award at least one automatic penalty run to the batting team..."

3. **"What happens on a Free Hit delivery after a no-ball in limited overs?"**  
   - *Rank 1 Hit:* `doc_free_hit_on_noballs_570e3ebce25c` (Score: 0.6912)  
   - *Passage:* "The striker cannot be dismissed by any method credited to the bowler..."

4. **"Why is Required Run Rate (RRR) only valid during the second innings chase?"**  
   - *Rank 1 Hit:* `doc_required_run_rate_scope_6d5684c84ee0` (Score: 0.6284)  
   - *Passage:* "Crucially, Required Run Rate is strictly defined only during the second innings..."

### Isolation & Negative Cases

1. **Football Offside Query (`neg01`):**  
   - Queried against cricket corpus with `sport=football`.  
   - *Result:* Zero hits returned (`status=FILTER_EMPTY`). Perfect isolation.
2. **Player Gossip & Personal Salaries (`neg02` / `neg03`):**  
   - Returned low semantic similarity without match, confirming unindexed gossip is not grounded.
