# exemplar

In manuscript culture, the exemplar was the authoritative copy scribes worked from. This repository is that for Codex Publicus case documents: the reference format that the data pipelines produce and the viewers render.

It defines, independently of any one implementation:

- **The court record key**: a deterministic, docket-anchored identifier for every US court decision and for each separate opinion within it (`us/{court}/{docket}/{decided}[/{role}.{author}][@{revised}]`), following the FRBR work/expression split used by ECLI, URN:LEX and Akoma Ntoso.
- **An Akoma Ntoso judgment profile**: how a US decision is represented in OASIS LegalDocML (Akoma Ntoso), including separate opinions, parallel printings of the same decision, page anchors into scanned volumes, and decisions whose text was not released.
- **Machine-checkable schemas** for the profile and for the viewer's JSON sidecar.
- **Test vectors** any implementation can run to prove conformance.

## Layout

| Path | Contents |
|---|---|
| `spec/` | Normative specifications (MUST/SHOULD language): the court record key, the Akoma Ntoso profile |
| `schema/` | Schematron rules layered on the Akoma Ntoso schema; JSON Schema for the viewer sidecar |
| `vectors/` | Language-neutral JSON test vectors: key computation, parsing, rejection, valid and invalid documents |
| `examples/` | Complete sample documents built from Caselaw Access Project data |

## Consumers

- `codexpublicus/stare`: builds documents from the Caselaw Access Project corpus.
- `codexpublicus/gorsuch-library`: builds documents for the Gorsuch corpus and computes court record keys.
- The shared Codex Publicus viewer: renders documents in this format.

Consumers pin a release tag. Releases follow semantic versioning: a change to how identifiers are computed, or to a document's required structure, is a major version.

## Status

Early. Nothing here is stable yet. The court record key grammar comes from gorsuch-library's research (`docs/research/2026-09-25-case-identifier-recommendation.md`) and moves here as the normative source.
