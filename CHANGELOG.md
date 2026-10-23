# Changelog

Changes to the specs, schemas, vectors and examples, by release tag. A release tag pins the court record key spec (CRK), the Akoma Ntoso profile and the court registry together; each spec's own versioning section (CRK section 13, profile section 18) says what its versions mean. Earlier versions are described there.

## v0.3.1 (unreleased)

CRK 0.3.1, profile 0.3.1, court registry `2026.10.18` (unchanged). Both are patch releases, as the owner ruled on 2026-10-23 (D94): one clarification of the CRK and a change to how the CAP examples are built. No key changes; no existing vector's expected result changes; none of the seven CAP example keys and none of their eIds changes.

### Court record key 0.3.1

- **Letter case in judge names** ([exemplar#14](https://github.com/codexpublicus/exemplar/issues/14) part b). Section 10.2: a byline's name matches a judge's name or printed form when the two are equal after case folding (Unicode full case folding, Python's `str.casefold()`), so `HOOD` matches `Hood` and `McDERMOTT` matches `McDermott`. Case folding is the only normalization: still no edit distance, OCR correction or other approximation. Under the 0.3.0 text such a byline needed its upper-case form listed as a printed form.

### Akoma Ntoso profile 0.3.1

- Section 5.3 names the copies of CAP's volume records inside each volume zip (`metadata/VolumeMetadata.json`, `metadata/CasesMetadata.json`) as sources for a printing's `@ordinal` and `@text`. No rule changes.

### Vectors and examples

- `vectors/court-record-key/byline.jsonl`: six vectors for letter case, among them `HOOD` for `Hood`, `McDERMOTT` for `McDermott`, the printed form `Deyens` printed `DEYENS`, and an upper-case misprint the fixture doesn't list, which still matches nothing. The judges fixture gains `hood` and `mcdermott`.
- `examples/cap/build.py` takes each printing's `@ordinal` and `@text`, and a reporter fallback key's decision ordinal, from CAP's `VolumeMetadata.json` and `CasesMetadata.json`, read with HTTP range requests from the volume zips on `data.stare.pub` (the official volume and each parallel printing's volume). `examples/cap/volumes.lock.json` pins each zip by ETag and size and each member read by SHA-256, and the build refuses one that doesn't match; members are cached in `.cache/stare/`. `examples/cap/manifest.json` no longer states `pageShared` or the withheld printings, and the build no longer refuses a fallback decision that isn't first on its page: Glover, 500 Pa. 524, now builds to `us/pa/rpt.500-pa-524/1983-04-27~2` from the volume's case list, which a new test checks. The values the records give equal the ones the manifest stated.
- `examples/cap/judges.json` drops its printed forms, each of which differed from the judge's name only in letter case.
- The examples, the minimal example and the no-text vector name profile 0.3.1 and the release tag `v0.3.1`; nothing else in them changes.
- `vectors/akn-profile/sidecars.jsonl`: `profile-mismatch` now sets the sidecar's `profile` to `0.3.0`, since its base document declares 0.3.1; it expects the same result.

## v0.3.0 (unreleased)

CRK 0.3.0, profile 0.3.0, court registry `2026.10.18` (unchanged). The owner ruled on the ten gaps of [exemplar#10](https://github.com/codexpublicus/exemplar/issues/10) on 2026-10-23, approving every proposal as written; this version writes each ruling into the spec text.

### Court record key 0.3.0

- **Docket cleaning** ([exemplar#12](https://github.com/codexpublicus/exemplar/issues/12)). Section 5.1 is replaced: label removal ignores letter case and covers `Appeal No.`, `Appeal, No.`, `Docket No.`, `File No.`, `Gen. No.` and the like; a thousands separator is removed (`31,079` gives `31079`); a list of dockets (`;`, or `Nos.` with `,`, `&` or `and`) is keyed by its first, and the others are aliases; a docket with no digit is no docket. Section 5.5 gains a step: a comma between digits becomes `_` (`131, 1997` gives `131_1997`) and every other comma is deleted. **Changes keys**: the same printed docket can give a different segment than under 0.2.0, and a decision that fell back to `rpt.` can now have a docket key.
- **Fallback ordinal** ([exemplar#13](https://github.com/codexpublicus/exemplar/issues/13)). Section 5.6: a fallback decision's ordinal is its position among every decision that begins on the same reporter page and shares its date, whether or not they take the fallback; section 7 points to it. Glover, 500 Pa. 524, is `us/pa/rpt.500-pa-524/1983-04-27~2`. **Decides keys** 0.2.0 left ambiguous.
- **Printed forms in a judge registry** ([exemplar#14](https://github.com/codexpublicus/exemplar/issues/14) part b). Section 10.2: an entry MAY list the strings in which a source prints the judge's name, OCR errors included, each with its source; a producer matches a byline only to a name or printed form, exactly, never by approximation. Adds keys for parts 0.2.0 refused; changes none.

### Akoma Ntoso profile 0.3.0

- **Per curiam bylines** ([exemplar#14](https://github.com/codexpublicus/exemplar/issues/14) part a). Section 15.4: a `majority` byline that reduces to `percuriam`, `bythecourt` or `thecourt` is `per-curiam`. **Changes part keys**: an unsigned `By the Court.` or `THE COURT.` opinion goes from `.../opinion` to `.../per-curiam`.
- **Titles above a byline** ([exemplar#15](https://github.com/codexpublicus/exemplar/issues/15)). Section 7.2: paragraphs printed before a byline are `span`s in the part's `heading`, numbered with its paragraphs, and the byline moves to `subheading`. New rule AKN-59; AKN-34, AKN-35 and AKN-40 follow.
- **Reporter lines inside an opinion** ([exemplar#16](https://github.com/codexpublicus/exemplar/issues/16)). New section 8.4 and a change to 12.1: a paragraph the source classes as head matter inside a writing keeps its place and carries `@class` and a `@cx:origin` other than `court`. New rule AKN-60.
- **Head matter classes** ([exemplar#17](https://github.com/codexpublicus/exemplar/issues/17)). Section 6 adds the class `citation` and allows `courtType` only on text that names the court, with `@cx:provenance="engine-output"`; section 15.2 maps `p.citation` and restricts `p.court`.
- **Page markers** ([exemplar#18](https://github.com/codexpublicus/exemplar/issues/18); proposed as 0.2.1, folded in). Section 9.1 says how `@cx:scan` is read from `data-blocks`, never from the page offset, and that `@breakAt` and `@breakWith` are absent without source data; section 16.3 says which of several entries for a page a consumer uses.
- **Printing facts from volume records** ([exemplar#19](https://github.com/codexpublicus/exemplar/issues/19)). Section 5.3: `@ordinal` is required when another decision begins on the page, determined from the source's volume records; `@text` gains `released`, and every value but `transcribed` is `engine-output`. AKN-24 checks both values and provenance; the sidecar schema's `text` gains `released`.
- **Citation links** ([exemplar#20](https://github.com/codexpublicus/exemplar/issues/20)). Section 15.2: a CAP citation link is a decision when it has `data-case-paths`, or when its `cites_to` entry, matched with whitespace removed, has a `reporters:` category; the aliases are formed from `data-cite`.
- **Footnote markers** ([exemplar#21](https://github.com/codexpublicus/exemplar/issues/21); proposed as 0.2.1, folded in). Sections 11.1 and 11.2: `@marker` is the note's label as the source gives it, OCR errors included, never corrected.

### Vectors, schemas and examples

- `vectors/court-record-key/`: 22 docket vectors and 6 compute vectors for the new rules, including a consolidated case with its `crk:` alias and Glover's mixed page; a new `byline.jsonl` for printed forms; the judges fixture gains names and printed forms. No 0.2.0 vector's expected result changes.
- `vectors/akn-profile/`: 18 document vectors and 3 sidecar vectors for the new rules, and a new `cap-mapping.jsonl` for the CAP mappings of roles, citation links and `@cx:scan`. Vectors that named 0.2.x now name 0.3.x.
- `schema/profile.sch` checks profile 0.3.x documents; `schema/sidecar.schema.json` takes a 0.3.x `profile`.
- The examples are rebuilt as profile 0.3.0 documents naming the release tag `v0.3.0`. None of the seven example keys changes, and no eId changes. Marutani, Zaffarano and Barry move their titles into the heading; the fourteen classed paragraphs inside their parts carry `@cx:origin="unknown"`; the head matter citation lines of Zaffarano, Marutani and Barry are class `citation`; `courtType` and the withheld printings carry `@cx:provenance="engine-output"`; Freelove gains one `ref` (`3 Gray 458`). `examples/cap/judges.json` renames `bylines` to `printed`, listing each name as CAP prints it, with its source.
