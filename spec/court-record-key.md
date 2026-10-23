# Court record key

Specification version: **0.4.0** (draft). Status: not yet stable; see section 13.

A court record key (CRK) is a deterministic identifier for a court decision and for each separately headed writing within it. It is built only from facts the court prints on the decision: the jurisdiction and the court, the docket number, the decision date, and, for a separate writing, its role and author as printed in its heading. Anyone holding those facts computes the same key without the court's cooperation. This version registers the courts of the United States, of five US territories, and the few English and colonial courts American sources hold (section 3).

```
{country}/{court}/{docket}/{decided}[~n][/{role}[.{author}[+{author}...]][~n]][@{revised}]
```

- `us/ca10/14-9585/2016-08-23` is a decision.
- `us/ca10/14-9585/2016-08-23/concurrence.gorsuch` is one writing within it.
- `us/scotus/25-365/2026-06-30@2026-07-01` is a revised version of a decision.
- `pr/prsupreme/8561/1943-05-18` is a decision of the Supreme Court of Puerto Rico.
- `us/dakotasup/rpt.3-dakota-1/1882-05` is a decision the source dates only to May 1882.

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

country     = 2*16LC                            ; a jurisdiction code (section 3)
court       = LC *( LC / DIGIT / "-" )          ; from the court registry (section 4)
docket      = ( LC / DIGIT ) *( LC / DIGIT / "-" / "_" / "." )
                                                ; normalized per docket profile (section 5)
decided     = date / year-month / year          ; decision date, as precise as known (section 6)
revised     = date                              ; date of an amended/corrected version
date        = 4DIGIT "-" 2DIGIT "-" 2DIGIT      ; ISO 8601 calendar date
year-month  = 4DIGIT "-" 2DIGIT                 ; ISO 8601 reduced precision
year        = 4DIGIT

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

The following regular expression (POSIX ERE and PCRE, anchored) accepts exactly the strings the ABNF accepts. It differs from the regex in the research doc, which gorsuch-library tests against, in the country segment and the decision date (0.4.0, section 13).

```regex
^([a-z]{2,16})/([a-z][a-z0-9-]*)/([a-z0-9][a-z0-9_.-]*)/([0-9]{4}(-[0-9]{2}(-[0-9]{2})?)?)(~([2-9]|[1-9][0-9]+))?(/(opinion|per-curiam|plurality|concurrence|concurrence-in-judgment|concurrence-in-part-and-judgment|partial|partial-majority|dissent|statement|order|judgment|decree)(\.[a-z][a-z-]*(\+[a-z][a-z-]*)*)?(~([2-9]|[1-9][0-9]+))?)?(@[0-9]{4}-[0-9]{2}-[0-9]{2})?$
```

Implementations MUST match the whole string. In engines where `$` also matches before a final newline (Python's `re`, PCRE without `D`), they MUST use a whole-string match (`re.fullmatch`, `\z`) so that `us/ca10/14-9585/2016-08-23\n` is rejected.

### 2.3 Validity rules beyond the grammar

A string is a **valid key** when it matches the grammar and all of the following hold:

1. `country` is a jurisdiction code this version defines (section 3).
2. `decided` is a real Gregorian calendar date (`2016-02-30` matches the grammar and is not valid), or a year and a month `01` to `12`, or a year.
3. `revised`, if present, is a real calendar date and is not earlier than `decided`; a partial `decided` is compared by the first day of its period (section 6.2).
4. A part whose role is `per-curiam` has no authors.
5. A docket segment that begins `rpt.` is a reporter fallback (section 5.6) and MUST have the shape `rpt.{volume}-{reporter}-{page}` defined there.

A validator MUST reject a string that fails the grammar or any of these rules.

### 2.4 Characters and structure

A key uses lowercase ASCII letters, digits and `/ - _ . ~ + @` only. All of these are legal unescaped in a URL path ([RFC 3986](https://www.rfc-editor.org/rfc/rfc3986) `pchar`), so a key can be used directly as a URL path. Producers and resolvers MUST NOT percent-encode any character of a key, and MUST treat a percent-encoded form as a different string.

`/` separates levels. `~` is the only ordinal marker. `@` is the only version marker. The **decision key** of a key is its prefix up to and including the decision ordinal, without the part and without `@revised`.

### 2.5 Error classes

A validator that reports why it rejected a string SHOULD use these classes. When a string has more than one defect, the class is that of the leftmost defective component, in the order listed.

| Class | Meaning |
|---|---|
| `structure` | Not shaped like a key: empty, too few or too many `/`-separated segments, more than one `@` |
| `country` | Country segment is not a jurisdiction code this version defines (section 3) |
| `court` | Court segment fails the `court` rule (uppercase, leading digit, illegal character) |
| `docket` | Docket segment fails the `docket` rule, or is a malformed `rpt.` segment |
| `date` | `decided` fails the `decided` rule, or is not a calendar date, or names a month outside `01` to `12` |
| `ordinal` | A `~` ordinal is `~0`, `~1`, has a leading zero, or is not a number |
| `role` | The part's role is not in the role vocabulary |
| `author` | An author fails the `author` rule, or a `per-curiam` part has authors |
| `revised` | `revised` fails the `date` rule, is not a calendar date, or is earlier than `decided` |

### 2.6 Key references: the `crk` URI scheme

A key written where a URI is expected, such as a link or an identifier that other systems dereference, is a **key reference**: the scheme name `crk`, a colon, and the key, unchanged.

```abnf
crk-ref     = %s"crk:" crk
```

`crk:us/ca10/14-9585/2016-08-23` refers to that decision, and `crk:us/ca10/14-9585/2016-08-23/concurrence.gorsuch` to the concurrence. The scheme name is lowercase. Nothing comes between the colon and the key (no `//` authority, no leading `/`), and nothing follows the key (no query, no fragment); the key is not percent-encoded (section 2.4). A key reference is valid when the string after `crk:` is a valid key (section 2.3). A string without the prefix, or with it in another letter case, is not a key reference.

In RFC 3986 terms a key reference is an absolute URI with scheme `crk` and a rootless path, so a consumer never resolves it against the URL of the document it appears in. A resolver maps `crk:{key}` to the record for `{key}`, or, for a key-shaped alias (section 11.1), to the key it is an alias of. The `crk` scheme is not registered with IANA; neither are the alias schemes of section 11.1.

The prefix is not part of the key. A key is computed, compared, frozen and listed without it; a format that carries keys says which of its fields hold a key and which hold a key reference.

## 3. Jurisdiction

The first segment, the country segment, is the jurisdiction code of the sovereign or body whose court issued the decision. The same code is the jurisdiction segment of stare.pub's citation addresses (`/c/{code}/...`) and the Akoma Ntoso `FRBRcountry` of the decision's document (section 15), so a key, an address and a document name one jurisdiction one way.

A jurisdiction code is one of these:

1. **A country's [ISO 3166-1](https://www.iso.org/iso-3166-country-codes.html) alpha-2 code**, lowercased: `us`, `gb`.
2. **A territory's own ISO 3166-1 alpha-2 code**, for the courts the territory establishes: Puerto Rico `pr`, Guam `gu`, the U.S. Virgin Islands `vi`, American Samoa `as`, the Northern Mariana Islands `mp`. A federal court seated in a territory, such as the District Court for the District of Puerto Rico (`prd`), is a court of the United States and keys under `us`.
3. **A registered body code** for a regional or supranational court, one that sits for several states or for none, such as the Caribbean Court of Justice, `ccj`. A body code is three to sixteen lowercase letters, never two, so that no code ISO 3166-1 assigns later can collide with it; it is a short form of the body's own name.
4. **For a court whose sovereign has changed, the issuing sovereign's code**: the jurisdiction that issued the decision on its date, not the one that holds the territory now. That is the sovereign's ISO 3166-1 code, or the code of the state that continues it; where neither exists, a registered code formed as in item 3. A colonial court's decision before 1776-07-04 keys under `gb`, and the same court's decision from that day under `us`.

Courts of tribal nations key under `us` in this version; codexpublicus/exemplar#45 asks whether each nation gets its own code.

The codes this version defines:

| Code | Kind | Jurisdiction | Its registered courts |
|---|---|---|---|
| `us` | country | United States | federal and state courts, the courts of territories without an ISO code of their own (Dakota Territory), tribal courts |
| `pr` | territory | Puerto Rico | `prsupreme`, `prapp` |
| `gu` | territory | Guam | `guam`, `superctguam` |
| `vi` | territory | U.S. Virgin Islands | `virginislands`, `visuper`, `vimunict`, `vipolct` |
| `as` | territory | American Samoa | `amsamoa`, `amsamoatc` |
| `mp` | territory | Northern Mariana Islands | `nmi`, `cnmisuperct`, `cnmitrialct` |
| `gb` | country | the United Kingdom, continuing the Kingdoms of England and of Great Britain | `kingsbench`, `houseoflordsuk`, `highctjchuk`, `privycoun`, `nhprivycounnh`, and the American colonies' courts before 1776-07-04 |
| `ph` | country | the Philippines | `phillipines` |
| `ccj` | body | the Caribbean Court of Justice | none yet (codexpublicus/exemplar#25) |
| `hawaii` | historical sovereign | the Hawaiian Kingdom and the governments that followed it, before 1898-08-12 | Hawaii's courts before that day |
| `texas` | historical sovereign | the Republic of Texas, before 1846-02-19 | Texas's courts before that day |
| `vermont` | historical sovereign | the Vermont Republic, before 1791-03-04 | Vermont's courts before that day |

The court registry gives each court its code, by date where a court's decisions span a change of sovereign (section 10.1). A producer takes the code from the registry for the decision date and MUST NOT choose one. A code is added by a minor version of this spec (section 13); its courts are added by a registry version. A body code or a historical sovereign's code, once defined, is never reassigned. A validator conforming to this version MUST reject any code the table doesn't list, with class `country`.

## 4. Courts

The court segment is a code from the court registry (section 10.1). The registry's codes are Free Law Project's courts-db ids, taken from the snapshot the registry names; CourtListener's court ids, for courts courts-db lacks and CourtListener names; and codes the registry mints itself. A court code is unique across every jurisdiction.

| Court family | Code | Examples |
|---|---|---|
| US Supreme Court | `scotus` | `scotus` |
| Federal courts of appeals, district and bankruptcy courts | the courts-db id, which is the court's `*.uscourts.gov` host label (one exception, below) | `ca10`, `ca6`, `cod`, `meb` |
| State and territorial courts | the courts-db id | `mass`, `wis`, `wisctapp`, `prsupreme` |
| Historical and defunct courts | the courts-db id, CourtListener's id, or a code the registry mints | `circtdnj`, `cc`, `kyctapphigh` |
| Courts outside the United States | the courts-db id | `kingsbench`, `houseoflordsuk` |

The one federal court whose courts-db id is not its host label is the Bankruptcy Court for the District of Nebraska: courts-db gives `neb` to the Nebraska Supreme Court, so the bankruptcy court is `nebraskab`, not `neb`.

A producer MUST take the court code from the registry and MUST NOT construct one. A source that names a court by its own id is translated through the registry: an id an entry lists as an alias (CourtListener's `txctapp5` is an alias of `texapp`) gives that entry's code, and a CAP court id gives the code `registry/cap-courts.json` assigns it for the decision date (section 10.1). A court the source names by an id neither one lists is `unregistered-court`. Once minted, a court code MUST NOT be renamed or reused. A court that merges or splits gets a new code, and the old code stays valid for decisions issued under it. Federal codes match what the judiciary assigns; state and historical codes are not court-assigned, and are the one input to the key that the court itself doesn't supply.

## 5. Docket

The docket segment is the docket number as printed on the decision, normalized by the docket profile that the court registry assigns to the court for the decision date. When the registry assigns the court no profile for that date, a producer MUST refuse with `no-docket-profile` before looking at the docket; nothing else in this section applies, the reporter fallback included (section 5.6). If the decision lists several dockets (a consolidated case), the producer MUST use the first docket listed in the caption of the decision as first issued; every other docket becomes an alias (section 11).

### 5.1 Cleaning

Every profile first cleans the printed docket:

1. Trim surrounding whitespace, and replace U+2010, U+2011, U+2012, U+2013, U+2014 and U+2212 with `-`.
2. Remove a leading label, ignoring letter case: optionally one of the words `Docket`, `Case`, `Appeal`, `Appeals`, `Record`, `File`, `Gen.` or `General`, with an optional comma after it; then `No`, `Nos`, `Number` or `Numbers`, with an optional `.`; then an optional `,` or `:`; and the whitespace after the label. Other words before `No.` name a docket series and stay: `Civ. No. 15693` keeps `Civ. No.`, and `S. F. No. 16720` keeps `S. F. No.`.
3. Remove each comma that has a digit before it and exactly three digits after it, followed by a non-digit or the end: `31,079` becomes `31079`.
4. The docket lists several dockets when the label removed in step 2 was plural (`Nos.`, `Numbers`) or the docket contains `;`. Split it at each `;` and, under a plural label, also at each `,`, each `&` and each word `and`. The first non-empty item, with a label removed from it as in step 2, is the docket. If that item is only digits, and the last item is digits followed by whitespace and more text, that whitespace and text are appended to it: `Nos. 22 & 23 WAP 2015` gives `22 WAP 2015`. Every other item is another docket of the decision (section 11.1).
5. Remove one trailing `.`, unless the docket ends in `Orig.`.

A result that is empty or has no digit means the decision has no docket (section 5.6).

Known residue of these rules: an unlabelled list (`753, 763` in 500 Pa.) gives `753_763` under the `printed` profile; a hyphenated range (`Nos. 3493-3494`) stays whole; `Appeal No. E.D. Appeal Docket 1982`, printed without its number, gives `e.d.appealdocket1982`, a valid segment that no rule here can tell from a real docket.

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
2. Replace each comma that has a digit before it and, after any whitespace, a digit after it with `_`; delete every other comma. `131, 1997` gives `131_1997`; `31 E.D. Appeal Docket, 1982` gives `31e.d.appealdocket1982`, the same segment as the same docket printed without the comma.
3. Remove all whitespace.
4. Replace each `:` and `/` with `_`.
5. The result MUST match the `docket` rule and MUST NOT begin with `rpt.`.

Letter case-type codes are part of the docket wherever they appear and are kept: Louisiana `2004-CA-1580` becomes `2004-ca-1580`; Mississippi `95-KA-01234-SCT` becomes `95-ka-01234-sct`.

### 5.6 Reporter fallback: `rpt.`

When the court has a docket profile for the decision date, and the decision has no docket (the cleaned docket is empty or has no digit, or the source records none) or that profile rejects the docket it has, a producer MUST use the reporter fallback if the decision has a reporter citation, and MUST otherwise refuse (`no-docket` or `docket-profile`, section 12). This mostly affects historical Caselaw Access Project (CAP) cases whose scan carries no usable docket.

The fallback replaces only the docket. It needs the same complete decision date as any other key (section 6), so it never yields a key for a decision dated only to the year or month.

The fallback docket segment is `rpt.{volume}-{reporter}-{page}` where:

- the citation is the decision's first page in its official reporter, or, if it has no official reporter citation, in the reporter of the CAP volume it was taken from;
- `volume` and `page` are the citation's volume and first page as decimal digits;
- `reporter` is the reporter abbreviation reduced to a **slug**: lowercase it, delete `.`, `'`, `’`, `(`, `)` and `,`, and replace each run of whitespace with `-`. `Mass.` becomes `mass`, `F.3d` becomes `f3d`, `F. App'x` becomes `f-appx`, `F. Supp. 2d` becomes `f-supp-2d`.

```abnf
rpt-docket  = %s"rpt." 1*DIGIT "-" slug "-" 1*DIGIT
slug        = ( LC / DIGIT ) *( LC / DIGIT / "-" )
```

Example: 1 Mass. 1, decided 1804-03-01, gives `us/mass/rpt.1-mass-1/1804-03-01`.

When a decision takes the fallback, its decision ordinal (section 7) is its position, in the order the reporter prints them (CAP's file ordinal: `-01`, `-02`), among all the decisions that begin on the same reporter page and share its decision date, whether or not they take the fallback themselves. The first is unmarked and the second takes `~2`, even when no decision on the page has the unmarked fallback key. Glover, printed second on 500 Pa. 524 after the docketed Kibler and decided the same day, is `us/pa/rpt.500-pa-524/1983-04-27~2`.

A fallback key is **non-canonical**: it is deterministic, but it rests on a citation a publisher assigned after the fact, and the `rpt.` prefix marks that. If a docket number is later recovered, the producer mints the docket key and records the fallback key as `replaced-by` that key (section 11). The fallback key MUST NOT be deleted or reused.

The fallback is never used for a court that has no docket profile for the decision date (section 5): in this version, the Federal Circuit. A producer MUST refuse those decisions with `no-docket-profile` whether or not the decision has a docket or a reporter citation, because a profile added later would mint a docket key for decisions that already had a fallback key. The Supreme Court before 1971-07-01 has the `scotus-numbered` profile (section 5.7), and a decision of that period with no docket, or one the profile rejects, takes the fallback like any other.

### 5.7 Profile `scotus-numbered`: Supreme Court, dockets before 1971-07-01

Before 1971-07-01 the Supreme Court's docket numbers carry no year, and a number identifies a case only within its term and its docket (the appellate docket, the Miscellaneous docket, the Original docket). The key's decision date places the decision in its term, so the segment is the number and the docket it belongs to. The cleaned docket MUST match, ignoring case, one of:

| Kind | Printed | Pattern | Segment |
|---|---|---|---|
| Appellate | `No. 36`, `NO. 36` | `^\d{1,5}$` | the number: `36` |
| Miscellaneous | `No. 94, Misc.` | `^\d{1,5},? Misc\.?$` | the number and `-misc`: `94-misc` |
| Original | `No. 13, Original`, `No. 4. Original` | `^\d{1,3}[,.]? Orig(inal)?\.?$` | the number and `-orig`: `13-orig` |

Hilton's Administrator v. Jones, 159 U.S. 584, printed `No. 1.` and decided 1895-11-18, is `us/scotus/1/1895-11-18`. A list of dockets is keyed by its first (section 5.1): `No. 365; No. 366; No. 367; No. 368` gives `365`. A docket the profile rejects (a range, `Nos. 202-207`; a lower court's number a reprint prints in its place) or a decision with none takes the reporter fallback, as the decisions in 2 U.S. (2 Dall.) do: Chisholm v. Georgia, which CAP dates only to 1793, is `us/scotus/rpt.2-us-419/1793`.

Two decisions decided the same day can print the same number, by misprint (United States v. Alexander, 148 U.S. 186, and United States v. Truesdell, 148 U.S. 196, both print `No. 552.` and were decided 1893-03-06) or because CAP's metadata reads a case name's `(No. 1)` as a docket. They compute the same key, and the decision ordinal separates them (section 7): for this profile it is counted in the order the United States Reports prints them, volume then page, because the Court's docket entries for those terms are not available to a producer.

## 6. Decision date

`decided` is the date printed on the decision as the date of decision: "Decided" (Supreme Court), the "FILED" stamp date (courts of appeals), or the entry date of an order. A producer MUST NOT use the date an opinion was posted, published or received by a publisher.

### 6.1 Precision

`decided` is the complete calendar date when the producer can establish it, and otherwise as much of it as the producer can establish: the year and month (`1882-05`) or the year (`1793`). A producer MUST NOT pad a missing month or day, and MUST NOT write a part it can't establish: `1882-05-15` for a decision dated May 1882 presents an invented fact as the court's. A decision whose year can't be established has no key (`no-decision-date`).

A date is established when the decision prints it, or when another source states it for that decision: another printing of the decision, the court's records or docket, a dataset that records the date without marking it approximate. This spec doesn't supply dates; a consumer that generates data in exemplar's formats is responsible for determining them, and SHOULD record where a date it didn't take from the decision came from (provenance, not part of the key).

A date a source marks approximate is established only as far as the source knows it. CourtListener marks such a date `date_filed_is_approximate` and pads a year and month to the 15th and a year to 1 July: a flagged date on 1 July is established to its year, and any other flagged date to its year and month. A date a source doesn't flag but that is a fill value is not established past its month either: in CourtListener's 2026-09-30 export, 14,976 of the 14,993 unflagged clusters for North Carolina Reports cases that CAP dates only to the month fall on the 5th, and every one of the 827 for Rhode Island Reports on the 6th. A producer SHOULD check a second source's dates for fill values before relying on it.

### 6.2 Keys with a partial date

A key whose `decided` is a year and month, or a year, is a **partial-date key**. Like a fallback key (section 5.6) it is deterministic but **non-canonical**: if the full date is established later, the producer mints the full-date key and records the partial-date key `replaced-by` it (section 11.2). The partial-date key MUST NOT be deleted or reused.

A partial date is part of the key as written. Decisions in one court and docket dated `1882-05` and `1882-05-04` have different keys and are not counted against each other for an ordinal; two dated `1882-05` share a `decided` segment, and their decision ordinal (section 7) is counted in the order the reporter prints them (volume, page, then CAP's file ordinal), since no docket entry orders them.

Where a rule compares a partial date with a full date (the date a docket profile or a jurisdiction code applies from, a revision date), it uses the first day of the partial date's period: a decision dated `1971` takes the Supreme Court's `scotus-numbered` profile, and one dated `1776-07` keys under `gb`.

## 7. Ordinals

The first instance of anything is unmarked. Later instances take `~2`, `~3`, and so on, in decimal with no leading zero. `~0` and `~1` are invalid.

- **Decision ordinal.** When one court issues several separate decisions in one docket on one date (an opinion and a separately entered order on a motion, or two orders-list entries), the first is unmarked and the later ones take `~2`, `~3` in the order the court's docket records them (ascending docket-entry or document number). Under the reporter fallback, the ordinal is counted as section 5.6 says; for a partial-date key as section 6.2 says, and under the `scotus-numbered` profile as section 5.7 says. Writings issued together (an opinion with its concurrences and dissents, or an orders-list disposition with the statements appended to it) are one decision, not several.
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

A key depends on two registries: a court registry, which this repository publishes, and a judge registry, which it doesn't.

### 10.1 Court registry

The court registry is `registry/courts.json` in codexpublicus/exemplar, validated by `schema/courts-registry.schema.json`. Each entry has a court code (section 4), its jurisdiction code (`country`, section 3), the court's name, its docket profiles with the date each applies from (for example `scotus`: `scotus-numbered` from the start, `scotus-ot1971` from 1971-07-01), and the source of its code. A court whose decisions span a change of sovereign also lists its jurisdiction codes with the date each applies from (`countries`; `pa`: `gb`, then `us` from 1776-07-04), and its `country` is the last of them. An entry MAY list aliases, other services' ids for the court or for a part of it, written `{service}:{id}` (`courtlistener:txctapp5`), and a `replaced-by` code for a court that merged or split. Codes are never renamed, reused or deleted.

The registry is built by `registry/build_courts.py` from a copy of courts-db's `courts.json`, vendored at `registry/sources/courts-db/` and pinned by commit and SHA-256 in the registry's `source` block, which also records the license courts-db states for it. Every court in that snapshot is registered; the registry's `excluded` block lists the one id left out, which fails the `court` rule. Four courts courts-db lacks are registered under CourtListener's ids (`kyctapphigh`, `mspb`, `tennsuperct`, `tennworkcompcl`; source `courtlistener`). The jurisdiction codes, docket profiles and aliases are this registry's assignments, not courts-db's: a territory's own courts take its code and the courts of England and the Philippines theirs (section 3); a state court in one of the thirteen colonies or Maine takes `gb` before 1776-07-04, one in Hawaii `hawaii` before 1898-08-12, one in Texas `texas` before 1846-02-19 and one in Vermont `vermont` before 1791-03-04, unless courts-db dates its start after that day; `scotus-numbered` and then `scotus-ot1971` for the Supreme Court; `us-coa` for the twelve regional courts of appeals; `us-district` for federal district and bankruptcy courts; none for the Federal Circuit; `printed` for every other court.

`registry/cap-courts.json`, validated by `schema/cap-courts.schema.json`, gives the registry code for each court the Caselaw Access Project names, by CAP court id, with the date each code applies from where one CAP court is several registry courts over time (CAP's Kentucky Court of Appeals is `kyctapphigh` before 1976-01-01 and `kyctapp` from it). Each entry says how its code was found; the file is engine output for review, and the CAP courts it can't map are listed with the reason. It is versioned and pinned with the court registry.

### 10.2 Judge registry

This repository publishes no judge registry. Judge slugs come from a registry the consumer supplies and identifies by URI and version (section 10.3), such as one computed and published from the consumer's own corpus.

Whatever its source, a judge registry used with this spec MUST meet these rules. Each entry has a slug, the judge's name, and the court codes the slug is registered for. A slug matches `author` (`^[a-z][a-z-]*$`; no digits, so a second Justice Harlan is `harlan-ii`). A slug identifies one judge within each court it is registered for; a registry MAY make slugs unique across all courts, and SHOULD give a judge who sat on several courts one slug for all of them. Slugs are never renamed, reused or deleted.

An entry MAY list printed forms: the strings in which a source prints the judge's name in a byline, misprints and OCR errors included, each with the source it was seen in. A producer maps a byline to a slug only through an entry's name or printed forms, for the key's court. The name the byline prints matches a name or printed form when the two are equal, character for character, after both are case-folded (Unicode full case folding, as Python's `str.casefold()` does it): `HOOD` matches the name `Hood`, and `McDERMOTT` matches `McDermott`. Case folding is the only normalization. A byline that matches no entry, or more than one, is `unregistered-author`. A printed form is a fact about a source's text that a person has checked; a registry needn't list a form that differs from the name, or from another form, only in letter case. A producer MUST NOT match a byline to a name by edit distance, OCR correction or any other approximation.

### 10.3 Pinning

Each registry is published as numbered, immutable snapshots, each identified by a URI and a version. Registries are append-only: a later snapshot adds entries and never removes one or changes its code, the jurisdiction code or the profile it already assigns for a date. It MAY assign a profile for a date range that had none, once a version of this spec defines that profile. A key computed under an earlier snapshot is therefore still computable under a later one.

A producer MUST record, alongside the keys it mints (for example in a release manifest), the URI and version of each registry snapshot it used. The registry version is not part of the key.

| Registry | URI | Version |
|---|---|---|
| Courts | `https://raw.githubusercontent.com/codexpublicus/exemplar/{tag}/registry/courts.json` | `2026.10.23` |
| CAP courts | `https://raw.githubusercontent.com/codexpublicus/exemplar/{tag}/registry/cap-courts.json` | `2026.10.23` |
| Judges | supplied by the consumer | the consumer's |

The court registry's URI is the raw file URL of `registry/courts.json` at the release tag of codexpublicus/exemplar the consumer pins, with `{tag}` replaced by that tag, and its version is the `version` field in the file, a CalVer date (`YYYY.MM.DD`). The raw URL returns the registry file itself, as tagged; a `github.com/.../blob/{tag}/...` URL returns an HTML page about the file, whose fragments GitHub uses for its own line anchors. A judge registry's URI is an absolute URI that names one snapshot, chosen by whoever publishes it. This version of the spec is published with court registry `2026.10.23`. The test vectors resolve court codes against that registry and use a judges fixture (`vectors/court-record-key/judges-fixture.json`), which stands in for a consumer's judge registry and is not one.

## 11. Aliases and relations

### 11.1 Aliases

Every other identifier a decision or part carries is kept as an **alias** that resolves to its key. An alias is never a key and is never minted as one. A resolver MUST accept any registered alias and return the key or keys it resolves to. An alias MAY resolve to more than one key (a reporter page shared by several decisions; a GovInfo package covering every decision in a docket); a resolver MUST then return all of them and MUST NOT choose one.

Aliases are written `{scheme}:{value}`. A non-lead docket of a consolidated case is a key-shaped alias: a key reference (section 2.6) to the key the docket would have had. That key is never minted, and a resolver maps the reference to the lead docket's decision key.

| Scheme | Value | Example | Resolves to |
|---|---|---|---|
| `crk` | the key the docket would have had (key-shaped alias) | `crk:us/scotus/17-1623/2020-06-15` | the lead docket's decision key |
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
alias          = crk-ref / cite-alias / neutral-alias / scotus-r-alias / ca6-alias
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

A producer computes a key from: the court code, and the jurisdiction code the registry gives it for the decision date; the docket as printed (or none) and, for the fallback, a reporter citation; the decision date; the decision ordinal; and, for a part, the role, the author slugs and the part ordinal; and, for a version, the revision date. It MUST refuse rather than guess, and SHOULD report one of these classes:

| Class | When |
|---|---|
| `unregistered-court` | The court code is not in the court registry |
| `no-docket-profile` | The registry gives the court no docket profile for the decision date; checked before the docket, and the fallback doesn't apply (5.6) |
| `docket-profile` | The docket doesn't fit the profile, and there is no reporter citation for the fallback |
| `no-docket` | The decision has no docket, and no reporter citation for the fallback |
| `no-decision-date` | Not even the decision's year is known |
| `date` | The decision date is not a calendar date, or not a year and month, or a year |
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
- **Minor:** a change that only adds: a jurisdiction code, a role, a docket profile for a court or date range that had none, an alias scheme, an error class.
- **Patch:** editorial changes and new test vectors that don't change any expected result.

While the version is 0.x, a minor version MAY break these rules (SemVer item 4). Consumers pin a release tag of this repository and SHOULD record the spec version they implement.

**0.2.0.** This version changes two things from 0.1.0, under SemVer item 4: a key-shaped alias is written as a key reference, `crk:` followed by the key, and the bare key-shaped string is no longer an alias (sections 2.6 and 11.1); and the court registry's URI is an absolute URL that names the release tag (section 10.3). No key changes: the same facts compute the same key, and every valid key stays valid.

**0.4.0.** This version changes four things from 0.3.1, under SemVer item 4. The first is the owner's ruling D101 (2026-10-23) on codexpublicus/exemplar#38, #39, #42 and #43; the rest settle codexpublicus/exemplar#26, #27, #33 and #37 and the pre-1971 Supreme Court gap of #46, as proposed in the pull request that brought them:

- the country segment is a jurisdiction code (section 3): ISO 3166-1 codes, a territory's own code, registered body codes such as `ccj`, and the issuing sovereign for a court whose sovereign changed. The grammar admits any two to sixteen lowercase letters, and a validity rule admits the codes section 3 lists. **Changes keys**: a decision of a territory's own court moves from `us` to the territory's code (`us/prsupreme/...` is `pr/prsupreme/...`), a colonial court's decision before 1776-07-04 from `us` to `gb`, and decisions of Hawaii's courts before 1898-08-12, Texas's before 1846-02-19 and Vermont's before 1791-03-04 to `hawaii`, `texas` and `vermont`;
- `decided` is as precise as the producer can establish it, a full date, a year and month, or a year (section 6); a partial-date key is non-canonical, and its ordinal is counted in printed order. The refusal class `incomplete-date` is withdrawn. **Adds keys** for decisions 0.3.1 refused; a fallback decision's ordinal (section 5.6) can change when a neighbour on its page that had a partial date gets a full one;
- the Supreme Court has the `scotus-numbered` profile before 1971-07-01 (section 5.7), and its decisions of that period take the reporter fallback like any other court's. **Adds keys** for decisions 0.3.1 refused `no-docket-profile`;
- the court registry registers the courts courts-db lists outside the United States, four courts courts-db lacks under CourtListener's ids, and CourtListener's ids for the districts of the Court of Appeals of Texas and for the Supreme Court of the Northern Mariana Islands as aliases; `registry/cap-courts.json` gives the code for each court CAP names (section 10.1). **Adds keys** for decisions 0.3.1 refused `unregistered-court`, or that a producer refused for want of a mapping.

Registry `2026.10.23` changes the jurisdiction code of thirteen territorial courts, and assigns date-ranged codes to 971 courts, which section 10.3's append-only rule forbids outside a 0.x minor version. A producer that minted a key under 0.3.x that these rules compute differently records the 0.3.x key `replaced-by` the 0.4.0 key (section 11.2). Every key valid under 0.3.1 stays valid.

**0.3.1.** This patch release of 0.3.0 states how section 10.2's exact match treats letter case, as ruled on codexpublicus/exemplar#14 part b (2026-10-23): a byline matches a judge's name or printed form when the two are equal after case folding, and nothing is approximated. A registry that listed a judge's name only as `Hood` gave a byline printed `HOOD` no key under the 0.3.0 text; it now gives `hood`. No other key changes, unless a registry has two entries for one court whose names or forms differ only in letter case, which now makes a byline matching them `unregistered-author`. No vector's expected result changes.

**0.3.0.** This version changes three things from 0.2.0, under SemVer item 4, as ruled on codexpublicus/exemplar#12, #13 and #14 (2026-10-23):

- docket cleaning (section 5.1) removes more label forms, ignoring letter case, removes thousands separators, and keys a list of dockets by its first; the `printed` profile (section 5.5) turns a comma between digits into `_` and deletes every other comma. The same printed docket can give a different segment than under 0.2.0, and a decision that took the reporter fallback under 0.2.0 can now have a docket key;
- a fallback decision's ordinal counts every decision that begins on its page and shares its date, whether or not that decision takes the fallback (sections 5.6, 7), which settles a reading 0.2.0 left open;
- a judge registry entry MAY list printed forms of the judge's name, matched exactly (section 10.2), which adds keys for parts that 0.2.0 refused and changes none.

A producer that minted a key under 0.2.0 that these rules compute differently records the 0.2.0 key `replaced-by` the 0.3.0 key (section 11.2). Every valid key stays valid.

**Registry versions.** The court registry has its own CalVer version (section 10.3). Adding courts, or assigning an existing profile to a court or date range that had none, is a new registry version and not a new spec version. A release tag of this repository pins both.

## 14. Test vectors

`vectors/court-record-key/` holds language-neutral vectors as JSON Lines, one object per line; `manifest.json` there describes each file's fields.

| File | Checks |
|---|---|
| `parse.jsonl` | key to parts, and parts back to the same key (round trip) |
| `reject.jsonl` | strings a validator rejects, with the error class (section 2.5) |
| `compute.jsonl` | facts to key, or to a refusal class (section 12) |
| `docket.jsonl` | printed docket to docket segment, per profile |
| `byline.jsonl` | the name a byline prints to a judge slug, through the judge registry's names and printed forms |
| `alias.jsonl` | printed identifier to alias string, and alias to key |

Every vector records its `provenance`:

- `human-curated`: a person checked it against the primary source. Ground truth; where it disagrees with any other vector, it wins.
- `hand-checked`: taken from a worked example in the research doc.
- `engine-output`: taken from an implementation's tests or output (gorsuch-library), or computed from a source's records (CAP's case metadata, CourtListener's export) by the rules here; it shows what the data and an implementation give, not what is correct.
- `spec-derived`: constructed from this document's rules to exercise an edge case, and not yet checked by a person.

## 15. Interop mappings (informative)

These are derived from a key, never canonical. For `us/ca10/14-9585/2016-08-23`:

- Akoma Ntoso work IRI: `/akn/us/judgment/ca10/2016-08-23/14-9585`, expression `…/eng@2016-08-23`. A part maps to an inline `<opinion>` with `eId` `opinion_concurrence.gorsuch`. The IRI's first segment is the key's country segment: `pr/prsupreme/8561/1943-05-18` is `/akn/pr/judgment/prsupreme/1943-05-18/8561`.
- URN:LEX ([RFC 9676](https://www.rfc-editor.org/rfc/rfc9676.html)): `urn:lex:us:court.appeals.10.circuit:decision:2016-08-23;14-9585`. The US jurisdiction table is empty, so the authority name is not standardized.
- ECLI-shaped string: `ECLI:US:CA10:20160823:14.9585`. This is not a real ECLI; the US has no ECLI coordinator.

## 16. Open issues

Non-normative. Each is a gap this version leaves for a later one.

- The Federal Circuit's dockets (`2021-1234`) need a profile.
- The Eleventh Circuit's letter suffix is dropped, but its meaning is unverified.
- `registry/cap-courts.json` is engine output: its 3,248 mappings need review, and 206 CAP courts (6,134 cases) have no code.
- The `us-district` profile is assigned to historical district courts, whose dockets predate the PACER form and so fall to `rpt.`; they may want a profile of their own.
- Codes for tribal nations (codexpublicus/exemplar#45), and courts that sit for several states, such as the Privy Council in its modern jurisdiction (codexpublicus/exemplar#42).
- `gb` stands for the Kingdom of England before 1707 as the state the United Kingdom continues; the colonies' change of sovereign is dated 1776-07-04 for all thirteen, although some broke with the Crown earlier and New York's courts sat under it until 1783.
- The decision ordinal when a docket doesn't record which of two decisions came first is settled only for partial-date keys (section 6.2) and the `scotus-numbered` profile (section 5.7); codexpublicus/exemplar#29 asks about the rest.
