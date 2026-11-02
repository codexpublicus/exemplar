# Court record key

Specification version: **0.6.1** (draft). Status: not yet stable; see section 13.5.

The rules 0.5.0 adds were proposed as P1a to P4 and ruled by the owner in D123 (2026-10-26). The rules 0.6.0 adds were proposed on codexpublicus/exemplar#26, #28, #29, #50, #54, #55 and #56 and ruled by the owner in D154 (2026-10-28). The criteria for the official-reporter table (section 10.1) and the holding of printings a CourtListener cluster alone links (section 5.9), which 0.6.1 states, were ruled by the owner in D158 (2026-11-02) and D151 (1) (2026-11-02). Each is marked where its text begins, and section 13.5 lists them.

A court record key (CRK) is a deterministic identifier for a court decision and for each separately headed writing within it. It is built only from facts the court prints on the decision: the jurisdiction and the court, the docket number, the decision date, and, for a separate writing, its role and author as printed in its heading. Anyone holding those facts computes the same key without the court's cooperation. This version registers the courts of the United States, of five US territories, and the few English and colonial courts American sources hold (section 3).

```
{jurisdiction}/{court}/{docket}/{decided}[~n][/{role}[.{author}[+{author}...]][~n]][@{revised}]
```

- `us/ca10/14-9585/2016-08-23` is a decision.
- `us/ca10/14-9585/2016-08-23/concurrence.gorsuch` is one writing within it.
- `us/scotus/25-365/2026-06-30@2026-07-01` is a revised version of a decision.
- `pr/prsupreme/8561/1943-05-18` is a decision of the Supreme Court of Puerto Rico.
- `us/dakotasup/rpt.3-dakota-1/1882-05-00` is a decision dated, as far as any trustworthy source establishes, only to May 1882.

The research behind this design, including the survey of alternatives and the sources for each docket profile, is codexpublicus/gorsuch-library `docs/research/2026-09-25-case-identifier-recommendation.md` ("the research doc"). This document supersedes it as the normative source. Where the two disagree, this document governs and the disagreement is a bug in one of them.

## 1. Conventions

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in BCP 14 ([RFC 2119](https://www.rfc-editor.org/rfc/rfc2119), [RFC 8174](https://www.rfc-editor.org/rfc/rfc8174)) when, and only when, they appear in all capitals, as shown here.

Grammar is ABNF ([RFC 5234](https://www.rfc-editor.org/rfc/rfc5234)) with the case-sensitive string extension of [RFC 7405](https://www.rfc-editor.org/rfc/rfc7405) (`%s"..."`). Plain RFC 5234 string literals are case-insensitive, which would admit `US/` and `OPINION`; every literal in this grammar is therefore written `%s"..."`. `DIGIT` is the RFC 5234 core rule.

Terms:

- **Decision.** One issuance by a court, on one date, in one docket or consolidated group of dockets. It includes the judgment and every writing issued with it. This is the FRBR *work*.
- **Part.** A separately headed writing within a decision: the opinion of the court, a concurrence, a dissent, a statement, and so on.
- **Version.** A later amended, corrected or revised issuance of the same decision with no new judgment. This is the FRBR *expression*.
- **Mint.** To publish a key for a decision or part, recording a decision key in the publisher's minted-key ledger (section 13.2). A minted key keeps resolving to its decision (section 13.1).
- **Publisher.** Whoever mints keys and resolves them, such as stare.pub. A publisher keeps a minted-key ledger and publishes an errata list (section 13.4).
- **Producer.** An implementation that computes keys from facts. **Validator.** An implementation that checks a string against this grammar and the validity rules. **Resolver.** An implementation that maps a key or alias to a record.

## 2. Grammar

### 2.1 ABNF

```abnf
crk         = jurisdiction "/" court "/" docket "/" decided [ ord ]
              [ "/" part ] [ "@" revised ]

jurisdiction = 2*16LC                           ; a jurisdiction code (section 3)
court       = LC *( LC / DIGIT / "-" )          ; from the court registry (section 4)
docket      = ( LC / DIGIT ) *( LC / DIGIT / "-" / "_" / "." )
                                                ; normalized per docket profile (section 5)
decided     = date                              ; decision date, zeroed where not established (section 6)
revised     = date                              ; date of an amended/corrected version
date        = 4DIGIT "-" 2DIGIT "-" 2DIGIT      ; YYYY-MM-DD, always ten characters

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

The following regular expression (POSIX ERE and PCRE, anchored) accepts exactly the strings the ABNF accepts. It differs from the regex in the research doc, which gorsuch-library tests against, in the jurisdiction segment (0.4.0, section 13.5).

```regex
^([a-z]{2,16})/([a-z][a-z0-9-]*)/([a-z0-9][a-z0-9_.-]*)/([0-9]{4}-[0-9]{2}-[0-9]{2})(~([2-9]|[1-9][0-9]+))?(/(opinion|per-curiam|plurality|concurrence|concurrence-in-judgment|concurrence-in-part-and-judgment|partial|partial-majority|dissent|statement|order|judgment|decree)(\.[a-z][a-z-]*(\+[a-z][a-z-]*)*)?(~([2-9]|[1-9][0-9]+))?)?(@[0-9]{4}-[0-9]{2}-[0-9]{2})?$
```

Implementations MUST match the whole string. In engines where `$` also matches before a final newline (Python's `re`, PCRE without `D`), they MUST use a whole-string match (`re.fullmatch`, `\z`) so that `us/ca10/14-9585/2016-08-23\n` is rejected.

### 2.3 Validity rules beyond the grammar

A string is a **valid key** when it matches the grammar and all of the following hold:

1. `jurisdiction` is a jurisdiction code this version defines (section 3).
2. `decided` is a real Gregorian calendar date (`2016-02-30` matches the grammar and is not valid), or a zeroed date (section 6.2): a year from `0001`, a month `01` to `12` and the day `00` (`1882-05-00`), or a year from `0001` with month and day `00` (`1793-00-00`). `1882-00-05` is not valid.
3. `revised`, if present, is a real calendar date and is not earlier than `decided`; a zeroed `decided` is compared by the first day of its period (section 6.2).
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
| `jurisdiction` | Jurisdiction segment is not a jurisdiction code this version defines (section 3) |
| `court` | Court segment fails the `court` rule (uppercase, leading digit, illegal character) |
| `docket` | Docket segment fails the `docket` rule, or is a malformed `rpt.` segment |
| `date` | `decided` fails the `decided` rule, or is neither a calendar date nor a zeroed date (`2016-02-30`, `1882-13-00`, `1882-00-05`) |
| `ordinal` | A `~` ordinal is `~0`, `~1`, has a leading zero, or is not a number |
| `role` | The part's role is not in the role vocabulary |
| `author` | An author fails the `author` rule, or a `per-curiam` part has authors |
| `revised` | `revised` fails the `date` rule, is not a calendar date (a zeroed date included), or is earlier than `decided` |

### 2.6 Key references: the `crk` URI scheme

A key written where a URI is expected, such as a link or an identifier that other systems dereference, is a **key reference**: the scheme name `crk`, a colon, and the key, unchanged.

```abnf
crk-ref     = %s"crk:" crk
```

`crk:us/ca10/14-9585/2016-08-23` refers to that decision, and `crk:us/ca10/14-9585/2016-08-23/concurrence.gorsuch` to the concurrence. The scheme name is lowercase. Nothing comes between the colon and the key (no `//` authority, no leading `/`), and nothing follows the key (no query, no fragment); the key is not percent-encoded (section 2.4). A key reference is valid when the string after `crk:` is a valid key (section 2.3). A string without the prefix, or with it in another letter case, is not a key reference.

In RFC 3986 terms a key reference is an absolute URI with scheme `crk` and a rootless path, so a consumer never resolves it against the URL of the document it appears in. A resolver maps `crk:{key}` to the record for `{key}`, or, for a key-shaped alias (section 11.1), to the key it is an alias of. The `crk` scheme is not registered with IANA; neither are the alias schemes of section 11.1.

The prefix is not part of the key. A key is computed, compared, frozen and listed without it; a format that carries keys says which of its fields hold a key and which hold a key reference.

## 3. Jurisdiction

The first segment, the jurisdiction segment, is the jurisdiction code of the sovereign or body whose court issued the decision. The same code is the jurisdiction segment of stare.pub's citation addresses (`/c/{code}/...`) and the Akoma Ntoso `FRBRcountry` of the decision's document (section 15), so a key, an address and a document name one jurisdiction one way.

A jurisdiction code is one of these:

1. **A country's [ISO 3166-1](https://www.iso.org/iso-3166-country-codes.html) alpha-2 code**, lowercased: `us`, `gb`. A court outside the United States takes the code of the country it sits in. This version registers courts in Great Britain (`gb`) and the Philippines (`ph`) only; a court elsewhere takes its own country's code, which a minor version adds when the registry first registers a court there.
2. **A territory's own ISO 3166-1 alpha-2 code**, for the courts the territory establishes: Puerto Rico `pr`, Guam `gu`, the U.S. Virgin Islands `vi`, American Samoa `as`, the Northern Mariana Islands `mp`. A federal court seated in a territory, such as the District Court for the District of Puerto Rico (`prd`), the Virgin Islands (`vid`), Guam (`gud`) or the Northern Mariana Islands (`nmid`), is a court of the United States and keys under `us`.
3. **A registered body code** for a regional or supranational court, one that sits for several states or for none, such as the Caribbean Court of Justice, `ccj`. A body code is three to sixteen lowercase letters, never two, so that no code ISO 3166-1 assigns later can collide with it; it is a short form of the body's own name.
4. **For a court whose sovereign has changed, the issuing sovereign's code**: the jurisdiction that issued the decision on its date, not the one that holds the territory now. That is the sovereign's ISO 3166-1 code while it has one. A sovereign that no longer exists has a registered code formed as in item 3, defined with the date its sovereignty ended: the Kingdom of England `england`, until the Kingdom of Great Britain began on 1707-05-01; the Hawaiian Kingdom and the governments that followed it `hawaii`; the Republic of Texas `texas`; the Vermont Republic `vermont`. An English court's decision before 1707-05-01 keys under `england`, and from that day under `gb`. A colonial court's decision keys under `england` before 1707-05-01, under `gb` from that day, and under `us` from 1776-07-04, one date for all thirteen colonies.

Courts of tribal nations key under `us` in this version; codexpublicus/exemplar#45 asks whether each nation gets its own code.

The codes this version defines:

| Code | Kind | Jurisdiction | Its registered courts |
|---|---|---|---|
| `us` | country | United States | federal and state courts, federal courts seated in a territory, the courts of territories without an ISO code of their own (Dakota Territory), tribal courts |
| `pr` | territory | Puerto Rico | `prsupreme`, `prapp` |
| `gu` | territory | Guam | `guam`, `superctguam` |
| `vi` | territory | U.S. Virgin Islands | `virginislands`, `visuper`, `vimunict`, `vipolct` |
| `as` | territory | American Samoa | `amsamoa`, `amsamoatc` |
| `mp` | territory | Northern Mariana Islands | `nmi`, `cnmisuperct`, `cnmitrialct` |
| `gb` | country | the United Kingdom, continuing the Kingdom of Great Britain, from 1707-05-01 | `kingsbench`, `houseoflordsuk`, `highctjchuk`, `privycoun`, `nhprivycounnh` from 1707-05-01, and the American colonies' courts from that day to 1776-07-04 |
| `ph` | country | the Philippines | `phillipines` |
| `ccj` | body | the Caribbean Court of Justice | none yet (codexpublicus/exemplar#25) |
| `england` | historical sovereign | the Kingdom of England, before 1707-05-01 | `kingsbench`, `houseoflordsuk`, `highctjchuk`, `privycoun`, `nhprivycounnh` and the American colonies' courts, before that day |
| `hawaii` | historical sovereign | the Hawaiian Kingdom and the governments that followed it, before 1898-08-12 | Hawaii's courts before that day |
| `texas` | historical sovereign | the Republic of Texas, before 1846-02-19 | Texas's courts before that day |
| `vermont` | historical sovereign | the Vermont Republic, before 1791-03-04 | Vermont's courts before that day |

The court registry gives each court its code, by date where a court's decisions span a change of sovereign (section 10.1). A producer takes the code from the registry for the decision date and MUST NOT choose one. A code is added by a minor version of this spec (section 13); its courts are added by a registry version. A body code or a historical sovereign's code, once defined, is never reassigned. A validator conforming to this version MUST reject any code the table doesn't list, with class `jurisdiction`.

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

A producer MUST take the court code from the registry and MUST NOT construct one. A source that names a court by its own id is translated through the registry: an id an entry lists as an alias (CourtListener's `txctapp5` is an alias of `texapp`) gives that entry's code, and a CAP court id gives the code `registry/cap-courts.json` assigns it for the decision date (section 10.1). A court the source names by an id neither one lists is `unregistered-court`. A CAP court whose entry is marked for review gives no code until the mark is removed: the producer refuses its decisions with `court-under-review`, and MUST NOT mint a key with the code the entry gives. *Ruled (P4), D123 (2026-10-26):* a decision whose official citation is to the United States Reports from volume 5 (1 Cranch) on, the Supreme Court Reporter or the Lawyers' Edition is a decision of the Supreme Court, because those reporters print no other court's decisions (1 to 4 U.S., Dallas's reports, also print Pennsylvania and federal circuit decisions, and are not counted). When the source names another court for such a decision, the source has misfiled it: CAP files the Supreme Court's orders that the Federal Claims Reporter reprints under the Federal Circuit, and every decision of 421 U.S. under the Western District of Pennsylvania. *Ruled (#50), D154 (2026-10-28):* the producer computes its key under `scotus`, from the source's docket and date, under `scotus-numbered` before 1971-07-01 and `scotus-ot1971` from it, and with the fallback citation section 5.6 gives. It MUST refuse with `court-conflict` instead when the citation's volume isn't one whose decisions span the decision's date, which a real citation always is: the reporter registry (section 10.1) gives the first and last date of decision each volume of the four reporters prints, and a volume it doesn't list spans no date. `102 S. Ct. 671`, which CAP gives a Second Circuit decision of 1996, is refused, since volume 102 prints decisions of 1981 and 1982; so is `951 S.Ct. 564`, since the Supreme Court Reporter has no volume 951. If the decision carries several of these citations, the United States Reports decides, then the Supreme Court Reporter, then the Lawyers' Edition; they all name the same court, so the order matters only for the fallback citation. Under 0.5.x such a decision was refused `court-conflict` whatever its volume. Once minted, a court code MUST NOT be renamed or reused. A court that merges or splits gets a new code, and the old code stays valid for decisions issued under it. Federal codes match what the judiciary assigns; state and historical codes are not court-assigned, and are the one input to the key that the court itself doesn't supply.

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

The Federal Circuit has a profile of its own (section 5.8).

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

When the court has a docket profile for the decision date, and the decision has no docket (the cleaned docket is empty or has no digit, or the source records none) or that profile rejects the docket it has, a producer MUST use the reporter fallback if the decision has a reporter citation, and MUST otherwise refuse: with `no-docket` or `docket-profile` when it has no citation, and, from 0.6.0, with `citation` when its citation isn't a reporter citation (section 12). This mostly affects historical Caselaw Access Project (CAP) cases whose scan carries no usable docket.

The fallback replaces only the docket. Its decision date is the one section 6 gives any key, zeroed where the producer can't establish the day or the month.

The fallback docket segment is `rpt.{volume}-{reporter}-{page}` where:

- the citation is the decision's first page in its official reporter, or, if it has no official reporter citation, in the reporter of the volume it was taken from (for CAP, the CAP volume);
- *Ruled (P1b), D123 (2026-10-26):* when the official citation gives the volume number of the volume the decision was taken from, but another reporter, the reporter is that volume's: the citation's volume and page stay, and its reporter is replaced. Two abbreviations name another reporter when their slugs differ with every `-` removed, so `F. Supp. 2d` and `F.Supp.2d` are one reporter here (codexpublicus/exemplar#31 asks which slug that reporter takes). The official citation is usually transcribed from the volume, so a reporter that disagrees with the volume it names is a transcription error or another spelling of the volume's reporter: CAP's metadata cites `271 A.D.2d 1` for a decision of 1946 printed on page 1 of 271 A.D. (the second series began in 1955), and `1 Serg. & Rawle 1` for a decision in CAP's volume 1 of `Serg. & Rawl.`; they take `rpt.271-ad-1` and `rpt.1-serg-rawl-1`;
- `volume` and `page` are the citation's volume and first page as decimal digits. *Ruled (P3b), D123 (2026-10-26):* a volume numbered with a fraction is written with each space and `/` replaced by `-`: 81½ Pa., printed `81 1/2 Pa.`, is `81-1-2`, and its page 9 is `rpt.81-1-2-pa-9`;
- `reporter` is the reporter abbreviation reduced to a **slug**: lowercase it, delete `.`, `'`, `’`, `(`, `)`, `,` and, *ruled (P3a), D123 (2026-10-26),* `&`, and replace each run of whitespace with `-`. `Mass.` becomes `mass`, `F.3d` becomes `f3d`, `F. App'x` becomes `f-appx`, `F. Supp. 2d` becomes `f-supp-2d`, `Hay. & Haz.` becomes `hay-haz` and `Pa. D. & C.2d` becomes `pa-d-c2d`.

```abnf
rpt-docket  = %s"rpt." 1*DIGIT "-" slug "-" 1*DIGIT
slug        = ( LC / DIGIT ) *( LC / DIGIT / "-" )
```

Example: 1 Mass. 1, decided 1804-03-01, gives `us/mass/rpt.1-mass-1/1804-03-01`.

*Ruled (#56), D154 (2026-10-28).* A reporter citation is a volume, a reporter and a page of decimal digits; the volume is decimal digits, or a number with a fraction as above. An official citation in another form (a neutral citation such as `2011-NMCA-108`, a roman-numeral or lettered page, a page range) is not a reporter citation for the fallback, and is read only where this spec reads it for another purpose (section 4). A producer MUST look at the docket before it reads the citation: a decision whose docket its court's profile accepts has a docket key whatever its citation. Prather v. Lyons, cited `2011-NMCA-108` and docketed `No. 33,147; Docket No. 29,812`, is `us/nmctapp/33147/2011-10-25`, and Morris v. Everett, `3 Ark. App. 280-A`, docketed `E 81-269`, is `us/arkctapp/e81-269/1981-12-16`. When the fallback is needed and the decision has no reporter citation in this form, the producer refuses with `citation`: Le Roy v. Servis, which CAP cites `1 Cai. Cas. iii` and prints with no docket, has no key. The producer doesn't fall back to the page the source's volume prints the decision on when the official citation isn't a reporter citation: for a reprint, that page is the one P1a says doesn't count, and `1 McGrath 23½` would share the key of the decisions on page 23.

When a decision takes the fallback, its initial decision ordinal (sections 7, 13.2) is its position, in the order the reporter prints them (CAP's file ordinal: `-01`, `-02`), among all the decisions that begin on the same reporter page and share its decision date, whether or not they take the fallback themselves. The first is unmarked and the second takes `~2`, even when no decision on the page has the unmarked fallback key. Glover, printed second on 500 Pa. 524 after the docketed Kibler and decided the same day, is `us/pa/rpt.500-pa-524/1983-04-27~2`.

*Ruled (P1a, P1c), D123 (2026-10-26).* The reporter page is the page of the citation the fallback uses. The decisions counted are those in the volume the decision was taken from whose citation, given as above, is the same, whether or not they take the fallback themselves, in that volume's printed order. Where the volume is the official reporter and paged as the citation is, that is every decision on the volume's page. Where it isn't, the volume's page doesn't count: CAP's 21 Mass. (4 Pick.) is paged seven pages ahead of the official volume, and the two decisions of 1825-10-17 it prints on its page 175 are officially 21 Mass. 167 and 21 Mass. 168, so both are unmarked: `us/mass/rpt.21-mass-167/1825-10-17` and `us/mass/rpt.21-mass-168/1825-10-17`. Counted on CAP's page, the second would be `~2` on a page where no decision has the unmarked key. A decision whose official citation begins on another page than the volume's does not count on the volume's page either: 115 A.D. 908, a memorandum decision CAP files on its page 909, is counted on page 908. A decision taken from a volume of another reporter, such as a Federal Circuit decision reprinted in the Bankruptcy Reporter with an official citation to F.3d, is counted among the decisions in that volume only; if the official volume prints another decision on the page with the same date, the two can compute one candidate, and the ledger (section 13.2) gives the one minted second the next ordinal.

A fallback key is **non-canonical**: it is deterministic, but it rests on a citation a publisher assigned after the fact, and the `rpt.` prefix marks that. If a docket number is later recovered, the producer mints the docket key and records the fallback key as `replaced-by` that key (section 11). The fallback key MUST NOT be deleted or reused.

The fallback is never used for a court that has no docket profile for the decision date (section 5): in this version, the Federal Circuit before 1982-10-01, the day it began (section 5.8), under which a source can file decisions the court didn't issue (CAP files the decisions of 2 U.S. (2 Dall.) there). A producer MUST refuse those decisions with `no-docket-profile` whether or not the decision has a docket or a reporter citation, because a profile added later would mint a docket key for decisions that already had a fallback key. The Supreme Court before 1971-07-01 has the `scotus-numbered` profile (section 5.7), and a decision of that period with no docket, or one the profile rejects, takes the fallback like any other.

### 5.7 Profile `scotus-numbered`: Supreme Court, dockets before 1971-07-01

Before 1971-07-01 the Supreme Court's docket numbers carry no year, and a number identifies a case only within its term and its docket (the appellate docket, the Miscellaneous docket, the Original docket). The key's decision date places the decision in its term, so the segment is the number and the docket it belongs to. The cleaned docket MUST match, ignoring case, one of:

| Kind | Printed | Pattern | Segment |
|---|---|---|---|
| Appellate | `No. 36`, `NO. 36` | `^\d{1,5}$` | the number: `36` |
| Miscellaneous | `No. 94, Misc.` | `^\d{1,5},? Misc\.?$` | the number and `-misc`: `94-misc` |
| Original | `No. 13, Original`, `No. 4. Original` | `^\d{1,3}[,.]? Orig(inal)?\.?$` | the number and `-orig`: `13-orig` |

Hilton's Administrator v. Jones, 159 U.S. 584, printed `No. 1.` and decided 1895-11-18, is `us/scotus/1/1895-11-18`. A list of dockets is keyed by its first (section 5.1): `No. 365; No. 366; No. 367; No. 368` gives `365`. A docket the profile rejects (a range, `Nos. 202-207`; a lower court's number a reprint prints in its place) or a decision with none takes the reporter fallback, as the decisions in 2 U.S. (2 Dall.) do: Chisholm v. Georgia, which CAP dates only to 1793, is `us/scotus/rpt.2-us-419/1793-00-00`.

Two decisions decided the same day can print the same number, by misprint (United States v. Alexander, 148 U.S. 186, and United States v. Truesdell, 148 U.S. 196, both print `No. 552.` and were decided 1893-03-06) or because CAP's metadata reads a case name's `(No. 1)` as a docket. They compute the same candidate key, and the decision ordinal separates them: the initial ordinal is counted in the order the United States Reports prints them, because the Court's docket entries for those terms are not available to a producer, and it is frozen at minting like any other (section 13.2). From 0.6.0 this is a case of section 7.1's rule 2, which counts it the same way.

### 5.8 Profile `us-cafc`: the Federal Circuit, from 1982-10-01

*Ruled (P2), D123 (2026-10-26).* The Court of Appeals for the Federal Circuit began on 1982-10-01, when the Federal Courts Improvement Act of 1982 merged the appellate side of the Court of Claims with the Court of Customs and Patent Appeals. It has printed its dockets in four forms. Until 2005 it printed a two-digit year and a serial number (`No. 87-1054`), the form the regional circuits use; over 2006 and 2007 it changed to a four-digit year (`No. 2004-1582`, decided 2006-03-20), which its captions still print. CAP prints 49 of its dockets both ways. Its electronic docket gives the two-digit form for the same dockets (the CM/ECF header on an opinion captioned `No. 2021-1234` reads `Case: 21-1234`), and so do CourtListener's records of its decisions since 2020. Its petitions docket was printed without a year (`Misc. No. 922`, which CourtListener records as `2010-M922`) until 2012, and since then as a numbered docket of its own (`No. 2013-152`). In its first months it decided the appeals pending in the Court of Claims under that court's numbers (`Appeal No. 176-78`, `No. 255-79T`).

The cleaned docket MUST match, ignoring case, one of:

| Kind | Printed | Pattern | Segment |
|---|---|---|---|
| Four-digit year | `No. 2004-1582`, `2017-1515`, `No. 2013-152` | `^(19\|20)\d{2}-\d{3,5}$` | unchanged: `2004-1582` |
| Two-digit year | `No. 87-1054`, `Appeal No. 84-941`, `21-1234` | `^(\d{2})-(\d{3,5})$` | the year in four digits, `-`, the number: `1987-1054`, `2021-1234` |
| Miscellaneous docket | `Misc. No. 922`, `Miscellaneous No. 268`, `No. MISC. 721`, `2010-M922` | `^(misc(ellaneous)?\.?\s*(nos?\.?\s*)?\|((19\|20)?\d{2}-)?m)(\d{1,4})((,\|&\|and)\s*\d{1,4})*$` | the number and `-misc`: `922-misc` |
| Court of Claims number | `Appeal No. 176-78`, `No. 255-79T`, `Appeal No. 236-D` | `^\d{1,3}-(\d{2}[a-z]?\|[a-z])$` | lowercased: `176-78`, `255-79t` |

A list in the miscellaneous form (`Misc. Nos. 134, 135`) is keyed by its first number. A two-digit year from `82` to `99` is 1982 to 1999, and one from `00` to `81` is 2000 to 2081; the year is never ambiguous, because the court began in 1982. The four-digit segment is the form the court has printed on every docket since 2006; a decision printed with the four-digit year and one printed with the two-digit year in the same docket share the docket segment, so the 49 dockets CAP prints both ways, and the court's electronic docket, which prints `Case: 21-1234` for `No. 2021-1234`, give one key.

Before 1982-10-01 the court has no profile, and a decision a source files under it from before that day is refused `no-docket-profile` (section 5.6).

### 5.9 A decision printed more than once

*Ruled (#54), D154 (2026-10-28), limited to printings a second source links.* A producer that holds several printings of one decision computes one candidate key for it, though each printing alone would compute its own. Each fact comes from the printings as follows:

1. **Date.** The most precise date that every printing's date fits: `1905-00-00` from one printing and `1905-02-15` from another give `1905-02-15` (section 6.1 already counts another printing as a trustworthy source). If two printings give dates neither of which can be the other, the producer refuses with `printings-disagree`.
2. **Docket.** If the dockets the printings print, under the court's profile, give one segment, that segment, whichever printing prints it; a printing that prints no docket, or one the profile rejects, doesn't count against it. If they give different segments, the segment of the printing in the decision's official reporter.
3. **Fallback citation.** If no printing gives a docket segment, the citation of the printing in the decision's official reporter (section 5.6).
4. **Official reporter.** The reporter the reporter registry (section 10.1) names official for the decision's court and date, by date, each with the statute, rule, court order or session law that designates it, on one of the grounds section 10.1 lists (from 0.6.1, D158). Where the registry names none for the court and date, or no printing is in it, and rule 2 or 3 needs it, the producer refuses with `printings-disagree`.

Printings that give different courts are refused with `printings-disagree`. The decision ordinal is the one the chosen printing's own candidate has: the printing whose docket segment or citation the key takes, or, where several print that segment, the lowest of their ordinals. Every printing's citation stays a `cite:` alias of the key, and the printed-date alias is computed from the official printing, as section 6.3 says.

The printings of 553 Pa. 54, docketed `Petition No. 442 M.D. Allocatur Docket 1998`, and of 717 A.2d 530, with no docket, compute `us/pa/petitionno.442m.d.allocaturdocket1998/1998-09-24` and `us/pa/rpt.717-a2d-530/1998-09-24` alone; under rule 2 the decision is the first, and no official reporter is needed. 455 Md. 138, `No. 82`, and 166 A.3d 183, `No. 82, Sept. Term, 2016`, give two docket segments, and the decision takes the official printing's, once the registry names one.

**Which printings are one decision.** This section applies only to printings whose link a second source confirms. Printings are linked by a second source when every one of them is connected to the others, directly or through other printings of the group, by at least one of these:

- **a parallel citation**: the source of one printing lists, among that printing's citations, the citation of the other, or the sources of the two list one citation in common. A citation is the same when it gives the same volume and first page in the same reporter, under any of the reporter's abbreviations (`102 App. Div. 21` is `102 A.D. 21`). CAP's `citations` for a case, its official citation and its parallel ones, are such a source: 553 Pa. 54's record lists `717 A.2d 530`;
- **an official source**: the court's own record or docket, or the official reporter's table of cases or of parallel citations, that names both printings' citations for the decision;
- **a person's ruling**: a person has checked the two printings against each other and recorded that they are one decision (human-curated).

A link from an engine-made crosswalk alone, such as CourtListener's clusters, is not a second source, and neither is a producer's own matching of names, dates or dockets. Printings whose candidates differ and that only such a link connects are not keyed: the producer refuses them with `printings-disagree`, and they wait for a second source or a person. 161 Me. 1 and 206 A.2d 225, which one CourtListener cluster holds and whose CAP records list no parallel citation, stay refused, though rule 3 and an official-reporter entry for Maine would key them. A producer isn't required to link printings that a second source would link; one that holds them apart keys each printing as its own decision, as before 0.6.0. Printings whose candidates are the same need no second source for this section, since the key doesn't depend on which of them supplies a fact; section 7.1 says when they are one decision.

*Ruled, D151 (1) (2026-11-02); stated from 0.6.1.* Printings whose candidates differ and whose only link is an engine crosswalk (for CAP, a CourtListener cluster) are **held**: the producer refuses them with `printings-disagree`, and SHOULD record as the reason that no second source links them. They stay held whatever the reporter registry names, because rules 1 to 4 apply only to printings a second source links; an entry in the official-reporter table that would choose one of them doesn't release them. Brydle v. Honigbaum, printed at 18 C.C.P.A. 1517 (`No. 2750`) and 49 F.2d 963 (`Patent Appeal No. 2750`), keys `us/ccpa/2750/1930-06-05` under rules 2 and 4 when 18 C.C.P.A. 1517's record lists the parallel citation, and is held when a CourtListener cluster is the only link, though registry `2026.11.02` names C.C.P.A. official for the court. Held printings are released when a second source links them or a person rules on them; until then none of them has a key.

## 6. Decision date

`decided` is the date printed on the decision as the date of decision: "Decided" (Supreme Court), the "FILED" stamp date (courts of appeals), or the entry date of an order. A producer MUST NOT use the date an opinion was posted, published or received by a publisher.

### 6.1 The best trustworthy date at minting

`decided` is the most precise date of decision the producer can establish from trustworthy sources when it mints the key. A date is established when the decision prints it, or when a trustworthy second source states it for that decision: another printing of the decision, the court's records or docket, or a dataset that records the date without marking it approximate and without padding it. The part of the date the producer can't establish is zeroed (section 6.2). A producer MUST NOT pad a missing month or day: `1882-05-15` for a decision dated May 1882 presents an invented fact as the court's. A decision whose year can't be established has no key (`no-decision-date`).

This spec doesn't supply dates; a consumer that generates data in exemplar's formats is responsible for determining them, and SHOULD record where a date it didn't take from the decision came from (provenance, not part of the key).

A date a source marks approximate is established only as far as the source knows it. CourtListener marks such a date `date_filed_is_approximate` and pads a year and month to the 15th and a year to 1 July: a flagged date on 1 July is established to its year, and any other flagged date to its year and month. A date a source doesn't flag but that is a fill value is not established past its month either: in CourtListener's 2026-09-30 export, 14,976 of the 14,993 unflagged clusters for North Carolina Reports cases that CAP dates only to the month fall on the 5th, and every one of the 827 for Rhode Island Reports on the 6th. A producer SHOULD check a second source's dates for fill values before relying on it.

A second source's date establishes nothing that contradicts what the decision prints. Where the decision prints only a year and month, or only a year, a date from another source in another year, or in another month of a printed month, is not a date for that decision: the producer MUST NOT take it as `decided`, and it doesn't make the key provisional (section 13.3); the producer MAY record it as metadata. A source that gives one decision more than one date establishes none of them.

The date is the best one at minting, and the key keeps it (section 13.1). A date established later, more precise than the key's or different from it, doesn't change the key: the producer mints a new key with that date and records the old key `replaced-by` the new one, and the old key keeps resolving, as a redirect. Where trustworthy sources disagree about the date, the producer MAY mint the key provisional; a date the official report prints in full is made provisional only by an official or human-curated source (section 13.3).

### 6.2 Zeroed dates

When the producer can establish the year and month of a decision but not the day, `decided` is the year and month with the day `00`: `1882-05-00`. When it can establish only the year, the month and day are `00`: `1793-00-00`. A key with a zeroed date is as canonical as one with a full date, and stays the decision's key until a date established later replaces it (section 6.1).

*Ruled (#56), D154 (2026-10-28).* A date a source gives as a day that doesn't exist in its month (`1911-02-29`, `2016-02-30`) establishes its year and month only, and the day is zeroed: `1911-02-00`. Lay v. Postal Telegraph Cable Co., 171 Ala. 172, which CAP dates 1911-02-29, is `us/ala/rpt.171-ala-172/1911-02-00`. A date that gives no year, or a month outside `01` to `12`, establishes nothing, and the producer refuses with `date`. A zeroed day can hide a misread month (`02-29` for `03-29`); a date established later replaces the key as section 6.1 says, and a wrong month is an errata entry (section 13.4).

A zeroed date keeps the key's date segment ten characters wide, and sorts before every full date in its period. It is not an ISO 8601 date: ISO 8601 writes the same reduced precision `1882-05` and `1793`, and a producer reading dates in that form (CAP's `decision_date`) zeroes them. Where a rule or a format needs a calendar date, a zeroed date stands for the first day of its period, `1882-05-01` and `1793-01-01`: comparing it with the date a docket profile or a jurisdiction code applies from, or with a revision date, and the Akoma Ntoso `FRBRdate`, which the profile names `decided-year-month` or `decided-year` so that no consumer reads that day as the court's. So a decision dated `1971-00-00` takes the Supreme Court's `scotus-numbered` profile, and one dated `1776-07-00` keys under `gb`.

A zeroed date is part of the key as written. Decisions in one court and docket dated `1882-05-00` and `1882-05-04` have different keys and are not counted against each other for an ordinal; two dated `1882-05-00` share a `decided` segment, and their initial decision ordinals are counted in the order the reporter prints them (page, then CAP's file ordinal) when one volume prints both, since no docket entry orders them. From 0.6.0 this is a case of section 7.1's rule 2.

### 6.3 The printed-date alias

Each decision also has a **printed-date alias**, which anyone holding the volume can compute: `crk-printed:` followed by the decision key computed from the decision's printing in its official reporter alone, or, when it has no official reporter citation, from its printing in the reporter of the volume it was taken from (the printing section 5.6 cites). No other source is consulted:

- the jurisdiction and the court are those the registry gives for the printed date;
- the docket is the docket that printing prints, under the court's docket profile, or the reporter fallback for that printing's citation (section 5.6);
- `decided` is the date of decision as that printing prints it, zeroed as section 6.2 says;
- the decision ordinal counts, in the order the reporter prints them (volume, page, then position on the page), the decisions whose printed-date aliases are otherwise the same.

Hilton's Administrator v. Jones (159 U.S. 584) has the printed-date alias `crk-printed:us/scotus/1/1895-11-18`. The decision at 3 Dakota 1, which CAP dates only to May 1882, has `crk-printed:us/dakotasup/rpt.3-dakota-1/1882-05-00`; were a second source to establish the 4th, its key would be `us/dakotasup/rpt.3-dakota-1/1882-05-04` and the alias would stay as it is.

The alias is never minted and never a key. A resolver maps it to the decision's key, following `replaced-by` to the current one (section 13.1). After the prefix it is the same string as the key whenever the key was computed from the printed record and its ordinal didn't advance at minting (section 13.2); it differs when a second source established a better date, the key is a docket key whose ordinal the court's docket set, or the ledger advanced the ordinal.

## 7. Ordinals

The first instance of anything is unmarked. Later instances take `~2`, `~3`, and so on, in decimal with no leading zero. `~0` and `~1` are invalid.

- **Decision ordinal.** When one court issues several separate decisions in one docket on one date (an opinion and a separately entered order on a motion, or two orders-list entries), the first is unmarked and the later ones take `~2`, `~3` in the order the court's docket records them (ascending docket-entry or document number). Under the reporter fallback, the ordinal is counted as section 5.6 says; where the source doesn't give the docket's order, as section 7.1 says. These rules give the initial ordinals: once a key is minted its ordinal is frozen, and a decision keyed later takes the next free ordinal (section 13.2). Writings issued together (an opinion with its concurrences and dissents, or an orders-list disposition with the statements appended to it) are one decision, not several.
- **Part ordinal.** When the same role and the same author list appear twice in one decision, the second takes `~2`, in the order printed. The same author in two different roles is already unique (Gorsuch wrote both the opinion and a concurrence in Gutierrez-Brizuela v. Lynch).

### 7.1 Printings and decisions that compute one candidate

*Ruled (#55, #29, #28), D154 (2026-10-28).* A producer that holds several printings computing the same candidate key decides which of them are one decision, and then counts the decisions' initial ordinals. The rules below apply to printings that the producer hasn't already linked as one decision; a link between printings whose candidates differ is section 5.9's.

1. **One decision in two volumes** (#55). Printings in different volumes whose facts give the same candidate key, from a docket (not the fallback) and a full date, are one decision when either:
   1. they print the same case name, compared after case folding and with every character but letters and digits removed (`Jarrott v. State` and `JARROTT v. STATE.` are the same name); or
   2. their reporters are two editions of one report, as the reporter registry lists them (P.R. Dec., the Spanish edition, and P.R., the English one, of the Supreme Court of Puerto Rico's decisions).

   Section 1's definition of a decision, one issuance by a court on one date in one docket, is what the rule applies: same court, same docket, same date. The case name is the check against the one exception, several decisions in one docket on one date, which a source without docket entries can't show. An exact name misses variants: `Kelley v. State` (289 S.W. 73) and `Kelly v. State` (105 Tex. Crim. 405) aren't joined, because any approximation is a judgement a person can't reproduce.
2. **Printed order in one volume** (#29). When decisions compute the same candidate key and the source doesn't give the docket's entry order, their initial decision ordinals are counted in the order the reporter prints them (page, then position on the page) if one volume prints every one of them as a separate decision; a decision printed in that volume and elsewhere is counted by its printing there. A volume that prints two decisions separately is evidence that they are two decisions; it is not evidence about decisions printed in different volumes, which rules 1 and 3 cover. Sections 5.7 and 6.2 are this rule applied to `scotus-numbered` dockets and to zeroed dates. Construction Services of Samoa v. Bank of Hawaii, printed twice in 8 Am. Samoa 3d, at 109 and 114, both `CA No. 21-02` and decided 2004-01-28, is `as/amsamoa/cano.21-02/2004-01-28` and `~2`; the nineteen decisions of 231 A.D.2d docketed `Appeal No. 1` and decided 1996-09-27 are `us/nyappdiv/1/1996-09-27` to `~19`.
3. **Different names in one reporter** (#28). Decisions in different volumes of one reporter that compute the same docket key with a full date, and print different case names (compared as in rule 1), are different decisions. Their initial decision ordinals are counted in printed order: volume, page, then position on the page. Claster v. Soble (22 Pa. Super. 631) and Commonwealth Building & Loan Ass'n v. Steele (23 Pa. Super. 19), both `Appeal, No. 1` and decided 1903-05-04, are `us/pasuperct/1/1903-05-04` and `~2`.

Printings and decisions that compute one candidate and that none of these rules separates or joins are held for a person: the producer refuses them with `shared-candidate`, and a person rules which of them are one decision. Printings in different reporters whose names differ (`Kelley` and `Kelly` above), printings joined only by a fallback or a zeroed date, and groups some of whose decisions are printed in one volume and some only elsewhere are held.

Ordinals counted by these rules are initial ordinals, frozen at minting like any other (section 13.2). If a court's docket later shows that the second printed decision was entered first, the keys don't change; the docket order is metadata. A key from rule 2 or 3 can name a docket that doesn't identify the case (`us/nyappdiv/1/1996-09-27~14`); it is unique, and anyone holding the volumes computes it.

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

A key depends on three registries: a court registry and a reporter registry, which this repository publishes, and a judge registry, which it doesn't.

### 10.1 Court registry

The court registry is `registry/courts.json` in codexpublicus/exemplar, validated by `schema/courts-registry.schema.json`. Each entry has a court code (section 4), its jurisdiction code (`jurisdiction`, section 3), the court's name, its docket profiles with the date each applies from (for example `scotus`: `scotus-numbered` from the start, `scotus-ot1971` from 1971-07-01), and the source of its code. A court whose decisions span a change of sovereign also lists its jurisdiction codes with the date each applies from (`jurisdictions`; `pa`: `england`, then `gb` from 1707-05-01 and `us` from 1776-07-04), and its `jurisdiction` is the last of them. An entry MAY list aliases, other services' ids for the court or for a part of it, written `{service}:{id}` (`courtlistener:txctapp5`), and a `replaced-by` code for a court that merged or split. Codes are never renamed, reused or deleted.

The registry is built by `registry/build_courts.py` from a copy of courts-db's `courts.json`, vendored at `registry/sources/courts-db/` and pinned by commit and SHA-256 in the registry's `source` block, which also records the license courts-db states for it. Every court in that snapshot is registered; the registry's `excluded` block lists the one id left out, which fails the `court` rule. Four courts courts-db lacks are registered under CourtListener's ids (`kyctapphigh`, `mspb`, `tennsuperct`, `tennworkcompcl`; source `courtlistener`). The jurisdiction codes, docket profiles and aliases are this registry's assignments, not courts-db's: a territory's own courts take its code; the courts in England take `england` before 1707-05-01 and `gb` from it, and the court in the Philippines `ph` (section 3); a state court in one of the thirteen colonies or Maine takes `england` before 1707-05-01 and `gb` from it until 1776-07-04, one in Hawaii `hawaii` before 1898-08-12, one in Texas `texas` before 1846-02-19 and one in Vermont `vermont` before 1791-03-04, unless courts-db dates the court's start on or after the day the United States took over (courts-db's start dates for colonial courts don't support anything finer: it starts `ctchansc` in 1721, and CAP has its decisions from 1700); `scotus-numbered` and then `scotus-ot1971` for the Supreme Court; `us-coa` for the twelve regional courts of appeals; `us-cafc` for the Federal Circuit from 1982-10-01, and none before (P2, D123); `us-district` for federal district and bankruptcy courts; `printed` for every other court.

`registry/cap-courts.json`, validated by `schema/cap-courts.schema.json`, gives the registry code for each court the Caselaw Access Project names, by CAP court id, with the date each code applies from where one CAP court is several registry courts over time (CAP's Kentucky Court of Appeals is `kyctapphigh` before 1976-01-01 and `kyctapp` from it). Each entry says how its code was found; the file is engine output for review, and the CAP courts it can't map are listed with the reason. An entry marked `review`, with a `review_reason`, has a code that a person must check before any key is minted with it (section 4). Table `2026.10.23` marked the 88 CAP courts (626 cases) it mapped to CourtListener's generic federal courts, `usdistct` and `uscirct`. *Ruled (#26), D154 (2026-10-28):* table `2026.10.28` maps 285 of the 294 CAP courts the earlier table left unmapped or marked, from the court line in the head matter of sampled case files (basis `head-matter`, each entry's note saying what was read and what a person should still confirm): 79 marked courts take a specific code, 6 keep the generic code without the mark because one CAP court id holds several federal districts within the same dates, 200 unmapped courts take a code, and 3 marked and 6 unmapped courts stay as they were. The court registry adds eight codes it mints (`massctyctsuff`, `mdctcomplbalt`, `mdoytermct`, `njdistct`, `colctyctelpaso`, `colctyctlake`, `calspectrib`, `washterrdistct`; source `exemplar`) and three of CourtListener's (`mdgenct`, `stp`, `coregsalina`). Removing a mark, or changing a marked entry's code, is a new version of the table. It is versioned and pinned with the court registry.

`registry/reporters.json`, validated by `schema/reporters.schema.json`, is the reporter registry, added in 0.6.0. It names reporters by their slug (section 5.6) and lists:

- `official`: by court code, the reporters official for its decisions, by date, each step with the statute, rule or court order that makes them official (section 5.9 rule 4). Each step applies from its date (`null`: from the court's first decision) until the next. Each entry is curation, court by court. Registry `2026.10.28` named none; registry `2026.11.02` names reporters for 51 courts. *Ruled, D158 (2026-11-02).* An entry admits a reporter on one of these grounds, and its `source` cites the statute, rule or session law:
  1. a statute, rule or court order that calls the reporter official, or directs by name that the court's decisions be published in it (Judiciary Law § 433-a's "New York Reports", G.L. c. 221, § 65's "Massachusetts Reports");
  2. a statute that provides for the reporter, which the court publishes, though no text calls it official. The United States Reports are this case (Act of Mar. 3, 1817, ch. 63, now 28 U.S.C. § 411), and so are the reports of the Court of Customs and Patent Appeals (Judicial Code § 192, 36 Stat. 1144; 28 U.S.C. § 833(c) (1948));
  3. a court's citation rule calling the series the official reports, without the designating statute: N.J. Ct. R. 2:6-2(a)(6) ("the official New Jersey reports"), Ga. Sup. Ct. R. 22(2) and Ga. Ct. App. R. 24(d), and the Louisiana Supreme Court's General Administrative Rules, Part G, § 8(A).

  A series that stopped with no successor ends with a step whose `reporters` is empty only where a primary source dates the end: the Commonwealth Court Reports from 1995-07-01, on 27 Pa.B. 1282 ("In June of 1995, the court ceased publication of the Commonwealth Court Reports"), and the Louisiana Reports from 1973-01-01, on the Louisiana Supreme Court's rule. Where only a secondary source dates the end (the Pennsylvania Superior Court Reports, which library guides end in 1997), the last step stays open. A decision whose date falls in an empty step, or before a court's first step, has no official reporter, and one that needs it is refused `printings-disagree`. New York's Miscellaneous Reports are official from 1892-07-01, the start of the miscellaneous reporter's term under L. 1892, ch. 598 (approved 1892-05-14, in effect from 1892-09-01), for the courts of record they report; the Superior Court of the City of New York and the Court of Common Pleas, which they reported until those courts ended in 1895, have no separate series from that date. A court whose reporter no primary source found so far designates has no entry, though secondary sources may call its reports official: in `2026.11.02`, among the courts CAP holds, Florida, Texas and Tennessee, the Court of Claims and the Court of International Trade, and the federal series only a commercial publisher printed (the Alaska Federal Reports, U.S. App. D.C., the nominative reports of the circuit courts).
- `editions`: reporters that are editions of one report (section 7.1 rule 1): P.R. Dec. and P.R.
- `supreme_court_volumes`: for the United States Reports, the Supreme Court Reporter, the Lawyers' Edition and its second series, the first and last date of decision each volume prints (section 4). Registry `2026.10.28` computes it from CAP's records, the decisions each U.S. volume CAP holds prints and the dates of the decisions CAP lists with a citation to each other volume, with stray dates set aside; it is engine output until a person checks it.

The reporter registry has its own CalVer version, and names the court registry version it pins (`courts_registry_version`); a release tag pins both. Adding or ending an `official` entry is a new reporter registry version, not a new spec version.

### 10.2 Judge registry

This repository publishes no judge registry. Judge slugs come from a registry the consumer supplies and identifies by URI and version (section 10.3), such as one computed and published from the consumer's own corpus.

Whatever its source, a judge registry used with this spec MUST meet these rules. Each entry has a slug, the judge's name, and the court codes the slug is registered for. A slug matches `author` (`^[a-z][a-z-]*$`; no digits, so a second Justice Harlan is `harlan-ii`). A slug identifies one judge within each court it is registered for; a registry MAY make slugs unique across all courts, and SHOULD give a judge who sat on several courts one slug for all of them. Slugs are never renamed, reused or deleted.

An entry MAY list printed forms: the strings in which a source prints the judge's name in a byline, misprints and OCR errors included, each with the source it was seen in. A producer maps a byline to a slug only through an entry's name or printed forms, for the key's court. The name the byline prints matches a name or printed form when the two are equal, character for character, after both are case-folded (Unicode full case folding, as Python's `str.casefold()` does it): `HOOD` matches the name `Hood`, and `McDERMOTT` matches `McDermott`. Case folding is the only normalization. A byline that matches no entry, or more than one, is `unregistered-author`. A printed form is a fact about a source's text that a person has checked; a registry needn't list a form that differs from the name, or from another form, only in letter case. A producer MUST NOT match a byline to a name by edit distance, OCR correction or any other approximation.

### 10.3 Pinning

Each registry is published as numbered, immutable snapshots, each identified by a URI and a version. Registries are append-only: a later snapshot adds entries and never removes one or changes its code, the jurisdiction code or the profile it already assigns for a date. It MAY assign a profile for a date range that had none, once a version of this spec defines that profile. A key computed under an earlier snapshot is therefore still computable under a later one.

A producer MUST record, alongside the keys it mints (for example in a release manifest), the URI and version of each registry snapshot it used. The registry version is not part of the key.

| Registry | URI | Version |
|---|---|---|
| Courts | `https://raw.githubusercontent.com/codexpublicus/exemplar/{tag}/registry/courts.json` | `2026.10.28` |
| CAP courts | `https://raw.githubusercontent.com/codexpublicus/exemplar/{tag}/registry/cap-courts.json` | `2026.10.28` |
| Reporters | `https://raw.githubusercontent.com/codexpublicus/exemplar/{tag}/registry/reporters.json` | `2026.11.02` |
| Judges | supplied by the consumer | the consumer's |

The court registry's URI is the raw file URL of `registry/courts.json` at the release tag of codexpublicus/exemplar the consumer pins, with `{tag}` replaced by that tag, and its version is the `version` field in the file, a CalVer date (`YYYY.MM.DD`). The raw URL returns the registry file itself, as tagged; a `github.com/.../blob/{tag}/...` URL returns an HTML page about the file, whose fragments GitHub uses for its own line anchors. A judge registry's URI is an absolute URI that names one snapshot, chosen by whoever publishes it. This version of the spec is published with court registry `2026.10.28`, which adds the eleven codes of section 10.1, and reporter registry `2026.11.02`, which adds the official-reporter table to 0.6.0's `2026.10.28`; registry `2026.10.25`, which assigns the Federal Circuit the `us-cafc` profile, is 0.5.x's, and `2026.10.23` is 0.4.0's. The test vectors resolve court codes against that registry and use a judges fixture (`vectors/court-record-key/judges-fixture.json`), which stands in for a consumer's judge registry and is not one.

## 11. Aliases and relations

### 11.1 Aliases

Every other identifier a decision or part carries is kept as an **alias** that resolves to its key. An alias is never a key and is never minted as one. A resolver MUST accept any registered alias and return the key or keys it resolves to. An alias MAY resolve to more than one key (a reporter page shared by several decisions; a GovInfo package covering every decision in a docket); a resolver MUST then return all of them and MUST NOT choose one.

Aliases are written `{scheme}:{value}`. A non-lead docket of a consolidated case is a key-shaped alias: a key reference (section 2.6) to the key the docket would have had. That key is never minted, and a resolver maps the reference to the lead docket's decision key.

| Scheme | Value | Example | Resolves to |
|---|---|---|---|
| `crk` | the key the docket would have had (key-shaped alias) | `crk:us/scotus/17-1623/2020-06-15` | the lead docket's decision key |
| `cite` | reporter citation, as `{volume}-{slug}-{page}` (volume and slug as in 5.6) | `cite:834-f3d-1142` | a decision key |
| `neutral` | state or territorial neutral citation, as a slug (5.6 rule applied to the whole citation) | `neutral:2017-wi-1` | a decision key |
| `scotus-r` | Supreme Court Reporter's R-number, as `{term year}-{n}` | `scotus-r:2023-54` | a decision key |
| `ca6` | Sixth Circuit file number, lowercased | `ca6:26a0272p.06` | a decision key |
| `cmecf` | CM/ECF document id, as `{court}:{id}` | `cmecf:ca10:010110380264` | a decision key |
| `govinfo` | GovInfo package or granule id, verbatim | `govinfo:USCOURTS-ca10-14-09585` | the decision keys in that docket |
| `cap` | CAP static file `{reporter}/{volume}/cases/{file}.json`, as `{reporter}/{volume}/{file}` | `cap:us/410/0113-01` | a decision key |
| `cl-cluster` | CourtListener cluster id | `cl-cluster:{id}` | a decision key |
| `cl-opinion` | CourtListener opinion id | `cl-opinion:{id}` | a part key |
| `crk-printed` | the decision key computed from the printed record alone (section 6.3) | `crk-printed:us/dakotasup/rpt.3-dakota-1/1882-05-00` | the decision's current key |

```abnf
alias          = crk-ref / cite-alias / neutral-alias / scotus-r-alias / ca6-alias
               / cmecf-alias / govinfo-alias / cap-alias / cl-alias / printed-alias
cite-alias     = %s"cite:" 1*DIGIT "-" slug "-" 1*DIGIT
neutral-alias  = %s"neutral:" slug
scotus-r-alias = %s"scotus-r:" 4DIGIT "-" 1*DIGIT
ca6-alias      = %s"ca6:" 2DIGIT %s"a" 4DIGIT ( %s"p" / %s"n" ) %s".06"
cmecf-alias    = %s"cmecf:" court ":" 1*DIGIT
govinfo-alias  = %s"govinfo:" 1*( %x41-5A / LC / DIGIT / "-" / "_" )
cap-alias      = %s"cap:" slug "/" 1*DIGIT "/" 1*DIGIT "-" 2DIGIT
cl-alias       = ( %s"cl-cluster:" / %s"cl-opinion:" ) %x31-39 *DIGIT
printed-alias  = %s"crk-printed:" jurisdiction "/" court "/" docket "/" decided [ ord ]
```

Further schemes are added by a minor version.

### 11.2 Relations

- `replaces` / `replaced-by`: between a new decision and the decision it vacates and replaces, whose keys each keep resolving to their own decision (section 9); and, in a publisher's ledger, from a superseded key to the key that supersedes it for the same decision (a fallback or zeroed-date key and the key minted when the docket or the date is established, a provisional key and its settled one), which makes the superseded key a redirect (section 13.1). A key corrected as an outright error is recorded in the errata list (section 13.4).

## 12. Computing a key (producer refusals)

A producer computes a key from: the court code, and the jurisdiction code the registry gives it for the decision date; the docket as printed (or none) and, for the fallback, a reporter citation; the decision date; the decision ordinal; and, for a part, the role, the author slugs and the part ordinal; and, for a version, the revision date. It MUST refuse rather than guess, and SHOULD report one of these classes:

| Class | When |
|---|---|
| `unregistered-court` | The court code is not in the court registry, or a source's court id is not one the registry or the CAP court table translates (section 4) |
| `court-under-review` | The CAP court table marks the decision's CAP court for review (sections 4, 10.1) |
| `court-conflict` | The decision's official citation is in a reporter only the Supreme Court's decisions take, the source names another court, and the citation's volume doesn't span the decision's date (section 4; under 0.5.x, whatever the volume) |
| `no-docket-profile` | The registry gives the court no docket profile for the decision date; checked before the docket, and the fallback doesn't apply (5.6) |
| `docket-profile` | The docket doesn't fit the profile, and there is no citation for the fallback |
| `no-docket` | The decision has no docket, and no citation for the fallback |
| `citation` | The fallback is needed and the decision's official citation isn't a volume, a reporter and a page (section 5.6; from 0.6.0) |
| `no-decision-date` | Not even the decision's year is known |
| `date` | The decision date gives no year, or a month outside `01` to `12` (section 6.2; under 0.5.x, also a day that doesn't exist in its month) |
| `printings-disagree` | The decision's printings compute different candidates, and section 5.9 can't give one: their link rests on no second source, they give different courts or dates neither of which can be the other, or the official reporter that rule 2 or 3 needs isn't in the reporter registry or prints none of them (from 0.6.0) |
| `shared-candidate` | Printings or decisions compute one candidate, and no rule of section 7.1 says whether they are one decision or how to count them; a person rules (from 0.6.0) |
| `unregistered-author` | An author is not in the judge registry for the court |
| `per-curiam-author` | A `per-curiam` part was given authors |
| `role` | The role is not in the vocabulary |
| `ordinal` | An ordinal is less than 1 |
| `revised` | The revision date is not a calendar date or is earlier than the decision date |

An ordinal of 1 means the first instance and produces no mark. Every key a producer emits MUST be a valid key (section 2.3).

What this section computes is a candidate key. A publisher mints it through its minted-key ledger, which confirms it or advances its decision ordinal (section 13.2).

## 13. Persistence and versioning

### 13.1 The address guarantee

A minted key always resolves to the decision it was minted for. A publisher MUST NOT change the decision a key resolves to, delete a key, or reuse a retired key for a different decision, except to correct an outright error (section 13.4).

A key is never edited, even if a later version of the decision reorders the caption or corrects the date. When the facts a key was computed from change for the same decision (a date established later, section 6.1; a docket recovered for a fallback key, section 5.6; a provisional key settled, section 13.3; a version of this spec that computes the key differently), the publisher mints the new key and records the old one `replaced-by` it. The old key is then a permanent redirect: a resolver given it returns the key it is replaced by, following each `replaced-by` in turn to the decision's current key. A new decision that vacates and replaces an earlier one (section 9) is not a redirect: each key keeps resolving to its own decision, and the two decisions are related by `replaces` and `replaced-by` (section 11.2).

### 13.2 The minted-key ledger

A publisher that mints keys keeps a **minted-key ledger**. For each decision key it has minted, the ledger records:

- the key;
- the decision it was minted for, by the publisher's own identifier for its record;
- its status: `active` (the decision's current key), `replaced` (superseded for the same decision, section 13.1) or `errata` (corrected by an errata entry, section 13.4);
- the key it is `replaced-by`, when its status is `replaced`, or `errata` with a replacement;
- whether it is provisional (section 13.3).

A key enters the ledger when it is minted and never leaves it, and a decision has at most one active key. Part keys and version keys are formed from the decision's key as minted (sections 8, 9) and need no entries of their own. This spec doesn't fix the ledger's format.

Sections 3 to 12 compute a **candidate** key. The ledger confirms or advances it, and only then is it minted:

1. If the ledger holds an active key for the decision with the candidate's **stem** (the decision key without its decision ordinal), that key is the decision's key, whatever ordinal the candidate has, and nothing is minted.
2. Otherwise, if no ledger entry holds the candidate, whatever its status, the candidate is minted as computed. If one does, the ordinal advances: the key minted is the candidate's stem with the lowest decision ordinal above the candidate's that no ledger entry holds.
3. The minted key is recorded `active`. If the decision had an active key, that key becomes `replaced`, `replaced-by` the new one.

Ordinals are therefore frozen at minting. The first decision minted under a stem keeps its ordinal, and a decision that arrives later (one the producer couldn't key before, or one a new source adds) takes the next free ordinal, even where the printed order or the docket would put it first. Before any key with a stem is minted, the ledger holds nothing under it and confirms every candidate, so the initial ordinals are those sections 5.6, 5.7, 6.2 and 7 compute. For example, decisions A and B, printed in that order on one page and dated May 1882, are minted `us/dakotasup/rpt.3-dakota-1/1882-05-00` and `~2`. A decision printed on the page before them that a later source adds computes the unmarked candidate; the ledger holds it, and holds `~2`, so the new decision is minted `~3`, and A and B keep their keys.

The ledger makes a minted key a fact about a publisher, not only about the decision: two publishers with different ledgers can mint different keys for one decision. The candidate key, and the printed-date alias (section 6.3), stay the same for both.

### 13.3 Provisional keys

Where trustworthy sources disagree about the decision date, or about another fact a key is computed from, a producer MAY mint the key all the same, marked **provisional** in the ledger. It SHOULD compute it from the value the decision's printing gives for the disputed fact (section 6.3).

A date the official report prints in full is overridden only by a source of the same standing. A second source that disagrees with it makes the key provisional only when that source is official (the court's own record or docket) or human-curated (a person's verified ruling on the date). CourtListener's dates, flagged approximate or not, engine output, and any other data that pads or estimates dates never make a printed full date provisional; a producer MAY record what they say as metadata on the decision. So `us/scotus/1/1895-11-18`, printed `Decided November 18, 1895.`, is not provisional when a CourtListener cluster gives 1895-11-19, and is when the Court's docket gives that date. Where the report prints only a year and month, or a year, a date that contradicts the printed year or month establishes nothing and doesn't make the key provisional (section 6.1). Trustworthy sources whose dates fit the printed year or month but disagree with each other make the key provisional: a CourtListener cluster dated 1882-05-12 and another printing of the decision dated 1882-05-19, for a report that prints only May 1882. The mark is metadata, never part of the key: a provisional key has the same form as any other and resolves like any other, and a resolver SHOULD report the mark with it.

When a person settles the disagreement, the producer recomputes the key from the settled facts. If that gives the same key, the mark is removed. Otherwise the settled key is minted (section 13.2), and the provisional key is `replaced-by` it.

### 13.4 Errata

The one exception to section 13.1 is the correction of an outright error: a key minted for the wrong decision, or computed from facts that were wrong (a misread docket, a wrong date, the wrong court), not merely less precise than facts established later. A publisher MAY retarget such a key to the decision it should have named, or retire it with a replacement. Every such correction MUST be recorded in the publisher's errata list, and none is ever made silently; the key's ledger status becomes `errata`.

A publisher that mints keys MUST publish an errata list, an empty one included, at a stable URL it records alongside its keys and the registry snapshots it used (section 10.3). The list is a JSON document, valid under `schema/crk-errata.schema.json`:

- `publisher`: an absolute URI naming the publisher.
- `entries`: the corrections, in the order they were made. Each has `seq`, its position in the list (1, 2, ... with no gaps); `date`, the date of the correction (`YYYY-MM-DD`); `key`, the key corrected; `error`, `wrong-decision` or `wrong-facts`; `reason`, what was wrong, in words; and exactly one of `replaced_by`, the key that replaces it, which the corrected key then redirects to, or `target`, an alias (section 11.1) of the decision the key resolves to from then on.

The list is append-only: each published version holds every entry of the one before, unchanged and in the same order, and adds new entries at the end. An illustrative list with one correction:

```json
{
  "publisher": "https://stare.pub/",
  "entries": [
    {
      "seq": 1,
      "date": "2026-11-02",
      "key": "us/mass/rpt.1-mass-1/1804-03-10",
      "error": "wrong-facts",
      "reason": "Decision date misread from the scan; the report prints March 1, 1804.",
      "replaced_by": "us/mass/rpt.1-mass-1/1804-03-01"
    }
  ]
}
```

### 13.5 Versions

**Spec versions.** This spec is versioned with [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html), because consumers pin it:

- **Major:** a change that makes the same facts compute a different key, or that makes a previously valid key invalid. Keys minted under an earlier major version stay valid and resolvable; a major version applies to keys minted after a producer adopts it.
- **Minor:** a change that only adds: a jurisdiction code, a role, a docket profile for a court or date range that had none, an alias scheme, an error class.
- **Patch:** editorial changes and new test vectors that don't change any expected result.

While the version is 0.x, a minor version MAY break these rules (SemVer item 4). Consumers pin a release tag of this repository and SHOULD record the spec version they implement.

**0.2.0.** This version changes two things from 0.1.0, under SemVer item 4: a key-shaped alias is written as a key reference, `crk:` followed by the key, and the bare key-shaped string is no longer an alias (sections 2.6 and 11.1); and the court registry's URI is an absolute URL that names the release tag (section 10.3). No key changes: the same facts compute the same key, and every valid key stays valid.

**0.6.1.** This patch release of 0.6.0 states what the reporter registry's official-reporter table admits, as the owner ruled in D158 (2026-11-02): a reporter a statute provides for and the court publishes, a series a court's citation rule calls the official reports, and an empty end step only where a primary source dates the end (section 10.1); and it states that printings linked only by an engine crosswalk stay held whatever the table names, as ruled in D151 (1) (2026-11-02) (section 5.9). No candidate key a 0.6.0 producer computes changes, and no vector's expected result changes; one vector that relied on the empty table, `54-no-official-reporter`, now names an empty table as its fixture. Reporter registry `2026.11.02`, published with it, names reporters for 51 courts. Of the 29,282 groups of printings that 0.6.0 held for want of the table, it keys 25,437 and leaves 3,845 held: 3,780 in courts it doesn't name, and 65 in courts it names, where the decision predates the court's first step, no printing is in the official reporter, or the official printings give different segments. The 47,867 groups linked only by a CourtListener cluster stay held. Measured over CAP's 6,920,598 printings with the oracle and a model of a first mint, as 0.6.0 was, 0.6.1 with registry `2026.11.02` keys 6,646,920 decisions, against 6,621,485; holds 54,656 for a person (51,712 `printings-disagree`, 2,944 `shared-candidate`), against 80,091; and refuses 398, against 398. `shared-candidate` rises by 2 because two groups the table resolves take a candidate another decision also computes (section 7.1).

**0.6.0.** This version changes seven things from 0.5.1, under SemVer item 4, as the owner ruled in D154 (2026-10-28) on the proposals of codexpublicus/exemplar#57: #26, #28, #29, #50, #55 and #56 as proposed, and #54 limited to printings a second source links. Five candidate keys a 0.5.1 producer computes for CAP's decisions change, all in their fallback ordinal (below); every other keeps its value, and what changes is which decisions have one. Measured over CAP's 6,920,598 printings with the oracle and a model of a first mint, 0.6.0 keys 6,621,485 decisions, against 6,563,151 under 0.5.1; holds 80,091 for a person (77,149 `printings-disagree`, 2,942 `shared-candidate`), against 153,207; and refuses 398, against 9,119:

- **#56** (sections 5.6, 6.2, 12): the docket is read before the citation, and a citation that isn't a volume, a reporter and a page is refused `citation` only when the fallback needs it; a day that doesn't exist in its month is zeroed. **Adds keys**: 920 decisions by their docket and 19 dates; 151 are refused `citation`. The class `date` narrows. **Changes keys**: a decision whose official citation isn't a reporter citation has no fallback citation, so section 5.6 no longer counts it for its neighbours' ordinal; 0.5.1 producers counted it on its volume's page. Five 0.5.1 keys move down one ordinal: the four decisions after `282 A.D.651` (CAP's typing of 282 A.D. 651) on that page, `us/nyappdiv/rpt.282-ad-651/1953-06-02~3` to `~6`, which become `~2` to `~5`, and `us/nysupct/rpt.1-cai-37/1803-05-00~2`, which becomes unmarked, since `1 Cai. 22a`, which CAP prints on its page 37, isn't on the official page 37 at all;
- **#50** (sections 4, 10.1, 12): a decision cited to the Supreme Court's reporters that a source files under another court keys under `scotus`, unless the citation's volume can't be the decision's. **Adds keys**: 1,256 of the 1,268 decisions 0.5.x refused `court-conflict`;
- **#26** (section 10.1; registry `2026.10.28`): the CAP court table maps 285 more CAP courts, and the court registry adds eleven codes. **Adds keys**: 6,533 printings get a court, and 6,531 of them a key;
- **#54** (section 5.9): a decision printed more than once takes one candidate from its printings, when a second source links them. Of the 81,429 groups of printings whose candidates differ, 47,867 rest on a CourtListener cluster alone and stay held; 4,280 key; 29,282 need the official reporter, which the registry doesn't name yet (28,435 of them would key with one). **Adds keys**;
- **#55, #29, #28** (section 7.1): printings in two volumes with one docket key, a full date and one case name, or in two editions of one report, are one decision; decisions that compute one candidate are counted in printed order when one volume prints them all, or when they are in volumes of one reporter and their names differ. **Adds keys**, and joins printings to the decisions they reprint: CAP's printings are 6,701,974 decisions, against 6,725,477.

No vector's expected key changes. Five vectors that expected a refusal expect a key: `not-a-date` (`us/ca10/14-9585/2016-02-00`), `court-conflict-cafc-sct`, `court-conflict-us-reports`, and `cap-court-under-review` and `cap-court-unmapped`, whose CAP courts the table now maps, renamed `cap-court-reviewed-prd` and `cap-court-mapped-ard`; new `cap-court-under-review` and `cap-court-unmapped` vectors use CAP courts the table still leaves. Nothing has been minted, so no key needs a `replaced-by` or an errata entry: in a first mint under 0.6.0, 4 decisions 0.5.1 would key take `~2` instead, because a decision 0.6.0 newly keys has the same candidate and is printed before it (all `Appeal No. 1` and `No. 2` dockets of the Appellate Division), and 21 are held, because a printing 0.6.0 newly keys either computes the same candidate with nothing to link the two (`shared-candidate`) or is linked to them by a CourtListener cluster alone and computes another candidate (`printings-disagree`).

**0.5.1.** This patch release of 0.5.0 states how a second source's date that contradicts a partial printed date is treated, as the owner ruled in D136 (2026-10-26): it establishes nothing, and it doesn't make the key provisional (sections 6.1, 13.3). The 0.5.0 text of section 13.3 could be read to make such a key provisional. No key changes, since the provisional mark isn't part of a key; under the 0.5.0 reading, CourtListener alone would have marked about 8,600 CAP decisions provisional that 0.5.1 doesn't. No vector's expected result changes.

**0.5.0.** This version changes six things from 0.4.0, under SemVer item 4. It takes up the three largest refusal classes CAP's decisions met under 0.4.0, as the owner ruled in D118 (2026-10-25): reporter-fallback decisions whose official citation isn't the page they are printed on (codexpublicus/exemplar#32), the Federal Circuit, which had no profile, and reporter slugs with `&` (codexpublicus/exemplar#30). The owner ruled the proposals P1a to P4 in D123 (2026-10-26): all as proposed, except that P2's docket segment takes a four-digit year. Under all of them, the reference oracle keys 6,911,474 of CAP's 6,920,598 decisions (99.87%), against 6,834,385 under 0.4.0:

- **P1a** (section 5.6): the fallback ordinal counts the decisions in the volume whose fallback citation is the same, not those on the volume's page. **Changes keys**: 296 0.4.0 keys, all in their ordinal;
- **P1b** (section 5.6): when the official citation gives the volume number of the volume the decision was taken from but another reporter, the volume's reporter is used. **Adds keys**;
- **P1c** (sections 5.6, 16): a decision whose official citation is in another reporter's volume is counted among the decisions in its own volume. **Adds keys**;
- **P2** (sections 5.8, 10.1): the Federal Circuit has the profile `us-cafc` from 1982-10-01, with four-digit years: `No. 87-1054` is `1987-1054`, and `No. 2004-1582` is kept as printed. **Adds keys** for decisions 0.4.0 refused `no-docket-profile`;
- **P3a, P3b** (section 5.6): a reporter slug deletes `&`, and a volume numbered with a fraction is written `81-1-2`. **Adds keys** for decisions whose fallback key was invalid; no valid key changes;
- **P4** (sections 4, 12): a decision whose official citation is in a reporter only the Supreme Court's decisions take, and that a source files under another court, is refused with the new class `court-conflict`. **Withdraws** 1,151 0.4.0 keys, nearly all of Supreme Court decisions keyed under another court; a few rest on a mistyped citation (CAP cites `951 S.Ct. 564` for a Third Circuit decision of 1991).

Registry `2026.10.25` assigns `us-cafc` to `cafc` from 1982-10-01, a profile for a date range that had none (section 10.3).

**0.4.0.** This version changes five things from 0.3.1, under SemVer item 4. The jurisdiction codes are the owner's rulings D101 (2026-10-23) and D104 (2026-10-24) on codexpublicus/exemplar#25, #38, #39, #42 and #43; the court registry's additions and the CAP court table D105 (2026-10-24) on codexpublicus/exemplar#26 and #27; and the key model, dates included, D102 (2026-10-25) on codexpublicus/exemplar#33 and #37, with the `scotus-numbered` profile for the pre-1971 Supreme Court gap of #46 (D103) following it:

- the first segment is a jurisdiction code (section 3): ISO 3166-1 codes, a territory's own code, registered body codes such as `ccj`, and the issuing sovereign for a court whose sovereign changed. The grammar admits any two to sixteen lowercase letters, and a validity rule admits the codes section 3 lists. **Changes keys**: a decision of a territory's own court moves from `us` to the territory's code (`us/prsupreme/...` is `pr/prsupreme/...`), a colonial court's decision from `us` to `england` before 1707-05-01 and to `gb` from then until 1776-07-04, and decisions of Hawaii's courts before 1898-08-12, Texas's before 1846-02-19 and Vermont's before 1791-03-04 to `hawaii`, `texas` and `vermont`;
- `decided` is the best date a producer can establish from trustworthy sources at minting (section 6.1), with the day, or the month and the day, zeroed where it can't establish them: `1882-05-00`, `1793-00-00` (section 6.2). A decision with a zeroed date has a key like any other, and its initial ordinal is counted in printed order. The refusal class `incomplete-date` is withdrawn. **Adds keys** for decisions 0.3.1 refused;
- the key model (section 13): a minted key always resolves to its decision and, when superseded, becomes a permanent `replaced-by` redirect; sections 3 to 12 compute a candidate that a publisher's minted-key ledger confirms or advances, so ordinals are frozen at minting and a decision keyed later takes the next free ordinal; a key MAY be minted provisional where trustworthy sources disagree, and a date the official report prints in full only where an official or human-curated source does (D113, 2026-10-25); an outright error is corrected only through the publisher's published errata list; and each decision has a printed-date alias, `crk-printed:`, that anyone holding the volume can compute (section 6.3). **Changes keys**: a key a publisher has minted no longer follows a later change in its neighbours' facts;
- the Supreme Court has the `scotus-numbered` profile before 1971-07-01 (section 5.7), with the initial decision ordinal in printed order, frozen at minting like any other, and its decisions of that period take the reporter fallback like any other court's. **Adds keys** for decisions 0.3.1 refused `no-docket-profile`;
- the court registry registers the courts courts-db lists outside the United States, each under the code of the country it sits in, four courts courts-db lacks under CourtListener's ids, and CourtListener's ids for the districts of the Court of Appeals of Texas and for the Supreme Court of the Northern Mariana Islands as aliases; `registry/cap-courts.json` gives the code for each court CAP names (section 10.1). **Adds keys** for decisions 0.3.1 refused `unregistered-court`, or that a producer refused for want of a mapping. The table's entries that map a CAP court to CourtListener's generic federal courts are marked for review, and the new refusal class `court-under-review` refuses their decisions until a person checks them (sections 4, 10.1, 12).

The key's first segment is named the jurisdiction segment, the word stare.pub's citation addresses use, as the owner ruled in D104(f) (2026-10-24): the ABNF rule is `jurisdiction`, the error class `jurisdiction` (0.3.1's `country`), a parsed key's part `jurisdiction`, and the court registry's fields `jurisdiction` and `jurisdictions`. No key changes for it.

Registry `2026.10.23` changes the jurisdiction code of thirteen territorial courts, and assigns date-ranged codes to 976 courts, which section 10.3's append-only rule forbids outside a 0.x minor version. A producer that minted a key under 0.3.x that these rules compute differently records the 0.3.x key `replaced-by` the 0.4.0 key (section 11.2). Every key valid under 0.3.1 stays valid.

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
| `decisions.jsonl` | printings and the links between them to decisions, each with its key or refusal class (sections 5.9, 7.1) |
| `docket.jsonl` | printed docket to docket segment, per profile |
| `byline.jsonl` | the name a byline prints to a judge slug, through the judge registry's names and printed forms |
| `alias.jsonl` | printed identifier to alias string, and alias to key |
| `ledger.jsonl` | a candidate key and a minted-key ledger to the key minted, and a key to the current key it resolves to (sections 13.1 to 13.4) |
| `errata.jsonl` | errata lists to valid or invalid, against `schema/crk-errata.schema.json` and the append-only rule (section 13.4) |

Every vector records its `provenance`:

- `human-curated`: a person checked it against the primary source. Ground truth; where it disagrees with any other vector, it wins.
- `hand-checked`: taken from a worked example in the research doc.
- `engine-output`: taken from an implementation's tests or output (gorsuch-library), or computed from a source's records (CAP's case metadata, CourtListener's export) by the rules here; it shows what the data and an implementation give, not what is correct.
- `spec-derived`: constructed from this document's rules to exercise an edge case, and not yet checked by a person.

## 15. Interop mappings (informative)

These are derived from a key, never canonical. For `us/ca10/14-9585/2016-08-23`:

- Akoma Ntoso work IRI: `/akn/us/judgment/ca10/2016-08-23/14-9585`, expression `…/eng@2016-08-23`. A part maps to an inline `<opinion>` with `eId` `opinion_concurrence.gorsuch`. The IRI's first segment is the key's jurisdiction segment: `pr/prsupreme/8561/1943-05-18` is `/akn/pr/judgment/prsupreme/1943-05-18/8561`.
- URN:LEX ([RFC 9676](https://www.rfc-editor.org/rfc/rfc9676.html)): `urn:lex:us:court.appeals.10.circuit:decision:2016-08-23;14-9585`. The US jurisdiction table is empty, so the authority name is not standardized.
- ECLI-shaped string: `ECLI:US:CA10:20160823:14.9585`. This is not a real ECLI; the US has no ECLI coordinator.

## 16. Open issues

Non-normative. Each is a gap this version leaves for a later one.

- The Eleventh Circuit's letter suffix is dropped, but its meaning is unverified.
- `registry/cap-courts.json` is engine output: its 3,448 mappings need review, 3 of them before any key is minted on them, and 6 CAP courts have no code (among them CAP 16930, four courts of military review under one id). About 20 printings key under the wrong court because no date separates them from the rest of their CAP court, and entries that already key file some New Jersey district-court and Ohio printings under the wrong court (codexpublicus/exemplar#26); a per-case corrections list would fix both, and none exists yet.
- The reporter registry's `official` table names no reporter for courts whose designation no primary source found so far shows (section 10.1): Florida, Texas, Tennessee, the Court of Claims, the Court of International Trade, the federal series only a commercial publisher printed, and others with a few groups each (in CAP, 3,780 groups of printings wait on them, 1,713 of them the Court of International Trade's). New York's reporters before 1892, the Superior Court's and the Court of Common Pleas' own reports among them, need a person who knows them. The end of the Pennsylvania Superior Court Reports has no primary source, so their step stays open. Its `supreme_court_volumes` table is engine output from CAP's records, and lacks the first series of the Lawyers' Edition from volume 92, which CAP's citations label as the second series.
- Section 5.9's second source counts a parallel citation under any of a reporter's abbreviations; this spec doesn't publish the table of abbreviations, and whether a source's parallel citations were themselves taken from an engine crosswalk is the source's to say.
- A decision taken from a volume of another reporter than its official citation's is counted for its fallback ordinal among the decisions in that volume only (section 5.6); counting across every volume a source holds would need an index of official citations, which a producer reading one volume doesn't have.
- The `us-cafc` profile takes no range (`Nos. 85-504 to 85-507`), slash form (`No. 86-954/1017`) or docket followed by another office's number (`97-1371 (Opposition Nos. ...)`); those decisions take the fallback. CourtListener's docket field writes lists without a label (`87-1038, 87-1064`) and `Appeal 82-19` without `No.`, which section 5.1 doesn't clean for any court.
- Sources misfile decisions under the wrong court; section 4 keys the Supreme Court's under `scotus` by their citation (codexpublicus/exemplar#50), and no rule here catches the rest. A citation whose volume can't be the decision's stays refused until a person corrects the source.
- The `us-district` profile is assigned to historical district courts, whose dockets predate the PACER form and so fall to `rpt.`; they may want a profile of their own.
- Codes for tribal nations (codexpublicus/exemplar#45), and the courts that sit for several states and would take a body code, such as the Caribbean Court of Justice or the Privy Council in its modern jurisdiction (codexpublicus/exemplar#25).
- The colonies' change of sovereign is dated 1776-07-04 for all thirteen, although some broke with the Crown earlier and New York's courts sat under it until 1783.
- The minted-key ledger's format is the publisher's (section 13.2); a later version may fix one, so that ledgers can be compared or mirrored.
- Section 7.1 rule 3 keys decisions that share a per-term docket number (`Appeal No. 1`, `Appeal, No. 1`, `Docket No. 11`) in printed order, and the key doesn't identify the case. A profile that rejects such dockets, so that they take the `rpt.` fallback, would change about 76,000 candidate keys; codexpublicus/exemplar#28 keeps it as the alternative.
