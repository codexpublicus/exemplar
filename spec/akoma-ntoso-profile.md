# Akoma Ntoso judgment profile for US decisions

Specification version: **0.3.0** (draft). Status: not yet stable; see sections 17 and 18.

This profile says how a US court decision is written as an Akoma Ntoso document: which elements of OASIS LegalDocML (Akoma Ntoso) 1.0 a decision uses, how its separate opinions, printings, pages, citations, footnotes and publisher-added material are marked, and how every document identifies itself by the court record key. Codex Publicus producers (stare for the Caselaw Access Project corpus, gorsuch-library for its corpus) write documents in this form, and the shared viewer reads them.

The decisions behind it are recorded on codexpublicus/stare#52 (2026-09-29): the court record key is the work and expression identifier; one document per decision, with separate opinions inside it; duplicative cases are other printings of the same decision (one work, several manifestations, codexpublicus/stare#61); page anchors come from CAP's `data-blocks`.

## 1. Conventions

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in BCP 14 ([RFC 2119](https://www.rfc-editor.org/rfc/rfc2119), [RFC 8174](https://www.rfc-editor.org/rfc/rfc8174)) when, and only when, they appear in all capitals, as shown here.

Each requirement a machine can check carries a rule id in brackets, `[AKN-n]`. Section 16 lists every rule and says what enforces it: the Akoma Ntoso XML Schema, the Schematron rules of codexpublicus/exemplar#3, or neither.

Terms:

- **Decision**, **part**, **version**, **key**, **decision key**, **part key**, **alias**, **key reference**: as defined in [`court-record-key.md`](court-record-key.md) ("the CRK spec"), version 0.3.0. A key reference is `crk:` followed by a key (CRK spec section 2.6).
- **Printing.** One publication of a decision on numbered pages: the official report, a regional reporter's reprint, a nominative reporter. A printing is identified by its citation.
- **Source.** The digital record a producer took the document's content from: a CAP case (its JSON and HTML), a CourtListener cluster and its opinions.
- **Producer.** A program that writes documents in this profile. **Consumer.** A program that reads them (the viewer, a validator, an indexer).
- **AKN.** The Akoma Ntoso 1.0 vocabulary, namespace `http://docs.oasis-open.org/legaldocml/ns/akn/3.0`. Element names without a prefix are AKN elements.
- **`cx`.** This profile's extension namespace, `https://codexpublicus.org/ns/exemplar` (open question O1). Attributes and elements with the `cx:` prefix are in it.

## 2. Base standard and extensions

The base standard is Akoma Ntoso Version 1.0, OASIS Standard, 29 August 2018. Its XML Schema is vendored unchanged at `schema/akn/1.0/` (`akomantoso30.xsd` and the `xml.xsd` it imports), with the source URL and SHA-256 of each file in `schema/akn/1.0/source.json`.

A document MUST be valid against that schema [AKN-1]. The profile adds no elements to the AKN namespace. It uses AKN's two extension points:

- **Attributes in another namespace.** Every AKN content element whose attributes include AKN's `core` group accepts attributes in any other namespace (`xsd:anyAttribute namespace="##other"`). The profile's `cx:` attributes go there.
- **`proprietary`.** The `meta/proprietary` element accepts elements in any other namespace. The profile's `cx:` metadata elements go there.

The schema processes both with `processContents="lax"`: XSD validation doesn't check them, and the Schematron rules (#3) do.

A document MUST declare the profile version it follows in `meta/proprietary/cx:profile/@version` [AKN-2].

## 3. The FRBR model

A decision has three FRBR levels in this profile, and the court record key names the first two.

| Level | What it is | Identified by | Where it appears |
|---|---|---|---|
| Work | The decision: one issuance by one court on one date, with every writing issued with it | the decision key, `us/dc/57/1943-04-06` | `FRBRWork` |
| Expression | One version of the decision's text in one language: the decision as first issued, or a version the court amended, corrected or revised | the decision key as first issued; the key with `@{revised}` for a revised version (CRK spec section 9) | `FRBRExpression` |
| Manifestation | One embodiment of an expression: each printing (the official report, a regional reprint with its own pages), each source text (CAP's transcription, CourtListener's text), and the AKN document itself | this document: section 5.1.3; a printing: its citation; a source: its record | `FRBRManifestation` for this document; `references` and `cx:printing`, `cx:source` for the others |

AKN's identification block describes exactly one manifestation, the document it sits in. The profile therefore lists the other manifestations, printings and sources, in `references` (section 5.2) and `proprietary` (section 5.3), and ties text positions to printings with page markers (section 9).

Consequences:

- **Duplicative cases are printings.** A regional reprint of an officially reported decision is not a separate decision and MUST NOT get its own document [AKN-3, not machine-checkable]; it is a `cx:printing` of the decision's document, with its own citation and pages, whether or not its text was released.
- **Revisions by the court are expressions.** A version the court labels amended, corrected or revised gets its own document whose expression URI is the `@{revised}` key.
- **Corrections to a transcription are not court revisions.** A corrected OCR text, or a source's updated record, changes the manifestation the producer read, not the court's text. In this version it is a new manifestation (a new document file for the same expression); whether it should instead be a new expression is open question O5.

## 4. Document outline

```
akomaNtoso
  judgment @name="judgment" @contains
    meta
      identification      FRBRWork, FRBRExpression, FRBRManifestation (section 5.1)
      references          the court, judges, producer, source agents, printings, sources (5.2)
      notes               editorial notes from head matter (11.2), when there are any
      proprietary         cx:profile, cx:keys, cx:printing, cx:source (5.3)
    header                the head matter: caption, docket, court, dates, counsel, panel,
                          syllabus and headnotes, each block marked with its origin (6)
    judgmentBody
      introduction        only for a decision with no released text (13.1)
      motivation          the opinions: one hcontainer per part, in printed order (7)
      decision            separately headed orders, judgments and decrees (7)
```

The root MUST be `akomaNtoso` with exactly one `judgment` child and no `components` [AKN-4]. `judgment/@name` MUST be `judgment` [AKN-5]. `judgment/@contains` MUST be `originalVersion` for the expression as first issued and `singleVersion` for a revised version [AKN-6]. `coverPage`, `conclusions`, `attachments` and `components` MUST NOT be used [AKN-7].

## 5. Metadata

### 5.1 Identification

`identification/@source` MUST reference the producer's `TLCOrganization` [AKN-8].

#### 5.1.1 FRBRWork

| Element | Value | Rule |
|---|---|---|
| `FRBRthis/@value`, `FRBRuri/@value` | a key reference to the decision key: `crk:` followed by the key exactly as computed under the CRK spec (no part, no `@revised`), `crk:us/dc/57/1943-04-06` | [AKN-9] |
| `FRBRalias` | one per alias of the decision: `name` is the CRK alias scheme (`cite`, `neutral`, `cap`, `cl-cluster`, ...) and `value` the alias string (CRK spec section 11.1); `name="akn-nc"` holds the AKN Naming Convention IRI derived from the key (CRK spec section 15); `name="vendor"` holds a vendor citation verbatim (`1954 U.S. LEXIS 2094`), which has no alias scheme; a key-shaped alias is described below the table | [AKN-10] |
| `FRBRdate` | `@date` the decision date, `@name="decided"` | [AKN-11] |
| `FRBRauthor/@href` | `#` + the court's `TLCOrganization` eId | [AKN-12] |
| `FRBRcountry/@value` | `us`, the key's country segment | [AKN-13] |
| `FRBRnumber` | OPTIONAL: `@value` the key's docket segment, `@showAs` the docket as printed | |
| `FRBRname` | OPTIONAL: `@value` the decision's short name as the source gives it | |

An alias that is itself a decision key, such as the key under another docket of a consolidated case, is a key-shaped alias (CRK spec section 11.1). Its `@name` MUST be `crk` and its `@value` a key reference to a valid decision key, with no part and no `@{revised}`: `crk:us/scotus/17-1623/2020-06-15` [AKN-10]. An alias whose `@name` is a CRK alias scheme MUST be valid under that scheme; `cl-opinion` names a part, not a decision, and is not used in `FRBRWork`. `@name` MUST be a CRK alias scheme, `akn-nc` or `vendor` [AKN-10].

The `akn-nc` IRI of a decision key without a decision ordinal is `/akn/us/judgment/{court}/{decided}/{docket}` [AKN-10]. CRK section 15 gives no mapping for a key with a decision ordinal (`~2`); for such a key this version doesn't fix the value of an `akn-nc` alias, and AKN-10 doesn't check it.

A document MUST NOT be written for a decision whose key the producer can't compute [AKN-14, not machine-checkable]; the CRK spec's refusals apply unchanged. Open question O7 covers decisions that have no key under CRK 0.1.0, such as Supreme Court decisions before 1971-07-01.

Every URI value in this profile that names a key is a key reference: the work and expression URIs, the manifestation URI built from them (section 5.1.3), a `ref/@href` that names a key (section 10), and the value of a key-shaped alias. A bare key in any of these places makes the document invalid [AKN-9, AKN-10, AKN-15, AKN-18, AKN-51]. The key follows `crk:` verbatim, with no percent-encoding (CRK spec section 2.4). A key reference is an absolute URI in RFC 3986 terms; consumers MUST resolve key references and alias values through a resolver and MUST NOT resolve them against the document's own URL.

An attribute that holds the key of the element it sits on, rather than a reference to another resource, holds the key itself with no prefix: `@cx:part` (section 7.2), and the part keys in the sidecar (section 16.3). A consumer that needs a part's URI writes `crk:` followed by `@cx:part`.

#### 5.1.2 FRBRExpression

| Element | Value | Rule |
|---|---|---|
| `FRBRthis/@value`, `FRBRuri/@value` | a key reference to the version key: `crk:` followed by the decision key for the decision as first issued, or by the decision key with `@{revised}` | [AKN-15] |
| `FRBRdate` | `@name="decided"` with the decision date, or `@name="revised"` with the revision date | [AKN-16] |
| `FRBRauthor/@href` | as in `FRBRWork` | |
| `FRBRauthoritative/@value` | `false` | [AKN-17] |
| `FRBRlanguage/@language` | `eng` for English text | |

`FRBRauthoritative` is `false` because every text this profile carries is a transcription: OCR of a printed page, or a third party's copy. AKN defines an authoritative text as the official product of the body entrusted with issuing it. A transcription is not that, however accurate it is.

For the decision as first issued, the expression URI equals the work URI. AKN distinguishes the two by element, not by string; open question O3 asks whether the strings should differ.

#### 5.1.3 FRBRManifestation

| Element | Value | Rule |
|---|---|---|
| `FRBRthis/@value`, `FRBRuri/@value` | the expression URI followed by `.akn.xml`, `crk:us/dc/57/1943-04-06.akn.xml` | [AKN-18] |
| `FRBRdate` | `@name="generated"`: the date the producer generated the file, or the date of the producer's release; a producer that builds reproducibly SHOULD use the release date | |
| `FRBRauthor/@href` | `#` + the producer's `TLCOrganization` eId | [AKN-19] |
| `FRBRformat/@value` | `application/akn+xml` | [AKN-20] |

The manifestation URI is in the `crk` scheme but is not a key reference: the CRK grammar admits nothing after the key, and the suffix marks the URI as naming this file, the Akoma Ntoso manifestation of the expression whose key precedes it.

Two producers writing documents for the same expression write the same manifestation URI; the producer and its source are in `FRBRauthor` and `cx:source`. Whether the URI should name them is open question O4.

`FRBRItem` is not used.

### 5.2 References

`references/@source` MUST reference the producer [AKN-21]. Every agent, printing and source the document refers to has an entry, with these eIds [AKN-22]:

| Entry | Element | eId | `@href` | `@showAs` |
|---|---|---|---|---|
| The court | `TLCOrganization` | `court_{code}` (the key's court code) | the court registry entry, `{registry URI}#{code}` | the registry's court name |
| Each judge named as an author, a joiner, or in marked-up head matter | `TLCPerson` | the judge's slug | the judge registry entry, `{registry URI}#{slug}` | the judge's name |
| The producer, and each organization that made a source | `TLCOrganization` | `org_{name}` | the organization's URL | its name |
| Each printing | `TLCReference @name="printing"` | `printing_{volume}-{reporter slug}-{page}` | the printing's `cite:` alias | the citation as printed |
| Each source | `TLCReference @name="source"` | `source_{name}` | the source record's alias (`cap:...`, `cl-cluster:...`) | a readable label |

The registry URI is the `cx:registry/@uri` of section 5.3, an absolute URI, so the court's and judges' hrefs are absolute too: `https://raw.githubusercontent.com/codexpublicus/exemplar/v0.3.0/registry/courts.json#dc`. The fragment is the court code or judge slug, as this profile defines it; it is not a JSON Pointer.

Judge slugs match `[a-z][a-z-]*` (CRK spec section 10.2) and never contain the `_` that every other eId in this table has; the two kinds can't collide.

### 5.3 Proprietary metadata

`meta/proprietary` (with `@source` referencing the producer) holds these `cx:` elements:

- `cx:profile @version`: the profile version (section 2) [AKN-2].
- `cx:keys @provenance`: how the keys were obtained (section 12), with one `cx:registry` child per registry used to compute them, `@name` (`courts`, `judges`), `@uri`, `@version`. This is the record of registry snapshots the CRK spec section 10.3 requires a producer to keep [AKN-23]. `@uri` MUST be an absolute URI with no fragment [AKN-23]. For the court registry it MUST be the raw file URL of `registry/courts.json` at the release tag of codexpublicus/exemplar the producer pinned, `https://raw.githubusercontent.com/codexpublicus/exemplar/{tag}/registry/courts.json` (CRK spec section 10.3) [AKN-23]; a judge registry's URI is the one its publisher gives the snapshot. The rules check the URL's shape and can't tell a tag from a branch name; a producer MUST NOT name a branch, since a branch doesn't name one snapshot. `cx:keys` MUST list exactly one `courts` registry. It MUST list one `judges` registry when some part key has authors, and MAY list one otherwise; a decision with no authored part, such as one with no released text (section 13.1), computes no judge slugs [AKN-23].
- `cx:printing`: one per printing in `references` [AKN-24]. Attributes:
  - `@ref`: `#` + the printing's `TLCReference` eId.
  - `@type`: `official` or `parallel`, as the source types the citation.
  - `@reporter`, `@volume`, `@firstPage`, `@lastPage`: as printed. `@lastPage` is OPTIONAL when the source doesn't give it.
  - `@ordinal`: REQUIRED when another decision begins on `@firstPage` of this printing, and absent otherwise; this decision's position among them, in printed order (CAP's file suffix, `-01`, `-02`). The producer MUST determine it from the source's record of the whole volume (CAP: the volume's `CasesMetadata.json` or its case file names), not from the case record alone.
  - `@text`: `transcribed` when the document's text was taken from this printing; `released` when a source released the printing's text as a record of its own, which this document didn't use (a CAP case in an unredacted volume at this citation); `withheld` when a source holds the printing's pages but released no text for this decision (CAP: `VolumesMetadata.json` lists the volume, and its case list has no case beginning on this page); `unavailable` when no source the producer consulted holds the printing's pages. Every value but `transcribed` is derived from the source's volume-level records, and the `cx:printing` carries `@cx:provenance="engine-output"` [AKN-24].
  - Children: `cx:cite @type @value` for each other citation of the same pages, such as a nominative reporter citation (`9 Wheat. 738` for 22 U.S. 738); `cx:scans @source @volume @first @last` when a source holds scans of the printing, giving the source's volume and the first and last scan sequence numbers (CAP's `first_page_order` and `last_page_order`).
- `cx:source`: one per source in `references` [AKN-25]. Attributes: `@ref` (the `TLCReference`), `@agent` (the organization that made it), `@record` (its alias), `@method` (`ocr`, `born-digital`, `keyed`, or `unknown`: how the source's text was made, as far as the source says), and whatever identifies the record's state as the source gives it (`@caseId`, `@lastUpdated`, `@sha256` for CAP; `@textField` for CourtListener). An optional `cx:confidence @value @scope @basis` child records a confidence figure the source publishes, such as CAP's `analysis.ocr_confidence`, with `@basis` naming the field it came from.

## 6. Header

`header` holds the head matter: everything printed before the first part. Each block of head matter is a `p` (one paragraph) or a `blockContainer` (several), in printed order, and each MUST carry [AKN-26]:

- `@class`: the kind of block, from this vocabulary: `parties`, `docketnumber`, `court`, `decisiondate`, `otherdate`, `attorneys`, `judges`, `syllabus`, `headnotes`, `summary`, `synopsis`, `history`, `disposition`, `posture`, `arguments` (arguments of counsel as a reporter printed them), `statement` (a reporter's statement of the case), `citation` (a citation of this decision that the reporter prints in the head matter: a parallel, neutral or other reporter's citation), `headmatter` (anything else).
- `@cx:origin`: who wrote it, as far as the producer knows (section 12.1).
- `@eId`: `header__p_{n}` for a `p`, `header__blockContainer_{n}` for a `blockContainer`; paragraphs inside a `blockContainer` are `{its eId}__p_{n}`. `p` and `blockContainer` blocks are numbered separately, each in printed order: each block's `n` MUST be greater than that of the previous header block of the same element, and need not be one greater.

Blocks of class `syllabus`, `headnotes`, `summary` and `synopsis` MUST NOT have `@cx:origin="court"` [AKN-27]. They are added by a reporter or a publisher; the official syllabus of the Supreme Court is itself prepared by the Reporter of Decisions and is not part of the opinion.

Inside head matter blocks, a producer SHOULD mark: the caption with `docTitle`; the docket number with `docketNumber`; the court's name with `courtType @refersTo` (the court's `TLCOrganization`); the decision date with `docDate @date`. A producer MUST NOT mark text with `courtType` unless the text names the court; a division, department, panel, county or sitting (`Division One.`, `Suffolk.`, `En Banc.`) is not the court's name. A `courtType` the producer adds after reading the text carries `@cx:provenance="engine-output"`. It MAY mark other dates with `date @date`, judges with `judge @refersTo` (a `TLCPerson`), parties with `party @refersTo`, and counsel with `lawyer @refersTo`. Markup that the producer derived, rather than copied from the source's own structure, carries `@cx:provenance="engine-output"` (section 12.2). The text inside stays as the source gives it: `Rebearing Denied` in the example is CAP's OCR of "Rehearing Denied", and it stays.

## 7. Parts: opinions and other separately headed writings

### 7.1 The construct, checked against the schema

codexpublicus/exemplar#2 asked for the AKN construct for separate opinions to be confirmed against the schema. These are the facts in `akomantoso30.xsd`:

- `opinion` is an inline element. Its content model is AKN's `inline` type, its `by` attribute (an agent reference) is required, and its `type` attribute is one of `dissenting`, `agreeing`, `null`. Inline content admits text, inline elements, markers and sub-flows, but not `p` or other blocks. An `opinion` can't directly hold a writing of several paragraphs.
- `judgmentBody` holds one or more of `introduction`, `background`, `arguments`, `remedies`, `motivation`, `decision`, in any order and repeatable. Each is of type `maincontent`, which admits hierarchical elements, `hcontainer` among them.
- `hcontainer` has a required `name`, then optional `num`, `heading` and `subheading`, then either `content` (blocks) or nested hierarchy.
- `heading` is inline and can hold `opinion`.

Two other constructs are schema-valid and were not chosen. Wrapping a writing's paragraphs in a `subFlow` inside an `opinion` inside a `p` puts an entire opinion inside one paragraph. Making each writing a `component` holding its own `judgment` gives each part its own identification block, but needs a full `meta` and `header` per part, splits footnotes and page markers across nested documents, and departs from the decision on stare#52 of one document per decision.

The profile's construct: each part is an `hcontainer` inside `motivation` or `decision`, and the part's heading holds an `opinion` element that says who wrote it and whether it agrees or dissents. The CRK spec's informative section 15 describes a part as an inline `<opinion>` with eId `opinion_concurrence.gorsuch`; here that eId is on the `hcontainer`, and the `opinion` element sits in its heading.

### 7.2 Rules

For each separately headed writing (CRK spec section 8), in printed order [AKN-28]:

```xml
<hcontainer name="{role}" eId="opinion_{part}" cx:part="{part key}" cx:authors="{slug} ..." cx:sourceType="{source's type}">
  <heading><opinion by="#{first author slug, or court_{code}}" type="{agreeing|dissenting}">{the heading as printed}</opinion></heading>
  <content>
    <p eId="opinion_{part}__p_1">...</p>
  </content>
</hcontainer>
```

- `@name` MUST be the part's CRK role [AKN-29].
- `@eId` MUST be `opinion_` followed by the part segment of the part key, `{role}[.{authors}][~n]` [AKN-30].
- `@cx:part` MUST be the part key, with no `crk:` prefix (section 5.1.1), and its decision key MUST equal the key the work URI names [AKN-31]. In a document for a revised version, the part key MAY omit `@{revised}`; if present, it MUST equal the expression's revision date. In a document for the decision as first issued, the part key has no `@{revised}`.
- `@cx:authors` MUST list the author slugs in printed order, separated by single spaces, the same list as the part key; it is absent for a part with no author [AKN-32].
- `@cx:joinedBy`, OPTIONAL, lists the slugs of judges who joined the writing, in printed order, each with a `TLCPerson` [AKN-33].
- `@cx:sourceType` records the source's own type for the writing (CAP's `majority`, `dissent`, ...), unchanged.
- `@cx:aliases`, OPTIONAL, lists the part's CRK aliases (`cl-opinion:{id}`), separated by single spaces.
- The heading's `opinion/@by` MUST reference the first author's `TLCPerson`, or the court's `TLCOrganization` for a part with no author (a per curiam opinion, an unsigned order) [AKN-34]. `opinion/@type` follows the table below and is absent where the table has no value [AKN-35].
- Parts with roles `order`, `judgment` and `decree` go in `decision`; every other part goes in `motivation` [AKN-36]. Consecutive parts that go in the same block share one block element, and printed order is kept: a decision whose order is printed between two opinions has `motivation`, `decision`, `motivation`.

| CRK role | Block | `opinion/@type` |
|---|---|---|
| `opinion`, `per-curiam`, `plurality`, `partial-majority` | `motivation` | (none) |
| `concurrence`, `concurrence-in-judgment`, `concurrence-in-part-and-judgment` | `motivation` | `agreeing` |
| `partial` | `motivation` | (none): AKN has no value for concurring in part and dissenting in part |
| `dissent` | `motivation` | `dissenting` |
| `statement` | `motivation` | (none) |
| `order`, `judgment`, `decree` | `decision` | (none); the heading MAY omit `opinion` |

The heading holds the writing's byline as the source gives it (CAP's `p.author`). Text the source prints after the byline, such as `(dissenting).` or `delivered the opinion of the Court.` in a separate paragraph, stays in `content`; the producer doesn't merge it into the heading.

When the source prints one or more paragraphs between the start of a writing and its byline (CAP: elements of `article.opinion` before `p.author`), they stay before the byline [AKN-59]:

- `heading` holds them in printed order, each as a `span` with `@eId` `{container eId}__p_{n}` and its own `@cx:blocks`, separated by `br`. They count in the part's paragraph numbering (section 8.1): with k such paragraphs, the first paragraph of `content` is `__p_{k+1}`.
- `subheading` holds the byline wrapped in `opinion`, and carries the byline's `@cx:blocks`. AKN-34 and AKN-35 apply to that `opinion`.
- Page markers in these paragraphs stay where they fall, inside their `span`.

A part with nothing printed before its byline keeps the byline in `heading`. A writing whose byline is its last element is refused in this version.

Marutani v. Pawelec's per curiam part (`examples/cap/us-pa-59e.d.misc.dkt.1983-1983-04-20.akn.xml`) is `<heading><span eId="opinion_per-curiam__p_1" cx:blocks="BL_561.3"><eop .../>ORDER</span></heading><subheading cx:blocks="BL_561.4"><opinion by="#court_pa">PER CURIAM:</opinion></subheading>`, followed by `content` starting at `__p_2`, the eId `Petition denied.` already had under 0.2.0.

Joint authors appear in printed order in the part key and `@cx:authors`; `opinion/@by` names the first, because AKN's `by` takes one agent.

A document MUST NOT contain a part whose key the producer can't compute (an author missing from the judge registry, CRK refusal `unregistered-author`); the producer refuses the whole document [AKN-37, not machine-checkable]. Open question O6 is whether to allow unkeyed parts instead.

### 7.3 The other judgment blocks

- `introduction` is used only to hold the notice of a decision with no released text (section 13.1).
- `background`, `arguments` and `remedies` MUST NOT be used in this version [AKN-38]. Neither CAP nor CourtListener marks where an opinion's background ends and its reasoning begins, and splitting a writing across blocks would split its `hcontainer`. Arguments of counsel printed in the head matter are header blocks of class `arguments`.
- `motivation` and `decision` hold parts as in 7.2; nothing else goes directly in them [AKN-39].

## 8. Text

### 8.1 Paragraphs and blocks

A part's `content` holds its paragraphs in source order. A source paragraph is a `p`; a block quotation is `block @name="blockquote"`. Every `p` and `block` taken from the source MUST have `@eId` `{container eId}__p_{n}`, where `n` is its 1-based position among the source's paragraphs and block quotations in that container [AKN-40]. Numbering counts every source paragraph, including ones an excerpt omits; an eId means the same paragraph in an excerpt and in the full document.

eIds are anchors this profile mints. Consumers MUST NOT display them as the court's paragraph numbers [AKN-41, not machine-checkable]. Paragraph numbers a court printed stay in the text in this version.

The text is the source's text. A producer MAY normalize whitespace and MUST remove the source's own markup, and MUST NOT otherwise change the text, including to correct an OCR error [AKN-42, not machine-checkable].

### 8.2 Scan anchors

Every element made from a source block that carries CAP's `data-blocks` MUST have `@cx:blocks`: the ALTO block ids from that `data-blocks` value, in order, separated by single spaces (`BL_731.32 BL_732.1`) [AKN-43]. A block id names a block in the volume's ALTO files; in CAP's data the first number in an id is the scan page sequence number that the `data-blocks` entry also gives. Bounding boxes are not in the document; the viewer's sidecar (#3) carries them, keyed by block id.

### 8.3 Omissions

An excerpt marks omitted text with `omissis`. A `p` that the producer inserts to hold omissions has `@cx:origin="producer"` and no `@eId` [AKN-44]. Page markers that fall in omitted text stay, in order, between the `omissis` elements.

### 8.4 Head matter inside a part

A paragraph that the source places inside a writing but classes as head matter (CAP: a `p` in `article.opinion` with a class other than `author`) stays where the source prints it and keeps its place in the part's paragraph numbering (section 8.1). It MUST carry `@class`, from the vocabulary of section 6 (`headmatter` for a class not in it), and `@cx:origin`, which MUST NOT be `court` [AKN-60]. A source that doesn't say who wrote it gives `unknown`, as in section 12.1.

## 9. Pages and printings

### 9.1 Page breaks

A page break in a printing is an `eop` marker at the point in the text where the page begins [AKN-45]:

```xml
operating. <eop refersTo="#printing_31-a2d-683" number="684" cx:scan="732"/>a taxicab.
```

- `@refersTo` MUST reference the printing's `TLCReference` [AKN-46].
- `@number` MUST be the number of the page that begins at the marker, as printed [AKN-47]. This is the page CAP's star paging labels (`*684`). AKN's name for the element is "end of page"; in this profile the marker sits at the boundary and names the page that follows it.
- `@cx:scan`, when the source holds scans of the printing, is the scan sequence number of the page that begins at the marker. From CAP it is read from the `data-blocks` of the source block that contains the page label: list the scan pages of that block's entries in order, dropping consecutive repeats; the k-th label in the block takes the (k+1)-th scan page, or the k-th when the label comes before any of the block's text. When the block has too few scan pages for its labels, `@cx:scan` MUST be absent. A producer MUST NOT compute it from `@number` and `cx:scans/@first`. The marker carries `@cx:provenance="engine-output"`.
- A printing's first page has no marker; its number is `cx:printing/@firstPage`.
- `@breakAt` and `@breakWith` MUST be absent unless the source records how the word was broken; CAP doesn't. A marker between two letters without them says only that the page began inside the word.

A page break inside head matter or a footnote is marked the same way, where it falls. Markers from different printings interleave in the one text; when two fall at the same position, they appear in the order the printings are listed in `references`.

### 9.2 Several printings

Every printing the producer knows of is listed (sections 5.2 and 5.3), whether or not its text was released. A producer MUST NOT place markers for a printing at positions the source doesn't give [AKN-48, not machine-checkable]. CAP's star paging marks only the printing CAP transcribed; the regional reprint of an officially reported decision therefore appears as a `cx:printing` with its citation, page range and scans, and with no markers, until a producer aligns its pages. Markers placed by alignment carry `@cx:provenance="engine-output"`.

### 9.3 Lines

`eol` MAY be used for line breaks taken from line-level data (ALTO). It follows the same rules as `eop`: `@refersTo` a printing, placed where the line begins [AKN-49]. CAP's JSON and HTML don't give line breaks.

## 10. Citations

A citation to a court decision is a `ref` whose text is the citation as printed [AKN-50]:

```xml
<ref href="cap:f2d/107/0238-01" cx:cite="107 F.2d 238">107 F.2d 238</ref>
```

`@href` is, in this order of preference [AKN-51]:

1. a key reference to the cited decision's key, `crk:us/...`, when the producer can map the source's link to a key;
2. a CRK alias from the source's own link: `cap:` from CAP's `data-case-paths`, `cl-cluster:` from a CourtListener opinion link;
3. a `cite:` alias formed from the citation (CRK spec section 11.1).

`@href` MUST NOT be empty. A citation that yields none of these stays unmarked text. When the source links one citation to several decisions (CAP's `data-case-ids="1089787,3558684"`), `@href` is the `cite:` alias, which a resolver maps to all of them; the producer MUST NOT pick one [AKN-52, not machine-checkable].

`@cx:cite` holds the citation as the source normalized it (CAP's `data-cite`). It can differ from the text. CAP normalizes a parallel citation to the official one: `60 S.Ct. 321` has `data-cite="308 U.S. 444"`. Pin pages stay in the text outside the `ref`.

A `ref` that the producer resolved itself, rather than taking the target from the source, carries `@cx:provenance="engine-output"`.

Citations to legislation, regulations and other non-decisions MUST NOT use a decision key or a decision alias scheme as `@href` [AKN-53]. In this version they stay unmarked text (open question O9).

## 11. Footnotes and notes

### 11.1 Footnotes in a part

A footnote in a part is the author's: it is an `authorialNote` placed at the position of its reference mark [AKN-54]:

- `@marker`: the note's mark as the source gives it (CAP: `aside.footnote/@data-label`), OCR errors included. A producer MUST NOT renumber or correct it (section 8.1). When the mark in the text differs from the note's label, `@marker` is the note's label. The note's eId numbers it by position and doesn't depend on `@marker`. When footnote numbers run on across parts, as in the example (the dissent's footnotes are 6 to 9), they stay.
- `@placement`: `bottom`.
- `@eId`: `{container eId}__authorialNote_{n}`, `n` its 1-based position in the part; its paragraphs are `{note eId}__p_{n}`.
- Its paragraphs carry `@cx:blocks` like any other.

The note's text is not repeated at the position where the source printed it.

### 11.2 Notes in head matter

A footnote in the head matter is not part of any opinion. It is a `note` in `meta/notes`, with `@eId` `note_{n}`, `@marker` and `@cx:origin`, and a `noteRef @href="#note_{n}"` at its reference mark [AKN-55]. Its `@marker` follows the rule of section 11.1.

## 12. Origin and provenance

Codex Publicus's rule for its data applies here: engine output is never presented as ground truth. A document records what kind of thing each piece of it is, and consumers must show it for what it is.

### 12.1 Origin: who wrote the text

`@cx:origin` says who wrote a block of text:

| Value | Meaning |
|---|---|
| `court` | the court (an opinion, the court's own order) |
| `reporter` | an official reporter of decisions (an official syllabus, a reporter's statement) |
| `publisher` | a commercial publisher (headnotes, a synopsis) |
| `producer` | the producer (an omission mark, the notice of section 13.1) |
| `unknown` | not known |

Header blocks, head matter notes and the blocks of section 8.4 MUST carry it. Every other block in a part is `court` and doesn't carry it. A source that doesn't say who wrote a head matter block gives `unknown`; this is CAP's case (open question O10).

### 12.2 Provenance: where markup and values came from

`@cx:provenance` says where an element's markup and attribute values came from, not its text:

| Value | Meaning |
|---|---|
| `source` | copied from the source's own structure or fields |
| `engine-output` | derived by a program: a key computed from source fields, a date parsed from text, a judge linked to a registry entry, a citation the producer resolved, a page marker placed by alignment |
| `human-curated` | checked by a person against the printed page |

The value applies to the element and is inherited by its descendants; an element with no `@cx:provenance` on itself or any ancestor is `source`. `cx:keys/@provenance` gives the provenance of the document's keys; a producer that computes them from source fields MUST give `engine-output` [AKN-56].

### 12.3 Text

How the text itself was made is in `cx:source/@method`, with any confidence figure the source publishes in `cx:confidence`. CAP's `ocr_confidence` is a figure CAP computed for each case; it is not a measured error rate, and consumers MUST NOT present it as one.

### 12.4 Consumers

Consumers MUST NOT present as verified anything whose provenance isn't `human-curated`, MUST present text whose source `@method` is `ocr` as a transcription made by OCR, and MUST label header blocks whose origin isn't `court` as not part of the court's opinion [AKN-57, not machine-checkable].

## 13. Edge cases

### 13.1 Decisions with no released text

When no source has released text for any part of a decision (every `cx:printing/@text` is `withheld` or `unavailable`), the document has no parts. Its `judgmentBody` is one `introduction` holding a `p` with `@class="no-text"` and `@cx:origin="producer"`, which says the text was not released and names the printings [AKN-58]. Its header holds what the source's metadata gives (name, docket, date), as blocks with `@cx:origin="producer"`, since they weren't printed in this form.

A printing whose text was withheld, of a decision whose text is available from another printing, is not this case: it is a `cx:printing` in that decision's document (section 3).

### 13.2 Several decisions on one page

When several decisions begin on one page, each has its own document. Each lists the printing with the same `@firstPage` and its own `@ordinal`, and the page's `eop` markers appear in each document's text. Their keys differ by docket, or, under the reporter fallback, by the decision ordinal (CRK spec section 5.6).

## 14. Example

`examples/minimal/us-dc-57-1943-04-06.akn.xml`, reproduced in full below, is an excerpt of Taylor v. Yellow Cab Co., 31 A.2d 683 (Municipal Court of Appeals for the District of Columbia, 1943), built by hand from CAP case `a2d/31/0683-01`: the head matter in full, the opening and closing of the majority opinion with its first footnote, and the opening of the dissent. It is valid against the vendored schema, and the checks compare this copy with the file.

Facts behind its identifiers:

- Court code `dc`: the court registry's `dc` (District of Columbia Court of Appeals) comes from courts-db, whose `dc` entry lists `${dc} Municipal ${coa}` and `Municipal ${coa} (for the)? ${dc}` among the court names it recognizes. CAP's `court.name` for this case is `District of Columbia Municipal Court of Appeals`. Mapping CAP's court to a registry code is `engine-output`, recorded in `cx:keys`.
- Docket `57`: CAP prints `No. 57.`; cleaning (CRK spec section 5.1) gives `57`, which the `printed` profile keeps.
- Decision key `us/dc/57/1943-04-06`; parts `opinion.hood` (CAP type `majority`) and `dissent.cayton` (`dissent`). The judge slugs come from `examples/minimal/judges.json`, a fixture standing in for a judge registry.
- Work and expression URI `crk:us/dc/57/1943-04-06`, the key reference to that key; `@cx:part` holds the part keys themselves.
- Registry URIs name the release tag `v0.3.0`, the tag this example is to be published under; they don't resolve until that tag exists. The judges fixture's URI is its raw file URL at the same tag.
- The court line's `courtType` carries `@cx:provenance="engine-output"`, as section 6 requires of a `courtType` the producer adds after reading the text.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!--
  Minimal example for spec/akoma-ntoso-profile.md 0.3.0, quoted in full in section 14 of that spec.
  An excerpt of Taylor v. Yellow Cab Co., 31 A.2d 683, built by hand from the Caselaw Access Project
  case a2d/31/0683-01. The text is CAP's, OCR errors included; omitted text is marked with omissis.
-->
<akomaNtoso xmlns="http://docs.oasis-open.org/legaldocml/ns/akn/3.0" xmlns:cx="https://codexpublicus.org/ns/exemplar">
  <judgment name="judgment" contains="originalVersion">
    <meta>
      <identification source="#org_exemplar">
        <FRBRWork>
          <FRBRthis value="crk:us/dc/57/1943-04-06"/>
          <FRBRuri value="crk:us/dc/57/1943-04-06"/>
          <FRBRalias name="akn-nc" value="/akn/us/judgment/dc/1943-04-06/57"/>
          <FRBRalias name="cite" value="cite:31-a2d-683" showAs="31 A.2d 683"/>
          <FRBRalias name="cap" value="cap:a2d/31/0683-01"/>
          <FRBRdate date="1943-04-06" name="decided"/>
          <FRBRauthor href="#court_dc"/>
          <FRBRcountry value="us"/>
          <FRBRnumber value="57" showAs="No. 57."/>
          <FRBRname value="Taylor v. Yellow Cab Co."/>
        </FRBRWork>
        <FRBRExpression>
          <FRBRthis value="crk:us/dc/57/1943-04-06"/>
          <FRBRuri value="crk:us/dc/57/1943-04-06"/>
          <FRBRdate date="1943-04-06" name="decided"/>
          <FRBRauthor href="#court_dc"/>
          <FRBRauthoritative value="false"/>
          <FRBRlanguage language="eng"/>
        </FRBRExpression>
        <FRBRManifestation>
          <FRBRthis value="crk:us/dc/57/1943-04-06.akn.xml"/>
          <FRBRuri value="crk:us/dc/57/1943-04-06.akn.xml"/>
          <FRBRdate date="2026-10-18" name="generated"/>
          <FRBRauthor href="#org_exemplar"/>
          <FRBRformat value="application/akn+xml"/>
        </FRBRManifestation>
      </identification>
      <references source="#org_exemplar">
        <TLCOrganization eId="court_dc" href="https://raw.githubusercontent.com/codexpublicus/exemplar/v0.3.0/registry/courts.json#dc" showAs="District of Columbia Court of Appeals"/>
        <TLCOrganization eId="org_exemplar" href="https://github.com/codexpublicus/exemplar" showAs="codexpublicus/exemplar"/>
        <TLCOrganization eId="org_cap" href="https://case.law/" showAs="Caselaw Access Project"/>
        <TLCPerson eId="cayton" href="https://raw.githubusercontent.com/codexpublicus/exemplar/v0.3.0/examples/minimal/judges.json#cayton" showAs="Cayton"/>
        <TLCPerson eId="hood" href="https://raw.githubusercontent.com/codexpublicus/exemplar/v0.3.0/examples/minimal/judges.json#hood" showAs="Hood"/>
        <TLCPerson eId="richardson" href="https://raw.githubusercontent.com/codexpublicus/exemplar/v0.3.0/examples/minimal/judges.json#richardson" showAs="Richardson"/>
        <TLCReference eId="printing_31-a2d-683" name="printing" href="cite:31-a2d-683" showAs="31 A.2d 683"/>
        <TLCReference eId="source_cap" name="source" href="cap:a2d/31/0683-01" showAs="Caselaw Access Project, a2d/31/0683-01"/>
      </references>
      <proprietary source="#org_exemplar">
        <cx:profile version="0.3.0"/>
        <cx:keys provenance="engine-output">
          <cx:registry name="courts" uri="https://raw.githubusercontent.com/codexpublicus/exemplar/v0.3.0/registry/courts.json" version="2026.10.18"/>
          <cx:registry name="judges" uri="https://raw.githubusercontent.com/codexpublicus/exemplar/v0.3.0/examples/minimal/judges.json" version="fixture"/>
        </cx:keys>
        <cx:printing ref="#printing_31-a2d-683" type="official" reporter="A.2d" volume="31" firstPage="683" lastPage="687" text="transcribed">
          <cx:scans source="#source_cap" volume="a2d/31" first="731" last="735"/>
        </cx:printing>
        <cx:source ref="#source_cap" agent="#org_cap" record="cap:a2d/31/0683-01" caseId="8152964" lastUpdated="2024-02-27T18:54:06.352297+00:00" sha256="6de9c242f53cc91197349d0060dbbd6ad0484c86d096cbdd364c0291123f06dd" method="ocr">
          <cx:confidence value="0.713" scope="case" basis="CAP analysis.ocr_confidence"/>
        </cx:source>
      </proprietary>
    </meta>
    <header>
      <p eId="header__p_1" class="parties" cx:origin="unknown" cx:blocks="BL_731.10"><docTitle>TAYLOR v. YELLOW CAB CO. OF DISTRICT OF COLUMBIA.</docTitle></p>
      <p eId="header__p_2" class="docketnumber" cx:origin="unknown" cx:blocks="BL_731.11"><docketNumber>No. 57.</docketNumber></p>
      <p eId="header__p_3" class="court" cx:origin="unknown" cx:blocks="BL_731.12"><courtType refersTo="#court_dc" cx:provenance="engine-output">Municipal Court of Appeals for District of Columbia.</courtType></p>
      <p eId="header__p_4" class="decisiondate" cx:origin="unknown" cx:blocks="BL_731.13"><docDate date="1943-04-06">April 6, 1943.</docDate></p>
      <p eId="header__p_5" class="otherdate" cx:origin="unknown" cx:blocks="BL_731.14">Rebearing Denied <date date="1943-04-27" cx:provenance="engine-output">April 27, 1943</date>.</p>
      <p eId="header__p_6" class="attorneys" cx:origin="unknown" cx:blocks="BL_731.28">James J. Laughlin, of Washington, D. C. for appellant.</p>
      <p eId="header__p_7" class="attorneys" cx:origin="unknown" cx:blocks="BL_731.29">Alfred M. Schwartz, of Washington, D. C. (A. Arvin Lynn, of Washington, D. C., on the brief), for appellees.</p>
      <p eId="header__p_8" class="judges" cx:origin="unknown" cx:blocks="BL_731.30">Before <judge refersTo="#richardson" cx:provenance="engine-output">RICHARDSON</judge>, Chief Judge, and <judge refersTo="#cayton" cx:provenance="engine-output">CAYTON</judge> and <judge refersTo="#hood" cx:provenance="engine-output">HOOD</judge>, Associate Judges.</p>
    </header>
    <judgmentBody>
      <motivation>
        <hcontainer name="opinion" eId="opinion_opinion.hood" cx:part="us/dc/57/1943-04-06/opinion.hood" cx:authors="hood" cx:sourceType="majority">
          <heading cx:blocks="BL_731.31"><opinion by="#hood">HOOD, Associate Judge.</opinion></heading>
          <content>
            <p eId="opinion_opinion.hood__p_1" cx:blocks="BL_731.32 BL_732.1">Plaintiff brought an action for damages for alleged illegal conduct of defendants by which he was prevented from operating. <eop refersTo="#printing_31-a2d-683" number="684" cx:scan="732"/>a taxicab. Trial by jury was demanded by plaintiff and the case was set for trial on Tuesday, October 27, 1942. On that day parties and their counsel were present in court at 10 a. m. but the case was not reached until about 3 p. m. At that time a “long panel” of jurors was not available but both sides agreed to accept a “short panel” of twelve jurors. Apparently one of the twelve was disqualified or excused, since by agreement the jury sworn to try the case consisted of only eleven members.</p>
            <p cx:origin="producer"><omissis>[…]</omissis></p>
            <p eId="opinion_opinion.hood__p_6" cx:blocks="BL_732.9">Plaintiff has appealed and argues (1) the court was in error in refusing his request for a continuance, and (2) the court abused its discretion in proceeding with the case in the absence of plaintiff.<authorialNote eId="opinion_opinion.hood__authorialNote_1" marker="1" placement="bottom"><p eId="opinion_opinion.hood__authorialNote_1__p_1" cx:blocks="BL_732.12">The record does not contain the evidence produced at the trial by either plaintiff or defendants and makes no showing of the merit, if any, of plaintiff’s claim. See Ray v. Carr, <ref href="cite:71-app-dc-37" cx:cite="71 App. D.C. 37">71 App.D.C. 37</ref>, <ref href="cap:f2d/107/0238-01" cx:cite="107 F.2d 238">107 F.2d 238</ref>.</p></authorialNote></p>
            <p cx:origin="producer"><omissis>[…]</omissis><eop refersTo="#printing_31-a2d-683" number="685" cx:scan="733"/><omissis>[…]</omissis><eop refersTo="#printing_31-a2d-683" number="686" cx:scan="734"/><omissis>[…]</omissis></p>
            <p eId="opinion_opinion.hood__p_11" cx:blocks="BL_734.4">Affirmed.</p>
          </content>
        </hcontainer>
        <hcontainer name="dissent" eId="opinion_dissent.cayton" cx:part="us/dc/57/1943-04-06/dissent.cayton" cx:authors="cayton" cx:sourceType="dissent">
          <heading cx:blocks="BL_734.5"><opinion type="dissenting" by="#cayton">CAYTON, Associate Judge</opinion></heading>
          <content>
            <p eId="opinion_dissent.cayton__p_1" cx:blocks="BL_734.6">(dissenting).</p>
            <p eId="opinion_dissent.cayton__p_2" cx:blocks="BL_734.7">I think a plain injustice has been done in this case and that the judgment should be reversed.</p>
            <p cx:origin="producer"><omissis>[…]</omissis><eop refersTo="#printing_31-a2d-683" number="687" cx:scan="735"/><omissis>[…]</omissis></p>
          </content>
        </hcontainer>
      </motivation>
    </judgmentBody>
  </judgment>
</akomaNtoso>
```

## 15. Source mappings

These tables say where each profile element comes from in each source. Field and class names were checked against CAP volumes `a2d/31` and `us/347` and against stare-builder's CourtListener record builder (`pipelines/courtlistener/src/stare_courtlistener/record.py`); a source field not listed has no place in the document.

### 15.1 CAP case JSON

| CAP field | Profile |
|---|---|
| `id` | `cx:source/@caseId` |
| `file_name`, with the volume's reporter and number | `cap:` alias: `FRBRalias @name="cap"`, `TLCReference` of the source, `cx:source/@record` |
| `name_abbreviation` | `FRBRWork/FRBRname` |
| `name` | not used; the printed caption comes from the HTML |
| `decision_date` | key input; `FRBRdate @name="decided"`; `docDate/@date`. A date with no month or day is a key refusal (`incomplete-date`) |
| `docket_number` | key input (CRK spec section 5); `FRBRnumber`. The printed form comes from the HTML |
| `court.name`, `court.id` | key input: the court code, mapped to the court registry (`engine-output`) |
| `jurisdiction` | not used |
| `citations[]` with `type` `official` or `parallel` | one printing each: `TLCReference`, `cx:printing @type`; and a `cite:` alias |
| `citations[]` with `type` `nominative` | `cx:cite @type="nominative"` on the printing whose pages it names |
| `citations[]` with `type` `vendor` | `FRBRalias @name="vendor"`, verbatim |
| `citations[]` with `type` `neutral` | `neutral:` alias |
| `first_page`, `last_page` | `cx:printing/@firstPage`, `@lastPage` of the official printing |
| `first_page_order`, `last_page_order` | `cx:scans/@first`, `@last` |
| `casebody.opinions[].type` | the part's role (15.4); `@cx:sourceType` |
| `casebody.opinions[].author` | key input: author slugs via the judge registry (`engine-output`); the heading text comes from the HTML |
| `casebody.opinions[].text` | not used when the HTML is available; the HTML carries the same text with structure |
| `casebody.head_matter`, `.parties`, `.judges`, `.attorneys` | not used when the HTML is available |
| `casebody.corrections` | not mapped; the empty string in every case of both sample volumes |
| `cites_to[]` | the category of a citation link that has no `data-case-paths` (section 15.2); each citation is marked where it occurs in the HTML |
| `analysis.ocr_confidence` | `cx:confidence @value @basis="CAP analysis.ocr_confidence" @scope="case"` |
| `analysis.sha256` | `cx:source/@sha256`, as given |
| `analysis` (other fields) | not used |
| `last_updated` | `cx:source/@lastUpdated` |
| `provenance` | not used; `cx:source/@method` is `ocr` |

### 15.2 CAP case HTML

| CAP HTML | Profile |
|---|---|
| `section.casebody @data-firstpage @data-lastpage` | check against `cx:printing/@firstPage`, `@lastPage` |
| `section.head-matter` children | `header` blocks in order, `@class` as below, `@cx:origin="unknown"` |
| `h4.parties` | `p @class="parties"` with `docTitle` |
| `p.docketnumber` | `p @class="docketnumber"` with `docketNumber` |
| `p.court` | `p @class="court"`, with `courtType` only as section 6 allows |
| `p.citation` | `p @class="citation"` |
| `p.decisiondate` | `p @class="decisiondate"` with `docDate` |
| `p.otherdate` | `p @class="otherdate"`, optionally with `date` (`engine-output`) |
| `p.attorneys` | `p @class="attorneys"` |
| `p.judges` | `p @class="judges"`, optionally with `judge` (`engine-output`) |
| head matter `p` with no class | `p @class="headmatter"` |
| any other head matter class | `p` or `blockContainer` with the class if it is in the vocabulary of section 6, `headmatter` if not |
| `article.opinion @data-type` | a part `hcontainer`; role per 15.4; `@cx:sourceType` |
| `p.author` | the part's `heading`, wrapped in `opinion`; the part's `subheading` when paragraphs precede the byline (section 7.2) |
| elements of `article.opinion` before `p.author` | `span @eId` in the part's `heading` (section 7.2) |
| `p` in an opinion | `p @eId` |
| `p` with a class other than `author` in an opinion | `p @eId @class @cx:origin` (section 8.4) |
| `blockquote` | `block @name="blockquote"` |
| `@data-blocks` on any of the above | `@cx:blocks` (block ids only) |
| `a.page-label @data-label` (`*684`) | `eop @number`, `@refersTo` the printing CAP transcribed; `@cx:scan` read from the `data-blocks` of the block where the label falls, as section 9.1 says (`engine-output`). `data-citation-index` was `1` on every label in both sample volumes |
| `a.footnotemark @href` | the position of an `authorialNote` (in a part) or a `noteRef` (in head matter) |
| `aside.footnote @data-label` | the note's content and `@marker` |
| `a.citation @data-cite @data-case-paths @data-case-ids` | a `ref` with `@cx:cite` from `data-cite`, or unmarked text, as below |
| `em` and other inline formatting | `i` and the matching AKN HTML inline elements |
| element `id` (`b731-32`) | not used |

A CAP citation link (`a.citation`) is classified in this order [AKN-51]:

1. A link with `data-case-paths` cites a decision: a `ref` whose `@href` is the `cap:` alias of its one path, or the `cite:` alias when it has several (section 10).
2. Otherwise, the producer finds the case's `cites_to[]` entry whose `cite` equals the link's `data-cite` once all whitespace is removed from both. If its `category` begins `reporters:`, the citation is a decision: a `ref` with the `cite:` alias, or the `neutral:` alias for `reporters:neutral`. Any other category (`laws:`, `journals:`) leaves the citation unmarked text (section 10, O9).
3. A link with neither stays unmarked text.

The `cite:` and `neutral:` aliases are formed from `data-cite`, never from `cites_to[].cite`.

### 15.3 CourtListener

A CourtListener record is a cluster with its docket, court, citations and opinions. Field names are CourtListener's, as stare-builder reads them.

| CourtListener | Profile |
|---|---|
| cluster `id` | `cl-cluster:` alias; source `TLCReference`; `cx:source/@record` |
| opinion `id` | `cl-opinion:` alias of the part: `@cx:aliases` on its `hcontainer` |
| cluster `case_name`, `case_name_short`, `case_name_full` | `FRBRname`; a header block of class `parties` with `@cx:origin="producer"` when no printed caption is available |
| docket `docket_number` | key input; `FRBRnumber` |
| docket `court_id` | key input: the court code, from the court registry entry with that code, checked by the producer |
| cluster `date_filed` | key input; `FRBRdate @name="decided"`. A cluster flagged as having an approximate date gives no key (`incomplete-date`) |
| cluster citations | printings and aliases as for CAP (15.1), after stare-builder's typing into `official`, `parallel`, `neutral`, `vendor` |
| opinion `type` | the part's role, through stare-builder's map to CAP types (`OPINION_TYPES`) and then 15.4 |
| opinion `author_str`, `author` | key input: author slugs via the judge registry (`engine-output`) |
| opinion `per_curiam` | role `per-curiam` |
| opinion `joined_by` | `@cx:joinedBy` (`engine-output` when the slugs are mapped by the producer) |
| opinion text (the first non-empty of `html_with_citations`, `html_columbia`, `html_lawbox`, `xml_harvard`, `html`, `plain_text`) | the part's content; `cx:source/@textField` names the field. Star pagination in the text maps to `eop` only when the printing it belongs to is identified (`engine-output`) |
| links to `/opinion/{id}/...` in `html_with_citations` | `ref @href="cl-cluster:{id}"` |
| cluster `syllabus`, `headnotes`, `summary`, `headmatter`, `posture`, `disposition`, `history`, `attorneys`, `judges` | header blocks of the same class (`headmatter` for `headmatter`), `@cx:origin="unknown"` |

### 15.4 Source opinion types to roles

| Source type (CAP `type`; CourtListener through stare-builder) | CRK role |
|---|---|
| `majority` | `opinion`; `per-curiam` when the byline, reduced to its letters and lowercased, is `percuriam`, `bythecourt` or `thecourt`, or CourtListener's `per_curiam` is set |
| `unanimous` | `opinion` |
| `plurality` | `plurality` |
| `concurrence` | `concurrence`. A producer MAY refine it to `concurrence-in-judgment` or `concurrence-in-part-and-judgment` from the printed heading (`(concurring in result)`); the refinement is `engine-output` |
| `concurring-in-part-and-dissenting-in-part` | `partial` |
| `dissent` | `dissent` |
| `rehearing`, `addendum`, `remittitur`, `on-the-merits`, `on-motion-to-strike-cost-bill` | none in this version (open question O8); the producer refuses the document |

OCR'd forms of `By the Court` (`By the Coubt.`) stay unmatched by the `majority` row; they are refused as `unregistered-author` until a person corrects the source or a later version lists such forms.

## 16. Validation

### 16.1 Now

The reference validator, `validator/validate.py` (`mise run validate [PATH ...]`), checks each `*.akn.xml` against the vendored Akoma Ntoso 1.0 schema and, if it is schema-valid, against the Schematron rules in `schema/profile.sch`, run with Saxon HE and the vendored SchXslt2 transpiler. It checks each `*.sidecar.json` against `schema/sidecar.schema.json` and, when the document it indexes sits beside it, against that document (section 16.3). Each finding names the rule id at the start of the Schematron message, `AKN-1` for a schema failure, or `sidecar-schema` or `sidecar-document` for a sidecar. With no paths it checks `examples/` and `vectors/akn-profile/`.

`uv run pytest` checks:

- the vendored Akoma Ntoso schema and SchXslt2 files against their SHA-256 pins;
- for every `*.akn.xml` under `examples/`: validity against the schema; that the work and expression URIs are key references, and the keys they name and every `@cx:part` pass the CRK grammar and validity rules, with each part's decision key equal to the work key; and that every example has a sidecar;
- for `examples/minimal`, that the keys are the ones the CRK rules compute from the printed facts, and that the copy in section 14 is identical to the file;
- that the Schematron's key regex is the CRK spec's, byte for byte, and that its key, key reference and alias functions agree with the CRK test vectors;
- that the Schematron checks every rule section 16.2 assigns to it, except AKN-28, AKN-45 and AKN-53 (below), and that a vector exercises every rule it checks;
- every document and sidecar vector in `vectors/akn-profile/`: the validator reports exactly the rule ids the vector expects;
- every vector in `vectors/akn-profile/cap-mapping.jsonl`, against a reading of the CAP mappings for roles (section 15.4), citation links (section 15.2) and `@cx:scan` (section 9.1).

`mise run check` runs ruff, the validator and pytest, as CI does.

### 16.2 Rules and what enforces them

The Schematron rules are in `schema/profile.sch` (codexpublicus/exemplar#3). This table is its checklist. Three rules the table assigns to Schematron within a range have no assertion of their own: AKN-28 (parts in printed order) and AKN-45 (an `eop` sits where its page begins) can't be checked from the document alone, and AKN-53 is covered by AKN-51, since every `ref` must target a decision.

| Rule | Requirement | Enforced by |
|---|---|---|
| AKN-1 | valid against the Akoma Ntoso 1.0 schema | XSD |
| AKN-2 | `cx:profile/@version` present | Schematron |
| AKN-3 | no document for a regional reprint | not machine-checkable |
| AKN-4 | root `akomaNtoso`, one `judgment`, no `components` | XSD (root and type); Schematron (no `components`) |
| AKN-5, AKN-6 | `judgment/@name`, `@contains` values | Schematron |
| AKN-7 | no `coverPage`, `conclusions`, `attachments`, `components` | Schematron |
| AKN-8, AKN-19, AKN-21 | `@source` and manifestation author reference the producer | Schematron |
| AKN-9, AKN-15 | work and expression URIs are key references to valid keys and agree with each other and with `@contains` | Schematron (regex from the CRK spec; calendar dates through `xs:date`) |
| AKN-10 | aliases well formed per CRK section 11.1; a key-shaped alias is named `crk` and is a key reference | Schematron |
| AKN-11, AKN-16 | `FRBRdate` names and values match the key's dates | Schematron |
| AKN-12, AKN-13 | work author is the court; country is `us` | Schematron |
| AKN-14, AKN-37 | no document without keys | not machine-checkable |
| AKN-17 | `FRBRauthoritative` is `false` | Schematron |
| AKN-18, AKN-20 | manifestation URI and format | Schematron |
| AKN-22 | reference eIds and hrefs follow the table in 5.2 | Schematron |
| AKN-23 | `cx:keys` lists a courts registry, and a judges registry when some part key has authors; registry URIs are absolute, the court registry's its raw file URL at a release tag | Schematron (the URL's shape; not whether the tag is a tag) |
| AKN-24, AKN-25 | each printing and source has its `cx:` record, and the reverse; a printing's `@text` is from the vocabulary, and a printing whose `@text` isn't `transcribed` is `engine-output` | Schematron (not whether `@ordinal` is present when another decision begins on the page, which needs the source's volume records) |
| AKN-26, AKN-27 | header blocks have `@class` from the vocabulary, `@cx:origin`, `@eId`; syllabus and headnotes are not `court` | Schematron |
| AKN-28 to AKN-36 | part `hcontainer` name, eId, `cx:part`, authors, joiners, `opinion/@by` and `opinion/@type` of the byline in `heading` or `subheading`, block placement | Schematron (key grammar via the CRK regex) |
| AKN-38, AKN-39 | no `background`, `arguments`, `remedies`; only parts in `motivation` and `decision` | Schematron |
| AKN-40 | paragraph eIds, title `span`s in a part's `heading` included, follow the pattern and increase within their container | Schematron |
| AKN-41, AKN-42 | eIds not shown as court numbering; text unaltered | not machine-checkable |
| AKN-43 | `@cx:blocks` syntax | Schematron; presence where the source had `data-blocks` is checked against the source by #4's example builder |
| AKN-44 | omission paragraphs are `producer` and have no eId | Schematron |
| AKN-45 to AKN-47, AKN-49 | `eop` and `eol` reference a printing; `@number` present | Schematron |
| AKN-48, AKN-52 | no invented page positions; no chosen target for an ambiguous link | not machine-checkable |
| AKN-50, AKN-51, AKN-53 | `ref/@href` non-empty, a key reference or an alias of a decision scheme | Schematron |
| AKN-54, AKN-55 | `authorialNote` and `note` attributes and eIds | Schematron |
| AKN-56 | `cx:keys/@provenance` present, and `engine-output` or `human-curated` | Schematron |
| AKN-57 | consumer presentation | not machine-checkable |
| AKN-58 | the no-text form | Schematron |
| AKN-59 | paragraphs printed before a byline are `span`s in `heading`, and the byline is in `subheading` | Schematron |
| AKN-60 | a classed paragraph inside a part has `@class` from the vocabulary and `@cx:origin` other than `court` | Schematron |

### 16.3 The viewer's sidecar

The JSON sidecar (#3, `schema/sidecar.schema.json`) is an index derived from the document; it adds no facts the document lacks except the bounding boxes. This profile expects it to carry: the profile version; the work, expression and manifestation URIs, as the document gives them (key references, and the manifestation URI); the parts (eId, part key with no prefix, role, authors); for each printing, each page number with the eId of the element its `eop` sits in; and for each `cx:blocks` id, its scan page and bounding box from CAP's `data-blocks`, which the viewer needs to highlight a paragraph on the archival PDF (codexpublicus/stare#51).

A printing's `pages` has one entry per `eop`, in document order, so a page number can appear more than once, for instance when a footnote runs onto a page that the text also begins. A consumer that needs one position for a page MUST use the first entry for that number whose `eId` is neither a note's nor inside one (an eId that begins `note_` or contains `__authorialNote_`), or, if every entry is inside a note, the first entry.

The sidecar has no version of its own. It is versioned with this profile: its `profile` field MUST equal the `cx:profile/@version` of the document it indexes, and its shape is the one this profile version defines.

### 16.4 Examples

codexpublicus/exemplar#4 builds complete documents from CAP cases: a single-opinion decision, a multi-opinion decision, a decision with parallel printings including a withheld regional reprint (sections 9.2 and 13.1), a decision under the reporter fallback, and a page where several decisions begin (13.2). Invalid counterparts go in `vectors/`.

## 17. Metadata crosswalk (informative)

Derived from a document, never the other way round. schema.org has no type for a court decision (the 2015 `USLegalDecision` proposal was not adopted; see the CRK research doc's survey), so the schema.org mapping uses `CreativeWork`.

| Profile | Dublin Core (`dcterms:`) | schema.org (JSON-LD) |
|---|---|---|
| work URI (decision key) | `identifier` | `identifier` |
| `FRBRalias` values | `identifier` (one per alias) | `identifier` as `PropertyValue` with `propertyID` the alias scheme |
| `FRBRname`; `docTitle` | `alternative`; `title` | `alternateName`; `name` |
| decided date | `issued` | `datePublished` |
| the court | `creator` | `author` (`Organization`) |
| `FRBRlanguage` | `language` (`en`) | `inLanguage` (`en`) |
| official printing's citation | `bibliographicCitation` | `identifier` (schema.org's `citation` is for works cited) |
| printings and sources (`cx:printing`, `cx:source`) | `hasFormat` | `workExample` (`CreativeWork` with `pageStart`, `pageEnd`) |
| the source this document was made from | `source` | `isBasedOn` |
| parts | `hasPart` | `hasPart` (`CreativeWork` with `identifier` the part key, `author` `Person`) |
| `ref/@href` targets | `references` | `citation` |
| revised expression and the first issue | `isVersionOf` | none |
| CRK `replaces` / `replaced-by` | `replaces` / `isReplacedBy` | none |
| `cx:source/@method`, `cx:confidence` | `provenance` (a statement) | none |

## 18. Versioning

This profile is versioned with [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html), separately from the CRK spec, because consumers pin it:

- **Major:** a change that makes a valid document invalid, or changes what an element or attribute means.
- **Minor:** a change that only adds: an optional element or attribute, a header class, an origin or provenance value, a source mapping.
- **Patch:** editorial changes and new examples that don't change any rule.

While the version is 0.x, a minor version MAY break these rules (SemVer item 4). This version, 0.3.0, follows CRK spec 0.3.0 and court registry `2026.10.18`. It is a minor version that breaks: a document records its profile version, and the Schematron rules check profile 0.3.x documents only. It writes in the owner's rulings of 2026-10-23 on the gaps listed in codexpublicus/exemplar#10:

- paragraphs printed before a byline are `span`s in the part's `heading`, and the byline moves to `subheading`; paragraph numbering doesn't change (section 7.2, AKN-59; codexpublicus/exemplar#15);
- a paragraph the source classes as head matter inside a writing keeps its place and carries `@class` and an origin other than `court` (sections 8.4, 12.1, AKN-60; codexpublicus/exemplar#16);
- `By the Court.` and `THE COURT.` bylines map to `per-curiam` (section 15.4; codexpublicus/exemplar#14);
- a head matter class `citation`, and `courtType` only on text that names the court (sections 6, 15.2; codexpublicus/exemplar#17);
- how `@cx:scan` is derived, break attributes only from source data, and which of several markers for a page a consumer uses (sections 9.1, 16.3; codexpublicus/exemplar#18, proposed as 0.2.1 and folded into this version);
- `@ordinal` is required when another decision begins on the page, and `@text` comes from the source's volume records, with a new value `released` (section 5.3; codexpublicus/exemplar#19);
- the order in which a CAP citation link is classified (section 15.2; codexpublicus/exemplar#20);
- a footnote's `@marker` is the note's label as the source gives it (sections 11.1, 11.2; codexpublicus/exemplar#21, proposed as 0.2.1 and folded into this version).

No key and no eId changes for a document whose parts have no `By the Court.` or `THE COURT.` byline. The previous version, 0.2.0, settled open question O2 by option (d), as ruled on codexpublicus/exemplar#4 (2026-10-18):

- the work, expression and manifestation URIs, a `ref/@href` that names a key, and the value of a key-shaped alias are key references, `crk:` followed by the key (sections 5.1, 10); a bare key there is invalid;
- a key-shaped alias is named `crk` (section 5.1.1);
- registry URIs are absolute, and the court registry's is its raw file URL at a release tag, so the court's and judges' hrefs are absolute (sections 5.2, 5.3);
- the sidecar's `profile` is a 0.2.x version and its URIs are key references (section 16.3).

`@cx:part` still holds the part key with no prefix. The version before it, 0.1.1, was a patch release of 0.1.0 that stated how to read six points the 0.1.0 text left ambiguous. A document records the profile version it follows (section 2); consumers SHOULD reject a document whose major version they don't implement, and, while the major version is 0, one whose minor version they don't implement.

## 19. Open questions

Non-normative. Each open question needs a decision from the owner; the text above implements the option marked "current" so that documents can be built and validated now. Settled questions keep their numbers.

- **O1. Extension namespace.** The `cx:` namespace is `https://codexpublicus.org/ns/exemplar`, and the profile version is an attribute. Options: (a) current; (b) put the major version in the namespace (`.../exemplar/1`), which makes a major change visible to XML tools; (c) a different URI.
- **O2. Absolute key URIs.** Settled in 0.2.0 by option (d), a URI scheme for keys: key references (`crk:us/dc/...`) and absolute registry URIs (sections 5.1, 5.2, 5.3, 10, 18).
- **O3. Expression URI of the first issue.** It equals the work URI. Options: (a) current; (b) always `@{decided}` for the first issue, which needs a CRK change, since CRK 0.1.0 reserves `@` for revisions; (c) a suffix outside the CRK grammar, like AKN's `/eng@{date}`.
- **O4. Manifestation URI.** `{expression}.akn.xml` names neither the producer nor its source. Options: (a) current, with the producer in `FRBRauthor` and the source in `cx:source`; (b) name both (`{expression}~{producer}@{release}.akn.xml`); (c) a content hash.
- **O5. Transcription corrections.** A corrected OCR text or an updated source record is a new manifestation of the same expression. Options: (a) current; (b) a new expression with `FRBRversionNumber`, treating the corrected text as a different version of the text; (c) record corrections inline (`ins`/`del` with provenance) in one manifestation.
- **O6. Parts without keys.** A part whose author isn't in the judge registry makes the producer refuse the whole document. Options: (a) current; (b) emit the part without `@cx:part`, with `@cx:keyRefusal` naming the CRK refusal class and an eId such as `opinion_{role}_{n}`, until the registry covers the judge. Under (a), coverage of CAP depends on the judge registry's coverage.
- **O7. Decisions without a decision key.** No document is written. This covers every Supreme Court decision before 1971-07-01 (no docket profile in CRK 0.1.0), every Federal Circuit decision, and every decision dated only to the year or month. Options: (a) current, waiting for CRK profiles and dates; (b) a document identified by a non-canonical alias (`cap:...`) marked as such, replaced when a key exists; (c) a resolver record without a document.
- **O8. CAP opinion types with no role.** `rehearing`, `addendum`, `remittitur`, `on-the-merits` and `on-motion-to-strike-cost-bill` writings make the producer refuse. Options: (a) current; (b) a separate decision with its own key (it often has its own date, sometimes printed only in the head matter's `otherdate`); (c) a part of the same decision with role `statement` or `order`; (d) a new CRK role (a CRK minor version).
- **O9. Citations to legislation.** They stay unmarked. Options: (a) current; (b) `ref` with an alias scheme for legislation, which the CRK spec doesn't have (see codexpublicus/stare#9); (c) `ref` to an external URL.
- **O10. Origin of CAP head matter.** CAP doesn't say who wrote each head matter block, so all of it is `unknown`. Options: (a) current; (b) a table of defaults per reporter and period (for example, the U.S. Reports syllabus as `reporter`), applied as `engine-output`.
- **O11. Parties.** CAP gives the caption as one string; party markup is optional. Options: (a) current; (b) require `party` elements with roles, which needs caption parsing (`engine-output`).
- **O12. Disposition.** The outcome ("Affirmed.") is not marked. Options: (a) current; (b) `analysis/judicial/result` with AKN's result types, from the text (`engine-output`) or from a source field such as CourtListener's `disposition`.
- **O13. Scan pages and the archival PDF.** `@cx:scan` and `cx:scans` use CAP's page order. Whether a page's index in the archival PDF (codexpublicus/stare#51) equals its CAP page order hasn't been checked here. Options: (a) state that they are equal, once checked; (b) record the PDF page separately.
- **O14. CRK section 15 wording.** It describes a part as an inline `<opinion>` with the part's eId; this profile puts the eId on an `hcontainer` and the `opinion` in its heading (section 7.1). Options: (a) a CRK patch release aligning the informative text; (b) leave it.
