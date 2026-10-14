# FanCue — Data Attribution & Licensing Notice

FanCue uses recorded match data to power deterministic match-state reconstruction and historical interval summaries. Licence statements below apply to the specific formats identified; do not assume one licence applies to every Cricsheet format.

---

## Cricsheet historical fixtures

- **Source:** [Cricsheet](https://cricsheet.org/)
- **Data format used by the registered historical fixtures:** Cricsheet JSON, format version 1.3.0
- **Licence recorded for these JSON fixtures:** Open Data Commons Attribution License (ODC-By v1.0)
- **Licence reference:** [ODC-By v1.0](https://opendatacommons.org/licenses/by/1.0/)
- **Canonical source licensing guidance:** [https://cricsheet.org/licensing/](https://cricsheet.org/licensing/)

### Attribution

> Data provided by Cricsheet (https://cricsheet.org/), licensed under the Open Data Commons Attribution License (ODC-By v1.0).

Retain the original attribution and notices when using or redistributing datasets or products where required by the applicable licence. Recheck Cricsheet's current licensing guidance and the original archive metadata before redistributing data or making commercial use.

### Registered fixture metadata

The project provenance registry records these expected fixtures and hashes:

| Match ID | Registered format | Teams | Fixture SHA-256 |
|---|---|---|---|
| `1529229` | ODI | India vs West Indies | `8163493c726d43e0865b6041c06bfa85f764d908e337d510108cdcf36e66c12f` |
| `1552779` | T20 | India vs Pakistan | `99b2df4d4ebcaa328834ec101776a201c679b5d89b1a604241c504b0d9bb3e2b` |

The registry also records archive SHA-256 `282b4543e36aae90bf14ab9e2cbd0f8829dfdd8b3e4a97b711b0336d69b5ba74` for the recently-added JSON archive snapshot. These hashes are provenance metadata, not proof that the files exist in a given deployment. Verify the fixtures actually packaged in the build before releasing.

### Fixture handling

The original JSON files are listed in `data/sources.yml` and expected at `data/raw/`. Verify actual fixture availability and hashes during ingestion/build validation. Never fabricate data to make a demo work.

---

## Football data source (provisional)

- **Candidate:** [StatsBomb Open Data](https://github.com/statsbomb/open-data)
- **Status:** Candidate only; the repository must not imply football data is integrated until actual ingestion and licensing review are completed.
- **Requirement:** Review the current repository licence and attribution requirements before downloading, redistributing, or using commercially.

---

## Operational policy

- Maintain source URL, retrieval timestamp, dataset revision, format, licence and SHA-256 for each fixture.
- Review licence terms for the actual file format and use case; terms may vary by format.
- Software licence and dataset licence are separate.
- Do not redistribute any dataset where the applicable terms do not permit it.
- Keep secrets out of fixtures, provenance files, logs and browser responses.
