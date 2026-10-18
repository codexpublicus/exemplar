# exemplar

In manuscript culture, the exemplar was the authoritative copy scribes worked from. This repository is that for Codex Publicus case documents: the reference format that the data pipelines produce and the viewers render.

It defines, independently of any one implementation:

- **The court record key**: a deterministic, docket-anchored identifier for every US court decision and for each separate opinion within it (`us/{court}/{docket}/{decided}[~n][/{role}[.{author}]][@{revised}]`), specified in [`spec/court-record-key.md`](spec/court-record-key.md), following the FRBR work/expression split used by ECLI, URN:LEX and Akoma Ntoso.
- **An Akoma Ntoso judgment profile**: how a US decision is represented in OASIS LegalDocML (Akoma Ntoso), including separate opinions, parallel printings of the same decision, page anchors into scanned volumes, and decisions whose text was not released, specified in [`spec/akoma-ntoso-profile.md`](spec/akoma-ntoso-profile.md).
- **Machine-checkable schemas** for the profile and for the viewer's JSON sidecar.
- **The court registry**: the court codes the key uses and the docket profile for each, built from a pinned snapshot of Free Law Project's courts-db.
- **Test vectors** any implementation can run to prove conformance.

## Layout

| Path | Contents |
|---|---|
| `spec/` | Normative specifications (MUST/SHOULD language): the court record key, the Akoma Ntoso profile |
| `registry/` | The court registry (`courts.json`), its build script, and the vendored courts-db snapshot it is built from |
| `schema/` | JSON Schema for the court registry; the vendored Akoma Ntoso 1.0 XML Schema (`schema/akn/1.0/`); Schematron rules layered on it; JSON Schema for the viewer sidecar |
| `vectors/` | Language-neutral JSON test vectors: key computation, parsing, rejection, valid and invalid documents |
| `examples/` | Complete sample documents built from Caselaw Access Project data |
| `tests/` | Checks that the vectors agree with the specs' grammars and rules |

## Consumers

- `codexpublicus/stare`: builds documents from the Caselaw Access Project corpus.
- `codexpublicus/gorsuch-library`: builds documents for the Gorsuch corpus and computes court record keys.
- The shared Codex Publicus viewer: renders documents in this format.

Consumers pin a release tag. Releases follow semantic versioning: a change to how identifiers are computed, or to a document's required structure, is a major version.

## Akoma Ntoso schema

`schema/akn/1.0/` holds the official Akoma Ntoso 1.0 XML Schema, `akomantoso30.xsd`, and the `xml.xsd` it imports, both unchanged from <https://docs.oasis-open.org/legaldocml/akn-core/v1.0/os/part2-specs/schemas/> (Akoma Ntoso Version 1.0, OASIS Standard, 29 August 2018), retrieved 2026-10-18. `schema/akn/1.0/source.json` records each file's URL and SHA-256 and the notice each file states: `akomantoso30.xsd` states OASIS copyright and that OASIS provides the schema under CC BY 4.0; `xml.xsd` states no license.

## Court registry

`registry/courts.json` is the court registry the court record key spec references (section 10). Its version is a CalVer date (`2026.10.18`), separate from the spec's SemVer version: adding courts is a new registry version, and a release tag pins both. It holds 2,802 courts, every US court in courts-db, each with the docket profile this registry assigns it.

Source and provenance: the court codes are the ids in Free Law Project's courts-db, <https://github.com/freelawproject/courts-db>, file `courts_db/data/courts.json` at commit `c22604dff8b6819d022cc5ddfd6d9080101149e3` (2026-10-07), retrieved 2026-10-18. That file is vendored unchanged at `registry/sources/courts-db/courts.json`, with the repository's LICENSE file beside it; courts-db's LICENSE states the BSD 2-Clause License. The registry's `source` block records the same facts and the vendored file's SHA-256, and its `excluded` block lists the seven courts-db ids left out and why.

To rebuild after vendoring a newer courts-db snapshot, update the pin in `registry/build_courts.py` and run `uv run python registry/build_courts.py`. The registry is append-only: a rebuild may add courts, and must not drop or change one already published.

There is no judge registry here. Judge slugs come from a registry the consumer supplies by URI (spec section 10.2); the vectors use a small fixture in its place.

## Status

Early. Nothing here is stable yet. The court record key spec is at 0.1.0 (draft), with court registry 2026.10.18; it moved here from gorsuch-library's research (`docs/research/2026-09-25-case-identifier-recommendation.md`) and is now the normative source. The Akoma Ntoso profile is at 0.1.0 (draft); its open questions are listed in its section 19.

## Checks

```
uv run pytest
```

The checks read the ABNF and the regex straight out of the spec, so a grammar change that the vectors don't follow fails. They also validate `registry/courts.json` against its schema, rebuild it from the vendored courts-db snapshot and compare, check the snapshot against its SHA-256 pin, and check that every court code a vector resolves is in the registry.

For the Akoma Ntoso profile, they validate every `examples/**/*.akn.xml` against the vendored Akoma Ntoso 1.0 schema (after checking its files against their pins), check each example's work, expression and part URIs against the court record key rules, and check that the example quoted in the profile is identical to `examples/minimal/`.
