# Court record key

Specification version: **0.1.0** (draft). Status: not yet stable; see section 13.

A court record key (CRK) is a deterministic identifier for a US court decision and for each separately headed writing within it. It is built only from facts the court prints on the decision: the court, the docket number, the decision date, and, for a separate writing, its role and author as printed in its heading. Anyone holding those facts computes the same key without the court's cooperation.

```
us/{court}/{docket}/{decided}[~n][/{role}[.{author}[+{author}...]][~n]][@{revised}]
```

- `us/ca10/14-9585/2016-08-23` is a decision.
- `us/ca10/14-9585/2016-08-23/concurrence.gorsuch` is one writing within it.
- `us/scotus/25-365/2026-06-30@2026-07-01` is a revised version of a decision.

The research behind this design, including the survey of alternatives and the sources for each docket profile, is codexpublicus/gorsuch-library `docs/research/2026-09-25-case-identifier-recommendation.md` ("the research doc"). This document supersedes it as the normative source. Where the two disagree, this document governs and the disagreement is a bug in one of them.

## 1. Conventions

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in BCP 14 ([RFC 2119](https://www.rfc-editor.org/rfc/rfc2119), [RFC 8174](https://www.rfc-editor.org/rfc/rfc8174)) when, and only when, they appear in all capitals, as shown here.

Grammar is ABNF ([RFC 5234](https://www.rfc-editor.org/rfc/rfc5234)) with the case-sensitive string extension of [RFC 7405](https://www.rfc-editor.org/rfc/rfc7405) (`%s"..."`). Plain RFC 5234 string literals are case-insensitive, which would admit `US/` and `OPINION`; every literal in this grammar is therefore written `%s"..."`. `DIGIT` is the RFC 5234 core rule.

Terms:

- **Decision.** One issuance by a court, on one date, in one docket or consolidated group of dockets. It includes the judgment and every writing issued with it. This is the FRBR *work*.
- **Part.** A separately headed writing within a decision: the opinion of the court, a concurrence, a dissent, a statement, and so on.
- **Version.** A later amended, corrected or revised issuance of the same decision with no new judgment. This is the FRBR *expression*.
- **Mint.** To compute a key for a decision or part and publish it.
- **Producer.** An implementation that computes keys from facts. **Validator.** An implementation that checks a string against this grammar and the validity rules. **Resolver.** An implementation that maps a key or alias to a record.

## 2. Grammar

### 2.1 ABNF

```abnf
crk         = country "/" court "/" docket "/" decided [ ord ]
              [ "/" part ] [ "@" revised ]

country     = %s"us"                            ; section 3
court       = LC *( LC / DIGIT / "-" )          ; from the court registry (section 4)
docket      = ( LC / DIGIT ) *( LC / DIGIT / "-" / "_" / "." )
                                                ; normalized per docket profile (section 5)
decided     = date                              ; decision date printed on the document
revised     = date                              ; date of an amended/corrected version
date        = 4DIGIT "-" 2DIGIT "-" 2DIGIT      ; ISO 8601 calendar date

part        = role [ "." authors ] [ ord ]
role        = %s"opinion" / %s"per-curiam" / %s"plurality" / %s"concurrence"
            / %s"concurrence-in-judgment" / %s"concurrence-in-part-and-judgment"
            / %s"partial" / %s"partial-majority" / %s"dissent"
            / %s"statement" / %s"order" / %s"judgment" / %s"decree"
authors     = author *( "+" author )            ; order as printed in the heading
author      = LC *( LC / "-" )                  ; judge slug from the judge registry

ord         = "~" ( %x32-39 / %x31-39 1*DIGIT ) ; 2, 3, ... ; the first instance is unmarked
LC          = %x61-7A                           ; a-z
```

### 2.2 Regular expression

The following regular expression (POSIX ERE and PCRE, anchored) accepts exactly the strings the ABNF accepts. It is byte-identical to the regex in the research doc, which gorsuch-library tests against.

```regex
^us/([a-z][a-z0-9-]*)/([a-z0-9][a-z0-9_.-]*)/([0-9]{4}-[0-9]{2}-[0-9]{2})(~([2-9]|[1-9][0-9]+))?(/(opinion|per-curiam|plurality|concurrence|concurrence-in-judgment|concurrence-in-part-and-judgment|partial|partial-majority|dissent|statement|order|judgment|decree)(\.[a-z][a-z-]*(\+[a-z][a-z-]*)*)?(~([2-9]|[1-9][0-9]+))?)?(@[0-9]{4}-[0-9]{2}-[0-9]{2})?$
```

Implementations MUST match the whole string. In engines where `$` also matches before a final newline (Python's `re`, PCRE without `D`), they MUST use a whole-string match (`re.fullmatch`, `\z`) so that `us/ca10/14-9585/2016-08-23\n` is rejected.

### 2.3 Validity rules beyond the grammar

A string is a **valid key** when it matches the grammar and all of the following hold:

1. `decided` is a real Gregorian calendar date (`2016-02-30` matches the grammar and is not valid).
2. `revised`, if present, is a real calendar date and is not earlier than `decided`.
3. A part whose role is `per-curiam` has no authors.
4. A docket segment that begins `rpt.` is a reporter fallback (section 5.6) and MUST have the shape `rpt.{volume}-{reporter}-{page}` defined there.

A validator MUST reject a string that fails the grammar or any of these rules.

### 2.4 Characters and structure

A key uses lowercase ASCII letters, digits and `/ - _ . ~ + @` only. All of these are legal unescaped in a URL path ([RFC 3986](https://www.rfc-editor.org/rfc/rfc3986) `pchar`), so a key can be used directly as a URL path. Producers and resolvers MUST NOT percent-encode any character of a key, and MUST treat a percent-encoded form as a different string.

`/` separates levels. `~` is the only ordinal marker. `@` is the only version marker. The **decision key** of a key is its prefix up to and including the decision ordinal, without the part and without `@revised`.

### 2.5 Error classes

A validator that reports why it rejected a string SHOULD use these classes. When a string has more than one defect, the class is that of the leftmost defective component, in the order listed.

| Class | Meaning |
|---|---|
| `structure` | Not shaped like a key: empty, too few or too many `/`-separated segments, more than one `@` |
| `country` | Country segment is not one this version defines |
| `court` | Court segment fails the `court` rule (uppercase, leading digit, illegal character) |
| `docket` | Docket segment fails the `docket` rule, or is a malformed `rpt.` segment |
| `date` | `decided` fails the `date` rule or is not a calendar date |
| `ordinal` | A `~` ordinal is `~0`, `~1`, has a leading zero, or is not a number |
| `role` | The part's role is not in the role vocabulary |
| `author` | An author fails the `author` rule, or a `per-curiam` part has authors |
| `revised` | `revised` fails the `date` rule, is not a calendar date, or is earlier than `decided` |

## 3. Country

The first segment is the country whose courts issued the decision, as a lowercase [ISO 3166-1](https://www.iso.org/iso-3166-country-codes.html) alpha-2 code. This version defines one country, `us`. Each further country (for example `bz` for Belize) needs its own court registry and docket profiles and is added by a minor version of this spec (section 13). A validator conforming to this version MUST reject any other country code with class `country`.

## 4. Courts

The court segment is a code from the court registry (section 10.1).

| Court family | Code source | Examples |
|---|---|---|
| US Supreme Court | fixed | `scotus` |
| Federal courts of appeals, district and bankruptcy courts | the court's `*.uscourts.gov` host label | `ca10`, `ca6`, `cod`, `meb` |
| State and territorial courts | the court registry, seeded from a frozen snapshot of Free Law Project's courts-db ids | registry-assigned |
| Historical and defunct courts | courts-db, or a code the registry mints | registry-assigned |

A producer MUST take the court code from the registry and MUST NOT construct one. Once minted, a court code MUST NOT be renamed or reused. A court that merges or splits gets a new code, and the old code stays valid for decisions issued under it. Federal codes are judiciary-assigned; state and historical codes are not, and are the one input to the key that the court itself doesn't supply.

## 5. Docket

The docket segment is the docket number as printed on the decision, normalized by the docket profile that the court registry assigns to the court for the decision date. If the decision lists several dockets (a consolidated case), the producer MUST use the first docket listed in the caption of the decision as first issued; every other docket becomes an alias (section 11).

### 5.1 Cleaning

Every profile first cleans the printed docket:

1. Trim surrounding whitespace.
2. Remove a leading label `No.`, `Nos.`, `Docket No.` or `Case No.`, with the whitespace after it.
3. Replace U+2010, U+2011, U+2012, U+2013, U+2014 and U+2212 with `-`.
4. Remove one trailing `.`, unless the docket ends in `Orig.`.

An empty result means the decision has no docket (section 5.6).

### 5.2 Profile `scotus-ot1971`: Supreme Court, dockets from 1971-07-01

The cleaned docket MUST match, ignoring case, one of:

| Kind | Printed | Pattern | Segment |
|---|---|---|---|
| Paid and IFP | `22-451`, `24-5774` | `^\d{2}-\d{1,5}$` | lowercased: `22-451` |
| Application | `20A87` | `^\d{2}A\d{1,5}$` | lowercased: `20a87` |
| Motion | `23M12` | `^\d{2}M\d{1,5}$` | lowercased: `23m12` |
| Original, electronic id | `22O141` | `^22O\d{1,3}$` | lowercased: `22o141` |
| Original, printed form | `141, Orig.`, `No. 141, Orig.` | `^\d{1,3},? Orig\.?$` | `22o` + the number: `22o141` |

Original cases carry the fixed prefix `22O` whatever year they were docketed (22O137 was docketed in 2007 and 22O160 in 2024). The printed form `N, Orig.` is kept as an alias. Numbering restarts on July 1, not at the start of the October Term.

### 5.3 Profile `us-coa`: federal courts of appeals

1. Remove a trailing Eleventh Circuit letter suffix (`21-14319-F` becomes `21-14319`).
2. Remove a trailing Second Circuit lead marker `(L)`, with any space before it.
3. The result MUST match `^\d{2}-\d{3,5}$`. The segment is the result unchanged: `14-9585`, `25-70019`. GovInfo's zero-padding (`14-09585`) MUST NOT be applied.

The Federal Circuit's four-digit-year dockets (`2021-1234`) don't fit this profile and need their own (section 16).

### 5.4 Profile `us-district`: federal district and bankruptcy courts

The cleaned docket MUST match, ignoring case, `^(\d):(\d{2})-([a-z]{1,4})-(\d{1,5})(-[a-z]{2,4})*$`, the PACER `o:yy-tp-nnnnn` form with optional judge initials. The segment is `{o}_{yy}-{tp}-{nnnnn}`, lowercased, with the judge initials removed: `1:17-cv-02523-PAB-STV` becomes `1_17-cv-02523`. Clerks append judge initials and change them on reassignment, so they are never part of the key. The result matches GovInfo's form (`USCOURTS-meb-2_10-ap-02064`).

### 5.5 Profile `printed`: state, territorial and other courts

1. Lowercase the cleaned docket.
2. Remove all whitespace.
3. Replace each `:` and `/` with `_`.
4. The result MUST match the `docket` rule and MUST NOT begin with `rpt.`.

Letter case-type codes are part of the docket wherever they appear and are kept: Louisiana `2004-CA-1580` becomes `2004-ca-1580`; Mississippi `95-KA-01234-SCT` becomes `95-ka-01234-sct`.

### 5.6 Reporter fallback: `rpt.`

When the decision has no docket (the cleaned docket is empty or the source records none), or the court's profile rejects the docket it has, a producer MUST use the reporter fallback if the decision has a reporter citation, and MUST otherwise refuse (`no-docket` or `docket-profile`, section 12). This mostly affects historical Caselaw Access Project (CAP) cases whose scan carries no usable docket.

The fallback docket segment is `rpt.{volume}-{reporter}-{page}` where:

- the citation is the decision's first page in its official reporter, or, if it has no official reporter citation, in the reporter of the CAP volume it was taken from;
- `volume` and `page` are the citation's volume and first page as decimal digits;
- `reporter` is the reporter abbreviation reduced to a **slug**: lowercase it, delete `.`, `'`, `’`, `(`, `)` and `,`, and replace each run of whitespace with `-`. `Mass.` becomes `mass`, `F.3d` becomes `f3d`, `F. App'x` becomes `f-appx`, `F. Supp. 2d` becomes `f-supp-2d`.

```abnf
rpt-docket  = %s"rpt." 1*DIGIT "-" slug "-" 1*DIGIT
slug        = ( LC / DIGIT ) *( LC / DIGIT / "-" )
```

Example: 1 Mass. 1, decided 1804-03-01, gives `us/mass/rpt.1-mass-1/1804-03-01`.

When several decisions begin on the same reporter page and share a decision date, the decision-level ordinal (section 7) separates them, in the order the reporter prints them (CAP's file ordinal: `-01`, `-02`).

A fallback key is **non-canonical**: it is deterministic, but it rests on a citation a publisher assigned after the fact, and the `rpt.` prefix marks that. If a docket number is later recovered, the producer mints the docket key and records the fallback key as `replaced-by` that key (section 11). The fallback key MUST NOT be deleted or reused.

The fallback is not used when the decision has a docket but the court has no docket profile for the decision date (section 16): the docket exists, and a profile added later would mint a second key for the same decision. A producer MUST refuse with `no-docket-profile`.

## 6. Decision date

`decided` is the date printed on the decision as the date of decision: "Decided" (Supreme Court), the "FILED" stamp date (courts of appeals), or the entry date of an order. A producer MUST NOT use the date an opinion was posted, published or received by a publisher.

The date MUST be a complete calendar date. When the source gives only a year, or a year and month, a producer MUST refuse with `incomplete-date` and MUST NOT pad the missing parts; a padded date would present an invented fact as the court's.

## 7. Ordinals

The first instance of anything is unmarked. Later instances take `~2`, `~3`, and so on, in decimal with no leading zero. `~0` and `~1` are invalid.

- **Decision ordinal.** When one court issues several separate decisions in one docket on one date (an opinion and a separately entered order on a motion, or two orders-list entries), the first is unmarked and the later ones take `~2`, `~3` in the order the court's docket records them (ascending docket-entry or document number). Writings issued together (an opinion with its concurrences and dissents, or an orders-list disposition with the statements appended to it) are one decision, not several.
- **Part ordinal.** When the same role and the same author list appear twice in one decision, the second takes `~2`, in the order printed. The same author in two different roles is already unique (Gorsuch wrote both the opinion and a concurrence in Gutierrez-Brizuela v. Lynch).

## 8. Parts: roles and authors

Each separately headed writing in a decision gets a part `/{role}[.{authors}][~n]`. A writing that isn't separately headed (a one-line "Justice X would grant the application") is not a part; it is metadata on the decision.

### 8.1 Roles

| Role | Writing |
|---|---|
| `opinion` | Opinion of the court (the lead opinion, whether or not it commands a majority) |
| `per-curiam` | Unsigned opinion of the court |
| `plurality` | Plurality opinion |
| `partial-majority` | Opinion of the court in part, plurality in the rest |
| `concurrence` | Concurring opinion |
| `concurrence-in-judgment` | Concurring in the judgment |
| `concurrence-in-part-and-judgment` | Concurring in part and concurring in the judgment |
| `partial` | Concurring in part and dissenting in part |
| `dissent` | Dissenting opinion, including dissent from denial |
| `statement` | Statement (e.g. respecting denial of certiorari) |
| `order` | Order |
| `judgment` | Judgment |
| `decree` | Decree |

The role vocabulary is the Codex Publicus `posture` vocabulary with `majority` renamed `opinion`; every other posture value maps to the role of the same name.

### 8.2 Authors

Each author is a judge slug from the judge registry (section 10.2), registered for the key's court. Joint authors are joined with `+` in the order the heading prints them: `plurality.kennedy+souter`. A `per-curiam` part MUST NOT have authors. A part whose heading names no author (an unsigned order) has none. A producer MUST NOT compute a slug from a name; an author absent from the registry for that court is a refusal (`unregistered-author`).

## 9. Versions

An amended, corrected or revised issuance of the same decision keeps the decision's key and adds `@{date of the revision}`. The bare key means the decision as first issued. `@` MAY follow a part, naming that writing within the revised version: `us/ca10/14-9585/2016-08-23/concurrence.gorsuch@{amended date}`.

A new decision gets a new key, not a version: an en banc decision, a decision after remand, an opinion on rehearing that the court says vacates and replaces the earlier one, an order granting rehearing. A version is anything the court labels amended, corrected, revised or errata with no new judgment. The two are linked with `replaces` and `replaced-by` (section 11).

## 10. Registries

A key depends on two maintained registries. This spec defines what they contain and how a consumer pins them; it does not fix where they are published.

### 10.1 Court registry

Each entry has a court code (section 4), its country, the court's name, and its docket profiles with the date range each applies to (for example `scotus`: `scotus-ot1971` from 1971-07-01, nothing before). An entry MAY list alias codes (other services' ids for the same court) and a `replaced-by` code for a court that merged or split. Codes are never renamed, reused or deleted.

### 10.2 Judge registry

Each entry has a slug, the judge's name, and the court codes the slug is registered for. A slug matches `author` (`^[a-z][a-z-]*$`; no digits, so a second Justice Harlan is `harlan-ii`). A slug identifies one judge within each court it is registered for; a registry MAY make slugs unique across all courts, and SHOULD give a judge who sat on several courts one slug for all of them. Slugs are never renamed, reused or deleted.

### 10.3 Pinning

Each registry is published as numbered, immutable snapshots, each identified by a URI and a version. Registries are append-only: a later snapshot adds entries and never changes or removes one, so a key computed under an earlier snapshot is still computable under a later one.

A producer MUST record, alongside the keys it mints (for example in a release manifest), the URI and version of each registry snapshot it used. The registry version is not part of the key.

| Registry | URI | Version |
|---|---|---|
| Courts | not yet assigned | |
| Judges | not yet assigned | |

Until the URIs are assigned, the test vectors carry their own fixture registry (`vectors/court-record-key/registry-fixture.json`), which is a test fixture and not a registry snapshot.

## 11. Aliases and relations

### 11.1 Aliases

Every other identifier a decision or part carries is kept as an **alias** that resolves to its key. An alias is never a key and is never minted as one. A resolver MUST accept any registered alias and return the key or keys it resolves to. An alias MAY resolve to more than one key (a reporter page shared by several decisions; a GovInfo package covering every decision in a docket); a resolver MUST then return all of them and MUST NOT choose one.

Aliases are written `{scheme}:{value}`, except that a non-lead docket of a consolidated case is written as a key-shaped string.

| Scheme | Value | Example | Resolves to |
|---|---|---|---|
| (key-shaped) | the key the docket would have had | `us/scotus/17-1623/2020-06-15` | the lead docket's decision key |
| `cite` | reporter citation, as `{volume}-{slug}-{page}` (slug as in 5.6) | `cite:834-f3d-1142` | a decision key |
| `neutral` | state or territorial neutral citation, as a slug (5.6 rule applied to the whole citation) | `neutral:2017-wi-1` | a decision key |
| `scotus-r` | Supreme Court Reporter's R-number, as `{term year}-{n}` | `scotus-r:2023-54` | a decision key |
| `ca6` | Sixth Circuit file number, lowercased | `ca6:26a0272p.06` | a decision key |
| `cmecf` | CM/ECF document id, as `{court}:{id}` | `cmecf:ca10:010110380264` | a decision key |
| `govinfo` | GovInfo package or granule id, verbatim | `govinfo:USCOURTS-ca10-14-09585` | the decision keys in that docket |
| `cap` | CAP static file `{reporter}/{volume}/cases/{file}.json`, as `{reporter}/{volume}/{file}` | `cap:us/410/0113-01` | a decision key |
| `cl-cluster` | CourtListener cluster id | `cl-cluster:{id}` | a decision key |
| `cl-opinion` | CourtListener opinion id | `cl-opinion:{id}` | a part key |

```abnf
alias          = crk / cite-alias / neutral-alias / scotus-r-alias / ca6-alias
               / cmecf-alias / govinfo-alias / cap-alias / cl-alias
cite-alias     = %s"cite:" 1*DIGIT "-" slug "-" 1*DIGIT
neutral-alias  = %s"neutral:" slug
scotus-r-alias = %s"scotus-r:" 4DIGIT "-" 1*DIGIT
ca6-alias      = %s"ca6:" 2DIGIT %s"a" 4DIGIT ( %s"p" / %s"n" ) %s".06"
cmecf-alias    = %s"cmecf:" court ":" 1*DIGIT
govinfo-alias  = %s"govinfo:" 1*( %x41-5A / LC / DIGIT / "-" / "_" )
cap-alias      = %s"cap:" slug "/" 1*DIGIT "/" 1*DIGIT "-" 2DIGIT
cl-alias       = ( %s"cl-cluster:" / %s"cl-opinion:" ) %x31-39 *DIGIT
```

Further schemes are added by a minor version.

### 11.2 Relations

- `replaces` / `replaced-by`: between a new decision and the decision it vacates and replaces; between a fallback key and the docket key that supersedes it; and between a wrongly minted key and its correction.

## 12. Computing a key (producer refusals)

A producer computes a key from: the country; the court code; the docket as printed (or none) and, for the fallback, a reporter citation; the decision date; the decision ordinal; and, for a part, the role, the author slugs and the part ordinal; and, for a version, the revision date. It MUST refuse rather than guess, and SHOULD report one of these classes:

| Class | When |
|---|---|
| `unregistered-court` | The court code is not in the court registry |
| `no-docket-profile` | The registry gives the court no docket profile for the decision date |
| `docket-profile` | The docket doesn't fit the profile, and there is no reporter citation for the fallback |
| `no-docket` | The decision has no docket, and no reporter citation for the fallback |
| `no-decision-date` | The decision date is unknown |
| `incomplete-date` | The decision date lacks a month or day |
| `date` | The decision date is not a calendar date |
| `unregistered-author` | An author is not in the judge registry for the court |
| `per-curiam-author` | A `per-curiam` part was given authors |
| `role` | The role is not in the vocabulary |
| `ordinal` | An ordinal is less than 1 |
| `revised` | The revision date is not a calendar date or is earlier than the decision date |

An ordinal of 1 means the first instance and produces no mark. Every key a producer emits MUST be a valid key (section 2.3).

## 13. Persistence and versioning

**Freeze at mint.** Once minted, a key MUST NOT change, even if a later version of the decision reorders the caption or corrects the date. A key minted wrongly is retired with a `replaced-by` relation and MUST NOT be reused.

**Spec versions.** This spec is versioned with [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html), because consumers pin it:

- **Major:** a change that makes the same facts compute a different key, or that makes a previously valid key invalid. Keys minted under an earlier major version stay valid and resolvable; a major version applies to keys minted after a producer adopts it.
- **Minor:** a change that only adds: a country, a role, a docket profile for a court or date range that had none, an alias scheme, an error class.
- **Patch:** editorial changes and new test vectors that don't change any expected result.

While the version is 0.x, a minor version MAY break these rules (SemVer item 4). Consumers pin a release tag of this repository and SHOULD record the spec version they implement.

## 14. Test vectors

`vectors/court-record-key/` holds language-neutral vectors as JSON Lines, one object per line; `manifest.json` there describes each file's fields.

| File | Checks |
|---|---|
| `parse.jsonl` | key to parts, and parts back to the same key (round trip) |
| `reject.jsonl` | strings a validator rejects, with the error class (section 2.5) |
| `compute.jsonl` | facts to key, or to a refusal class (section 12) |
| `docket.jsonl` | printed docket to docket segment, per profile |
| `alias.jsonl` | printed identifier to alias string, and alias to key |

Every vector records its `provenance`:

- `human-curated`: a person checked it against the primary source. Ground truth; where it disagrees with any other vector, it wins.
- `hand-checked`: taken from a worked example in the research doc.
- `engine-output`: taken from an implementation's tests or output (currently gorsuch-library); it shows what an implementation does, not what is correct.
- `spec-derived`: constructed from this document's rules to exercise an edge case, and not yet checked by a person.

## 15. Interop mappings (informative)

These are derived from a key, never canonical. For `us/ca10/14-9585/2016-08-23`:

- Akoma Ntoso work IRI: `/akn/us/judgment/ca10/2016-08-23/14-9585`, expression `…/eng@2016-08-23`. A part maps to an inline `<opinion>` with `eId` `opinion_concurrence.gorsuch`.
- URN:LEX ([RFC 9676](https://www.rfc-editor.org/rfc/rfc9676.html)): `urn:lex:us:court.appeals.10.circuit:decision:2016-08-23;14-9585`. The US jurisdiction table is empty, so the authority name is not standardized.
- ECLI-shaped string: `ECLI:US:CA10:20160823:14.9585`. This is not a real ECLI; the US has no ECLI coordinator.
## 16. Open issues

Non-normative. Each is a gap this version leaves for a later one.

- Supreme Court dockets before 1971-07-01 were not year-prefixed; their format needs a profile. Until then, producers refuse with `no-docket-profile`.
- The Federal Circuit's dockets (`2021-1234`) need a profile.
- Decisions whose source gives only a year or year and month have no key (section 6).
- The Eleventh Circuit's letter suffix is dropped, but its meaning is unverified.
- State court codes depend on a courts-db snapshot that hasn't been frozen.

