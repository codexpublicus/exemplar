# exemplar

In manuscript culture, the exemplar was the authoritative copy scribes worked from. This repository is that for Codex Publicus case documents: the reference format that the data pipelines produce and the viewers render.

It defines, independently of any one implementation:

- **The court record key**: a deterministic, docket-anchored identifier for every court decision and for each separate opinion within it (`{jurisdiction}/{court}/{docket}/{decided}[~n][/{role}[.{author}]][@{revised}]`, where `{jurisdiction}` is a jurisdiction code: `us`, a territory's `pr`, a historical sovereign's `england`), specified in [`spec/court-record-key.md`](spec/court-record-key.md), following the FRBR work/expression split used by ECLI, URN:LEX and Akoma Ntoso.
- **An Akoma Ntoso judgment profile**: how a US decision is represented in OASIS LegalDocML (Akoma Ntoso), including separate opinions, parallel printings of the same decision, page anchors into scanned volumes, and decisions whose text was not released, specified in [`spec/akoma-ntoso-profile.md`](spec/akoma-ntoso-profile.md).
- **Machine-checkable schemas** for the profile and for the viewer's JSON sidecar.
- **The court registry**: the court codes the key uses, with each court's jurisdiction code and docket profile, built from a pinned snapshot of Free Law Project's courts-db; the registry code for each court the Caselaw Access Project names; and the reporter variant map, built from a pinned snapshot of Free Law Project's reporters-db.
- **Test vectors** any implementation can run to prove conformance.

## Layout

| Path | Contents |
|---|---|
| `spec/` | Normative specifications (MUST/SHOULD language): the court record key, the Akoma Ntoso profile |
| `registry/` | The court registry (`courts.json`), its build script, and the vendored courts-db snapshot it is built from; CAP's courts mapped to registry codes (`cap-courts.json`); the reporter registry (`reporters.json`): official reporters, editions of one report, and the dates each volume of the Supreme Court's reporters prints; the reporter variant map (`reporter-variants.json`), its build script, and the vendored reporters-db snapshot it is built from |
| `schema/` | JSON Schema for the court registry, the CAP court table, the reporter registry, the reporter variant map and a key publisher's errata list (`crk-errata.schema.json`, CRK section 13.4); the vendored Akoma Ntoso 1.0 XML Schema (`schema/akn/1.0/`); the profile's Schematron rules (`profile.sch`); JSON Schema for the viewer sidecar (`sidecar.schema.json`) |
| `vectors/` | Language-neutral JSON test vectors: key computation, parsing, rejection, valid and invalid documents and sidecars |
| `examples/` | Sample documents built from Caselaw Access Project data, each with its viewer sidecar: `minimal/`, the hand-built excerpt the profile quotes, and `cap/`, complete documents generated from CAP cases |
| `validator/` | The reference validator, which runs the XSD, the Schematron rules and the sidecar schema, and the vendored SchXslt2 transpiler it uses |
| `tests/` | Checks that the vectors agree with the specs' grammars and rules |

## Consumers

- `codexpublicus/stare`: builds documents from the Caselaw Access Project corpus.
- The Gorsuch library (<https://gorsuch.codexpublicus.org>): builds documents for the Gorsuch corpus and computes court record keys.
- The shared Codex Publicus viewer: renders documents in this format.

Consumers pin a release tag. Releases follow semantic versioning: a change to how identifiers are computed, or to a document's required structure, is a major version.

## Akoma Ntoso schema

`schema/akn/1.0/` holds the official Akoma Ntoso 1.0 XML Schema, `akomantoso30.xsd`, and the `xml.xsd` it imports, both unchanged from <https://docs.oasis-open.org/legaldocml/akn-core/v1.0/os/part2-specs/schemas/> (Akoma Ntoso Version 1.0, OASIS Standard, 29 August 2018), retrieved 2026-10-18. `schema/akn/1.0/source.json` records each file's URL and SHA-256 and the notice each file states: `akomantoso30.xsd` states OASIS copyright and that OASIS provides the schema under CC BY 4.0; `xml.xsd` states no license.

## Schematron rules and the viewer sidecar

`schema/profile.sch` holds the profile's rules that the XML Schema can't express: every rule section 16.2 of the profile assigns to Schematron, each assertion message starting with the rule id it enforces (`[AKN-31]`), or the section number for a requirement without one. Its query binding is `xslt2`. Open question O7 of the profile is still open; the rules implement the 0.6.0 text, which takes its option (a), and check nothing it leaves open.

`schema/sidecar.schema.json` is the JSON Schema for the viewer's sidecar, the index the viewer loads beside a document (profile section 16.3): the keys, the parts, each printing's page markers with the eId they sit in, and each scan block's page and bounding box from CAP's `data-blocks`. A sidecar is named after its document (`{stem}.sidecar.json` beside `{stem}.akn.xml`), and everything in it except the bounding boxes must agree with the document.

The reference validator runs both:

```
uv run python validator/validate.py [PATH ...]
```

It checks each `*.akn.xml` against the Akoma Ntoso schema and then the Schematron rules, and each `*.sidecar.json` against its JSON Schema and its document. It runs the Schematron with Saxon HE (`saxonche`) and SchXslt2's transpiler, vendored unchanged from the SchXslt2 1.11.2 release (<https://codeberg.org/SchXslt/schxslt2>) at `validator/vendor/schxslt2/`, retrieved 2026-10-18. `validator/vendor/schxslt2/source.json` records the release archive's URL and SHA-256, each file's SHA-256, and the notice the files state: the MIT License, copyright David Maus.

## Examples from CAP data

`examples/cap/` holds seven complete documents, each with its sidecar, generated from Caselaw Access Project cases by `examples/cap/build.py`:

| Document | CAP case | What it shows |
|---|---|---|
| `us-dc-69-1943-05-11` | `a2d/31/0647-01`, D'Elia & Marks Co. v. Lyon | a short single-opinion decision |
| `us-dc-30-1943-02-12`, `us-dc-68-1943-05-11` | `a2d/31/0657-01` and `-02` | two decisions that begin on 31 A.2d 657 (profile section 13.2) |
| `us-pa-1428-1983-02-01` | `pa/500/0256-01`, Commonwealth ex rel. Zaffarano v. Genaro | an opinion, a concurrence and a dissent; a parallel A.2d printing whose text CAP withheld; page breaks inside paragraphs, a word and a footnote; footnotes, block quotations and citations |
| `us-pa-59e.d.misc.dkt.1983-1983-04-20` | `pa/500/0510-01`, Marutani v. Pawelec | a per curiam order with a dissenting statement |
| `us-pa-rpt.500-pa-109-1982-12-31` | `pa/500/0109-01`, Commonwealth v. Barry | no docket in CAP: the reporter fallback key; two dissents |
| `us-mass-rpt.150-mass-66-1889-11-11` | `mass/150/0066-01`, Commonwealth v. Freelove | an 1889 Massachusetts Reports case under the reporter fallback, with headnotes |

`examples/cap/manifest.json` lists each case's two source files, the case JSON and HTML from <https://static.case.law>, with the URL each was downloaded from and its SHA-256, and the CAP volume zip each is a member of, with that zip's SHA-256. The files are kept at `examples/cap/source/` under the same paths. CAP's data is CC0. The judge slugs come from `examples/cap/judges.json`, a fixture standing in for a judge registry like `examples/minimal/judges.json`.

A printing's `@ordinal` and `@text`, and a reporter fallback key's decision ordinal, come from CAP's volume records rather than from the manifest: `metadata/VolumeMetadata.json` and `metadata/CasesMetadata.json` in each volume zip on <https://data.stare.pub/cap/>, the volume the case is in and the volume of each parallel printing. The build reads those two members with HTTP range requests, so it never downloads a whole zip, and sends a User-Agent naming this repository. `examples/cap/volumes.lock.json` pins each zip by the ETag and size data.stare.pub served (every range response must match both) and each member by its SHA-256, and records which CAP slug each cited reporter abbreviation maps to, from <https://stare.pub/reporters.json>. A zip or member that doesn't match is an error, not a rebuild. The members are cached in `.cache/stare/` at the repository root, so once the cache is warm the build makes no requests; the first build after a clone, and every CI run, needs network access to data.stare.pub. Nothing from the volume records is committed here.

```
uv run python examples/cap/build.py           # rebuild the examples
uv run python examples/cap/build.py --check   # fail if a rebuild differs from the committed files
uv run python examples/cap/build.py --fetch   # download the source files again, check their pins, rebuild
uv run python examples/cap/build.py --lock    # pin the volume records again as data.stare.pub serves them, rebuild
```

The build is deterministic, and the checks run `--check`. It refuses a case rather than guess at anything the profile or the court record key spec leaves open, and says which. Invalid counterparts of these documents are in `vectors/akn-profile/documents.jsonl` (ids starting `cap-`).

## Court registry

`registry/courts.json` is the court registry the court record key spec references (section 10). Its version is a CalVer date (`2026.11.05`), separate from the spec's SemVer version: adding courts is a new registry version, and a release tag pins both. It holds 2,823 courts: every court in courts-db but one whose id fails the court rule, each with the jurisdiction code and docket profiles this registry assigns it (version `2026.11.05` gives the regional courts of appeals `printed` before 1971-01-01, CRK section 5.3), seven courts courts-db lacks, under CourtListener's ids, and eight codes the registry mints for CAP courts neither has (source `exemplar`).

Source and provenance: the court codes are the ids in Free Law Project's courts-db, <https://github.com/freelawproject/courts-db>, file `courts_db/data/courts.json` at commit `c22604dff8b6819d022cc5ddfd6d9080101149e3` (2026-10-07), retrieved 2026-10-18. That file is vendored unchanged at `registry/sources/courts-db/courts.json`, with the repository's LICENSE file beside it; courts-db's LICENSE states the BSD 2-Clause License. The registry's `source` block records the same facts and the vendored file's SHA-256, and its `excluded` block lists the one courts-db id left out and why.

`registry/cap-courts.json` maps each of the Caselaw Access Project's 3,454 court ids to the registry code for its decisions, with the date each code applies from where one CAP court is several registry courts over time. It is engine output, computed from CAP's case metadata and CourtListener's 2026-09-30 crosswalk of CAP cases to its clusters; each entry names the basis its code rests on, and the 6 courts it can't map are listed with the reason. Version `2026.10.28` maps 285 courts the earlier table left unmapped or marked for review, read from the head matter of their case files (codexpublicus/exemplar#26); version `2026.11.05.1` pins court registry `2026.11.05` and maps every court as before.

`registry/reporters.json` is the reporter registry (spec section 10.1): the reporters official for each court's decisions (version `2026.11.05` lists 51 courts, each step citing the statute, court rule or session law that makes its reporters official), the reporters that are editions of one report, and the dates each volume of the United States Reports, the Supreme Court Reporter and the Lawyers' Edition prints, computed from CAP's records for a person to check.

`registry/reporter-variants.json` is the reporter variant map (CRK sections 5.6 and 10.1, from 0.7.0): for each spelling of a reporter's abbreviation, the abbreviation whose slug a key uses. It is built by `registry/build_reporter_variants.py` from Free Law Project's reporters-db, <https://github.com/freelawproject/reporters-db>, file `reporters_db/data/reporters.json` at release v3.2.67, commit `4dd4e64e2fdbdb99215a8040bdb65eb74f8e1542` (2026-10-09), retrieved 2026-11-05 and vendored unchanged at `registry/sources/reporters-db/reporters.json` with the repository's LICENSE file beside it (BSD 2-Clause). Every variation reporters-db lists for one edition maps to that edition; the build's curated entries add the spellings CAP uses that reporters-db lacks, resolve `P.R.`, and keep apart three series a reporters-db variation would join. To take a newer reporters-db snapshot, vendor it, update the pin and run `uv run python registry/build_reporter_variants.py`; a changed entry changes keys, so it ships with a minor version of the spec.

To rebuild after vendoring a newer courts-db snapshot, update the pin in `registry/build_courts.py` and run `uv run python registry/build_courts.py`. The registry is append-only: a rebuild may add courts, and must not drop or change one already published.

There is no judge registry here. Judge slugs come from a registry the consumer supplies by URI (spec section 10.2); the vectors use a small fixture in its place.

## Status

Early. Nothing here is stable yet. The court record key spec is at 0.8.0 (draft), with court registry 2026.11.05, CAP court table 2026.11.05.1, reporter registry 2026.11.05 and reporter variant map 2026.11.05; it moved here from an unpublished study written for the Gorsuch library and is now the normative source. The Akoma Ntoso profile is at 0.6.0 (draft); its open questions are listed in its section 19. Documents refer to keys as `crk:` URIs (`crk:us/dc/57/1943-04-06`) and to the registries by their raw file URLs at a release tag; the examples name `v0.6.0`, the tag they are to be published under. Changes from one version to the next are in [`CHANGELOG.md`](CHANGELOG.md).

## Checks

```
uv run pytest
```

or, with mise, `mise run check` (everything CI runs) and `mise run validate [PATH ...]` (the reference validator).

The checks read the ABNF and the regex straight out of the spec, so a grammar change that the vectors don't follow fails. They check the CAP source-mapping vectors (`vectors/akn-profile/cap-mapping.jsonl`) against a reading of the profile's mappings for roles, citation links and scan pages. They also validate `registry/courts.json`, `registry/cap-courts.json` and `registry/reporter-variants.json` against their schemas, rebuild the court registry and the variant map from the vendored courts-db and reporters-db snapshots and compare, check each snapshot against its SHA-256 pin, and check that every court code a vector resolves is in the registry.

For the Akoma Ntoso profile, they validate every `examples/**/*.akn.xml` against the vendored Akoma Ntoso 1.0 schema (after checking its files against their pins), check each example's work, expression and part URIs against the court record key rules, and check that the example quoted in the profile is identical to `examples/minimal/`.

For the Schematron rules and the sidecar, they run every vector in `vectors/akn-profile/`: each edits a valid document or sidecar and names the rules the result must fail, no more and no fewer. They also check the vendored transpiler against its pins, that the Schematron's key regex is byte-identical to the court record key spec's, that its key and alias functions accept and reject what the court record key vectors say, that it covers every rule section 16.2 assigns it, and that every rule it checks has a vector.

## Licensing

Copyright (c) 2026 Codex Publicus contributors.

The specification text, the schemas, the court registry and the test vectors are licensed under the Creative Commons Attribution-NoDerivatives 4.0 International licence (CC BY-ND 4.0), whose legal code is in [`LICENSES/CC-BY-ND-4.0.txt`](LICENSES/CC-BY-ND-4.0.txt). So are the README, the changelog and the examples built here. The code is licensed under the BSD 3-Clause License, in [`LICENSE`](LICENSE) (also at `LICENSES/BSD-3-Clause.txt`).

| Path | Licence |
|---|---|
| `spec/` | CC BY-ND 4.0 |
| `schema/` (except `schema/akn/1.0/*.xsd`) | CC BY-ND 4.0 |
| `registry/courts.json`, `registry/cap-courts.json`, `registry/reporters.json`, `registry/reporter-variants.json` | CC BY-ND 4.0; `registry/courts.json` is built from courts-db data, whose notice is in [`registry/NOTICE-courts-db.txt`](registry/NOTICE-courts-db.txt), and `registry/reporter-variants.json` from reporters-db data, whose notice is in [`registry/NOTICE-reporters-db.txt`](registry/NOTICE-reporters-db.txt) |
| `vectors/` | CC BY-ND 4.0 |
| `validator/validate.py`, `validator/__init__.py`, `validator/vendor/schxslt2/source.json`, `tests/`, `registry/build_courts.py`, `registry/build_reporter_variants.py`, `examples/cap/build.py`, `.mise/`, `.github/`, `pyproject.toml`, `uv.lock` | BSD 3-Clause |
| `examples/minimal/`, and in `examples/cap/` the built documents and sidecars, `judges.json`, `manifest.json` and `volumes.lock.json` | CC BY-ND 4.0 |
| `examples/cap/source/` | the Caselaw Access Project's data, unchanged: CC0 1.0, whose legal code is in [`LICENSES/CC0-1.0.txt`](LICENSES/CC0-1.0.txt) |
| `README.md`, `CHANGELOG.md`, `examples/README.md` | CC BY-ND 4.0 |
| `schema/akn/1.0/*.xsd`, `registry/sources/courts-db/`, `registry/sources/reporters-db/`, `validator/vendor/schxslt2/` (except `source.json`) | vendored third-party files under the terms each states, described above |

<!-- REUSE-IgnoreStart -->
Code files carry SPDX headers (`SPDX-License-Identifier: BSD-3-Clause`); [`REUSE.toml`](REUSE.toml) records the same for the files that can't carry one. The vendored third-party files and the courts-db and reporters-db notices carry no annotation from this repository, so `reuse lint` reports them.
<!-- REUSE-IgnoreEnd -->
