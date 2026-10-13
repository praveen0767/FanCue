# data/

## Purpose

This directory is the designated location for authoritative match data
used by the FanCue deterministic match engine.

**No data files are committed to this repository.**

All datasets must come from appropriately licensed sources. Before downloading
or using any dataset, the applicable license must be reviewed and recorded.

---

## Licensing and Provenance Requirements

Every dataset used in this project must have a recorded entry in
`data/sources.yml` (created when the first dataset is approved) containing:

| Field | Description |
|---|---|
| `source_name` | Human-readable name of the source |
| `source_url` | Canonical URL of the dataset or its license page |
| `license` | SPDX identifier or full license name |
| `permitted_use` | `non_commercial` / `commercial` / `evaluation_only` |
| `retrieved_date` | ISO 8601 date of download |
| `revision_id` | Version or commit hash of the downloaded snapshot |
| `attribution` | Attribution text required by the license |

---

## Candidate Data Sources

### Cricket

| Source | URL | Notes |
|---|---|---|
| Cricsheet | https://cricsheet.org/ | Ball-by-ball data in YAML and JSON formats |
| Cricsheet licensing | https://cricsheet.org/licensing/ | **Review before downloading** |
| Cricsheet JSON format | https://cricsheet.org/format/json/ | Format specification for the JSON variant |

Cricsheet publishes ball-by-ball data under a Creative Commons license.
The exact license variant (CC-BY, CC-BY-SA, etc.) and any attribution
requirements must be confirmed at https://cricsheet.org/licensing/ before use.

### Football

| Source | URL | Notes |
|---|---|---|
| StatsBomb Open Data | https://github.com/statsbomb/open-data | Event-level data for selected matches |
| StatsBomb license | https://github.com/statsbomb/open-data/blob/master/LICENSE.pdf | **Review before downloading** |

StatsBomb open data is provided for non-commercial use with attribution.
Confirm current terms before ingesting any data.

---

## What Is NOT Permitted Here

- Do **not** commit raw dataset files to Git.
- Do **not** invent, fabricate, or extrapolate match data.
- Do **not** use data whose license has not been reviewed and recorded.
- Do **not** redistribute data in a way that violates its source license.
- Do **not** create placeholder "sample" match files that impersonate real matches.

---

## Directory Structure (populated in Phase 02/03)

```
data/
  README.md         <- this file
  sources.yml       <- provenance registry (created Phase 02)
  raw/              <- downloaded originals, gitignored
  processed/        <- normalised engine-ready format, gitignored
```

`raw/` and `processed/` are listed in `.gitignore`.
Only `README.md` and `sources.yml` are tracked by Git.
