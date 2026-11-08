# SPDX-FileCopyrightText: Copyright (c) 2026 Codex Publicus contributors
# SPDX-License-Identifier: BSD-3-Clause

"""A minimal reading of spec/court-record-key.md, used only to check the vectors.

It is written from the spec's prose, not from any producer, so a vector that
disagrees with it points at either the vector or the spec. Nothing here is a
library; vectors MUST NOT be generated from it.
"""

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

ROLES = frozenset(
    {
        "opinion",
        "per-curiam",
        "plurality",
        "concurrence",
        "concurrence-in-judgment",
        "concurrence-in-part-and-judgment",
        "partial",
        "partial-majority",
        "dissent",
        "statement",
        "order",
        "judgment",
        "decree",
    }
)

# Section 3: the jurisdiction codes this version defines.
JURISDICTIONS = frozenset(
    {"us", "pr", "gu", "vi", "as", "mp", "gb", "ph", "ccj", "england", "hawaii", "texas", "vermont"}
)
JURISDICTION = re.compile(r"[a-z]{2,16}")
COURT = re.compile(r"[a-z][a-z0-9-]*")
DOCKET = re.compile(r"[a-z0-9][a-z0-9_.-]*")
RPT = re.compile(r"rpt\.[0-9]+-[a-z0-9][a-z0-9-]*-[0-9]+")
AUTHOR = re.compile(r"[a-z][a-z-]*")
ORD = re.compile(r"[2-9]|[1-9][0-9]+")
DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
# A date as a source states it (facts): ISO 8601, a calendar date or reduced to a year and month
# or a year.
ISO_DECIDED = re.compile(r"[0-9]{4}(-[0-9]{2}(-[0-9]{2})?)?")


class Refusal(Exception):
    """A producer refusal; args[0] is the class from spec section 12."""


def is_date(text: str) -> bool:
    if not DATE.fullmatch(text):
        return False
    try:
        date(int(text[:4]), int(text[5:7]), int(text[8:]))
    except ValueError:
        return False
    return True


def is_decided(text: str) -> bool:
    """Sections 2.3, 6.2: a calendar date, or a zeroed date (YYYY-MM-00, YYYY-00-00)."""
    if not DATE.fullmatch(text):
        return False
    year, month, day = text[:4], text[5:7], text[8:]
    if day != "00":
        return is_date(text)
    return year != "0000" and (month == "00" or 1 <= int(month) <= 12)


def zeroed(fact: str) -> str | None:
    """Section 6.2: the decided segment for a date a source states in ISO 8601 form (a calendar
    date, a year and month, or a year), or None when it gives no year or a month outside 01 to 12.

    From 0.6.0 (#56), a day that doesn't exist in its month (`1911-02-29`, `2016-02-30`)
    establishes the year and month only, and is zeroed.
    """
    if not ISO_DECIDED.fullmatch(fact):
        return None
    segment = {4: fact + "-00-00", 7: fact + "-00"}.get(len(fact), fact)
    if len(fact) == 10 and not is_decided(segment):
        segment = fact[:7] + "-00"
    return segment if is_decided(segment) else None


def period(text: str) -> tuple[str, str]:
    """The first and last calendar day of a zeroed date's or a reduced ISO 8601 date's period."""
    text = {4: text + "-00-00", 7: text + "-00"}.get(len(text), text)
    if text.endswith("-00-00"):
        return text[:4] + "-01-01", text[:4] + "-12-31"
    if text.endswith("-00"):
        year, month = int(text[:4]), int(text[5:7])
        following = date(year + month // 12, month % 12 + 1, 1)
        return text[:7] + "-01", date.fromordinal(following.toordinal() - 1).isoformat()
    return text, text


def period_start(decided: str) -> str:
    """Section 6.2: the calendar date a decided segment stands for, the first day of its period."""
    if decided.endswith("-00-00"):
        return decided[:4] + "-01-01"
    if decided.endswith("-00"):
        return decided[:7] + "-01"
    return decided


def classify(key: str) -> str | None:
    """The error class of spec section 2.5, or None for a valid key."""
    if key.count("@") > 1:
        return "structure"
    body, at, revised = key.partition("@")
    segments = body.split("/")
    if len(segments) not in (4, 5):
        return "structure"
    jurisdiction, court, docket, decided = segments[:4]
    if not JURISDICTION.fullmatch(jurisdiction) or jurisdiction not in JURISDICTIONS:
        return "jurisdiction"
    if not COURT.fullmatch(court):
        return "court"
    if not DOCKET.fullmatch(docket) or (docket.startswith("rpt.") and not RPT.fullmatch(docket)):
        return "docket"
    day, tilde, ordinal = decided.partition("~")
    if not is_decided(day):
        return "date"
    if tilde and not ORD.fullmatch(ordinal):
        return "ordinal"
    if len(segments) == 5:
        head, tilde, ordinal = segments[4].partition("~")
        role, dot, authors = head.partition(".")
        if role not in ROLES:
            return "role"
        if dot and not all(AUTHOR.fullmatch(a) for a in authors.split("+")):
            return "author"
        if dot and role == "per-curiam":
            return "author"
        if tilde and not ORD.fullmatch(ordinal):
            return "ordinal"
    if at and (not is_date(revised) or revised < period_start(day)):
        return "revised"
    return None


def parse(key: str) -> dict[str, Any]:
    """Split a valid key into the parts recorded in parse.jsonl."""
    assert classify(key) is None, key
    body, _, revised = key.partition("@")
    segments = body.split("/")
    jurisdiction, court, docket, decided = segments[:4]
    day, _, ordinal = decided.partition("~")
    parts: dict[str, Any] = {
        "jurisdiction": jurisdiction,
        "court": court,
        "docket": docket,
        "decided": day,
        "decision_ordinal": int(ordinal) if ordinal else 1,
        "role": None,
        "authors": [],
        "part_ordinal": None,
        "revised": revised or None,
        "fallback": docket.startswith("rpt."),
    }
    if len(segments) == 5:
        head, _, part_ordinal = segments[4].partition("~")
        role, _, authors = head.partition(".")
        parts["role"] = role
        parts["authors"] = authors.split("+") if authors else []
        parts["part_ordinal"] = int(part_ordinal) if part_ordinal else 1
    return parts


def decision_key(parts: dict[str, Any]) -> str:
    key = f"{parts['jurisdiction']}/{parts['court']}/{parts['docket']}/{parts['decided']}"
    if parts["decision_ordinal"] > 1:
        key += f"~{parts['decision_ordinal']}"
    return key


def format_key(parts: dict[str, Any]) -> str:
    key = decision_key(parts)
    if parts["role"] is not None:
        key += f"/{parts['role']}"
        if parts["authors"]:
            key += "." + "+".join(parts["authors"])
        if parts["part_ordinal"] > 1:
            key += f"~{parts['part_ordinal']}"
    if parts["revised"]:
        key += f"@{parts['revised']}"
    return key


# Docket profiles (spec section 5).

_LABEL = re.compile(
    r"(?:(?:docket|case|appeals|appeal|record|file|gen\.|general),?\s*)?"
    r"(numbers|number|nos|no)\b\.?\s*[,:]?\s*",
    re.IGNORECASE,
)
_DASHES = str.maketrans(dict.fromkeys("‐‑‒–—−", "-"))
_THOUSANDS = re.compile(r"(?<=[0-9]),(?=[0-9]{3}(?:[^0-9]|$))")


def _unlabel(text: str) -> tuple[str, bool]:
    """Step 2: the text without a leading label, and whether the label was plural."""
    m = _LABEL.match(text)
    if not m:
        return text, False
    return text[m.end() :], m.group(1).lower() in ("nos", "numbers")


def _strip_period(text: str) -> str:
    return text[:-1] if text.endswith(".") and not text.endswith("Orig.") else text


def clean_all(printed: str) -> list[str]:
    """Spec section 5.1: the cleaned docket first, then every other docket the list names.

    An empty list means the decision has no docket.
    """
    text, plural = _unlabel(printed.strip().translate(_DASHES))
    text = _THOUSANDS.sub("", text)
    items = [text]
    if plural or ";" in text:
        separators = r";|,|&|\band\b" if plural else r";"
        items = [i.strip() for i in re.split(separators, text) if i.strip()]
        items = [_unlabel(i)[0].strip() for i in items]
        if (
            len(items) > 1
            and re.fullmatch(r"[0-9]+", items[0])
            and (tail := re.fullmatch(r"[0-9]+(\s+.+)", items[-1]))
        ):
            items[0] += tail.group(1)
    items = [_strip_period(i) for i in items]
    if not items or not items[0] or not re.search(r"[0-9]", items[0]):
        return []
    return items


def clean(printed: str) -> str:
    """The cleaned docket, or "" when the decision has no docket."""
    return (clean_all(printed) or [""])[0]


def _scotus(text: str, court: str = "") -> str | None:
    if m := re.fullmatch(r"([0-9]{1,3}),? orig\.?", text, re.IGNORECASE):
        return f"22o{m.group(1)}"
    for pattern in (
        r"[0-9]{2}-[0-9]{1,5}",
        r"[0-9]{2}a[0-9]{1,5}",
        r"[0-9]{2}m[0-9]{1,5}",
        r"22o[0-9]{1,3}",
    ):
        if re.fullmatch(pattern, text, re.IGNORECASE):
            return text.lower()
    return None


def _scotus_numbered(text: str, court: str = "") -> str | None:
    if m := re.fullmatch(r"([0-9]{1,5})", text):
        return m.group(1)
    if m := re.fullmatch(r"([0-9]{1,5}),? misc\.?", text, re.IGNORECASE):
        return f"{m.group(1)}-misc"
    if m := re.fullmatch(r"([0-9]{1,3})[,.]? orig(?:inal)?\.?", text, re.IGNORECASE):
        return f"{m.group(1)}-orig"
    return None


def _coa(text: str, court: str = "") -> str | None:
    text = re.sub(r"\s*\(L\)$", "", text)
    text = re.sub(r"(?<=[0-9])-[A-Za-z]$", "", text)
    return text if re.fullmatch(r"[0-9]{2}-[0-9]{3,5}", text) else None


def _cafc(text: str, court: str = "") -> str | None:
    """Section 5.8: the Federal Circuit from 1982-10-01, with four-digit years."""
    if re.fullmatch(r"(?:19|20)[0-9]{2}-[0-9]{3,5}", text):
        return text
    if m := re.fullmatch(r"([0-9]{2})-([0-9]{3,5})", text):
        century = "19" if int(m.group(1)) >= 82 else "20"
        return f"{century}{m.group(1)}-{m.group(2)}"
    if m := re.fullmatch(
        r"(?:misc(?:ellaneous)?\.?\s*(?:nos?\.?\s*)?|(?:(?:19|20)?[0-9]{2}-)?m)([0-9]{1,4})"
        r"(?:\s*(?:,|&|\band\b)\s*[0-9]{1,4})*",
        text,
        re.IGNORECASE,
    ):
        return f"{m.group(1)}-misc"
    if re.fullmatch(r"[0-9]{1,3}-(?:[0-9]{2}[a-z]?|[a-z])", text, re.IGNORECASE):
        return text.lower()
    return None


def _district(text: str, court: str = "") -> str | None:
    m = re.fullmatch(
        r"([0-9]):([0-9]{2})-([a-z]{1,4})-([0-9]{1,5})(?:-[a-z]{2,4})*", text, re.IGNORECASE
    )
    return f"{m.group(1)}_{m.group(2)}-{m.group(3).lower()}-{m.group(4)}" if m else None


# Section 5.5 (from 0.7.0, #35, D192): the courts that print a lower court's docket number in
# parentheses after their own.
LOWER_COURT_NUMBER = frozenset({"ala", "alacrimapp", "alacivapp", "nm", "nmctapp", "ri"})
_TRAILING_GROUP = re.compile(r"\s*\([^()]*\)\s*$")


def _printed(text: str, court: str = "") -> str | None:
    if court in LOWER_COURT_NUMBER:
        # From 0.7.0 (#35): drop the lower court's number, then one trailing `.` (5.1 step 5).
        text = _strip_period(_TRAILING_GROUP.sub("", text))
    else:
        # From 0.7.0 (#35): delete parentheses, keeping what they enclose.
        text = text.replace("(", "").replace(")", "")
    text = re.sub(r"(?<=[0-9]),(?=\s*[0-9])", "_", text.lower()).replace(",", "")
    text = re.sub(r"\s+", "", text).replace(":", "_").replace("/", "_")
    return text if DOCKET.fullmatch(text) and not text.startswith("rpt.") else None


PROFILES = {
    "scotus-numbered": _scotus_numbered,
    "scotus-ot1971": _scotus,
    "us-coa": _coa,
    "us-cafc": _cafc,
    "us-district": _district,
    "printed": _printed,
}


def _dated(steps: list[dict[str, Any]], field: str, decided: str | None) -> Any:
    """The value of the last step that starts on or before decided (sections 5, 10.1).

    A zeroed date picks a step only when its whole period is on or after the step's start.
    """
    chosen = None
    for step in steps:
        if step["from"] is None or decided is None or step["from"] <= period_start(decided):
            chosen = step[field]
    return chosen


def profile_for(court: dict[str, Any], decided: str | None) -> str | None:
    return _dated(court["profiles"], "profile", decided)


def jurisdiction_for(court: dict[str, Any], decided: str | None) -> str:
    """Section 3: the issuing sovereign's code for the decision date."""
    if "jurisdictions" in court:
        return _dated(court["jurisdictions"], "jurisdiction", decided)
    return court["jurisdiction"]


# Section 5.3 (from 0.7.0, #36, D192): the Second Circuit's docket number after a calendar number,
# `No. 1217, Docket 79-5006`, `Nos. 1149, 1291, Dockets 89-7039, 89-7041`; and (D195) its docket
# number with a case-type suffix, printed from 2002, `05-5250-cv`, `03-7868 CV`, `03-4725-AG NAC`,
# or a marker, `03-1396(L), 03-1397(CON)`, `93-9263L`.
_CA2_NUMBER = r"[0-9]{2}-[0-9]{3,5}(?![0-9])"
# One group of a case-type suffix: up to five letters, directly or after `-` or a space, that
# aren't a word of a list or range.
_CA2_SUFFIX = r"(?:-|\s)?(?!(?:to|and|et|no|nos|thru)(?![a-z]))[a-z]{1,5}(?![a-z0-9])"
_CA2_MARKER = r"\s*\([a-z]{1,4}\)"
_CA2_END = r"(?=\s*(?:[,;&]|\band\b|\.?\s*$))"
_CA2_WORD = re.compile(r"\bdockets?\b\.?\s*(?:nos?\b\.?\s*)?", re.I)
# The number after `Docket`, with nothing after it that the suffix form reads (0.7.0, D192).
_CA2_PLAIN = re.compile(rf"({_CA2_NUMBER})(?![a-z-])(?!\s+(?!to\b)[a-z]{{2}}(?![a-z]))", re.I)
# The number with a case-type suffix of one or two groups, a marker, or both (D195).
_CA2_SUFFIXED = re.compile(
    rf"({_CA2_NUMBER})(?:(?:{_CA2_SUFFIX}){{1,2}}(?:{_CA2_MARKER})?|{_CA2_MARKER}){_CA2_END}", re.I
)
# Another docket: a later number of the form, alone or with a suffix or marker.
_CA2_OTHER = re.compile(
    rf"(?<![0-9a-z-])({_CA2_NUMBER})(?:{_CA2_SUFFIX}){{0,2}}(?:{_CA2_MARKER})?(?![0-9a-z-])", re.I
)


def _second_circuit(profile: str | None, court: str, printed: str) -> list[str]:
    """The us-coa dockets a Second Circuit docket names in the two-number form (D192) or with a
    case-type suffix or marker (D195), first the decision's docket, or [] when it is in neither."""
    if profile != "us-coa" or court != "ca2":
        return []
    text = printed.strip().translate(_DASHES)
    word = _CA2_WORD.search(text)
    start = word.end() if word else len(text) - len(_unlabel(text)[0])
    m = _CA2_SUFFIXED.match(text, start) or (word and _CA2_PLAIN.match(text, start))
    if not m:
        return []
    return [m.group(1)] + _CA2_OTHER.findall(text, m.end())


def docket_segment(
    courts: dict[str, Any], court: str, printed: str, decided: str | None = None
) -> str:
    """The docket segment, or Refusal(no-docket-profile / no-docket / docket-profile)."""
    profile = profile_for(courts[court], decided)
    if profile is None:
        raise Refusal("no-docket-profile")
    if found := _second_circuit(profile, court, printed):
        return found[0]
    text = clean(printed)
    if not text:
        raise Refusal("no-docket")
    segment = PROFILES[profile](text, court)
    if segment is None:
        raise Refusal("docket-profile")
    return segment


def other_dockets(
    courts: dict[str, Any], court: str, printed: str, decided: str | None = None
) -> list[str]:
    """Docket segments of the other dockets a printed list names (sections 5.1, 11.1)."""
    profile = profile_for(courts[court], decided)
    if found := _second_circuit(profile, court, printed):
        return found[1:]
    segments = (
        [PROFILES[profile](item, court) for item in clean_all(printed)[1:]] if profile else []
    )
    return [s for s in segments if s is not None]


def slug(text: str) -> str:
    """Section 5.6: an abbreviation reduced to a slug (`&` deleted from 0.5.0)."""
    text = re.sub(r"[.'’(),&]", "", text.lower())
    return re.sub(r"\s+", "-", text.strip())


# Section 5.6 (from 0.7.0, #31, D192): registry/reporter-variants.json, the reporter variant map.
VARIANTS: dict[str, Any] = json.loads(
    (Path(__file__).resolve().parent.parent / "registry" / "reporter-variants.json").read_text(
        encoding="utf-8"
    )
)["variants"]


def abbreviation(text: str) -> str:
    """Section 5.6 (from 0.7.0): the abbreviation the variant map gives a spelling, with
    whitespace runs collapsed; a spelling it doesn't list is its own abbreviation."""
    spelling = " ".join(text.split())
    entry = VARIANTS.get(spelling)
    return entry["abbreviation"] if entry else spelling


def reporter_slug(text: str) -> str:
    """Section 5.6: a reporter's slug, from the abbreviation the variant map gives (0.7.0)."""
    return slug(abbreviation(text))


def volume_text(volume: str) -> str:
    """Section 5.6 (from 0.5.0): a volume numbered with a fraction, `81 1/2`, is `81-1-2`."""
    return re.sub(r"[\s/]+", "-", volume.strip())


def rpt_segment(citation: dict[str, str]) -> str:
    volume, reporter = volume_text(citation["volume"]), reporter_slug(citation["reporter"])
    return f"rpt.{volume}-{reporter}-{citation['page']}"


_CITATION = re.compile(r"([0-9]+(?:\s+[0-9]+/[0-9]+)?)\s+(.+?)\s+(\*?[0-9]+)")
_VOLUME = re.compile(r"[0-9]+(?:\s+[0-9]+/[0-9]+)?")
_STAR_PAGE = re.compile(r"\*([0-9]+)")


def reporter_citation(citation: dict[str, str] | str | None) -> dict[str, str] | None:
    """Section 5.6 (from 0.6.0, #56): a reporter citation is a volume, a reporter and a page of
    decimal digits. facts give a citation as {volume, reporter, page} or as the source prints it;
    one in another form (`2011-NMCA-108`, `1 Cai. Cas. iii`, `3 Ark. App. 280-A`) gives None.
    From 0.6.3 (D187 (2)), a star page (`*49`) is read as the official reporter's page, 49."""
    if citation is None:
        return None
    if isinstance(citation, str):
        m = _CITATION.fullmatch(citation.strip())
        if not m:
            return None
        citation = {"volume": m.group(1), "reporter": m.group(2), "page": m.group(3)}
    if star := _STAR_PAGE.fullmatch(citation["page"]):
        citation = {**citation, "page": star.group(1)}
    if not _VOLUME.fullmatch(citation["volume"]) or not citation["page"].isdigit():
        return None
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", reporter_slug(citation["reporter"])):
        return None
    return citation


# Section 4: the reporters only the Supreme Court's decisions take, in the order that decides
# which citation the fallback uses (from 0.6.0, #50), with their reporter registry names.
SUPREME_COURT_REPORTERS = {"us": "us", "sct": "s-ct", "led": "l-ed", "led2d": "l-ed-2d"}
_SUPREME_ORDER = {"us": 0, "sct": 1, "led": 2, "led2d": 2}


def supreme_court_citation(citation: dict[str, str] | str | None) -> bool:
    """Section 4 (from 0.5.0): whether an official citation is one only the Supreme
    Court's decisions take: the United States Reports from volume 5, the Supreme Court Reporter,
    the Lawyers' Edition. 1 to 4 U.S. (Dallas) also print Pennsylvania and circuit decisions."""
    citation = reporter_citation(citation)
    if citation is None:
        return False
    reporter = reporter_slug(citation["reporter"]).replace("-", "")
    if reporter not in SUPREME_COURT_REPORTERS:
        return False
    return not (reporter == "us" and int(citation["volume"].split()[0]) <= 4)


def supreme_court_volume_fits(
    citation: dict[str, str] | str, decided: str, reporters: dict[str, Any]
) -> bool:
    """Section 4 (from 0.6.0, #50): whether the citation's volume is one whose decisions span the
    decision's date, by the reporter registry's supreme_court_volumes. A volume the registry
    doesn't list doesn't."""
    citation = reporter_citation(citation)
    assert citation is not None
    name = SUPREME_COURT_REPORTERS[reporter_slug(citation["reporter"]).replace("-", "")]
    volumes = reporters["supreme_court_volumes"]["reporters"][name]
    span = volumes.get(citation["volume"].split()[0])
    if span is None:
        return False
    start, end = period(decided)
    return period(span["first"])[0] <= end and start <= period(span["last"])[1]


def supreme_court_fallback_citation(facts: dict[str, Any]) -> dict[str, str] | str | None:
    """Section 4 (from 0.6.0, #50): of the decision's Supreme Court citations, the United States
    Reports decides, then the Supreme Court Reporter, then the Lawyers' Edition."""
    cited = [facts["reporter_citation"], *facts.get("parallel_citations", [])]
    ranked = [
        (_SUPREME_ORDER[reporter_slug(c["reporter"]).replace("-", "")], i, c)
        for i, c in enumerate(reporter_citation(c) for c in cited)
        if c is not None and supreme_court_citation(c)
    ]
    return min(ranked)[2] if ranked else facts["reporter_citation"]


def fallback_citation(facts: dict[str, Any]) -> dict[str, str] | None:
    """Section 5.6 (from 0.5.0): the citation the fallback uses.

    reporter_citation is the decision's official citation; printed_in is the volume and page the
    source's volume prints it on, and that volume's reporter. With no official citation, printed_in.
    When the official citation names printed_in's volume number but another reporter, the
    reporter is printed_in's. From 0.6.0 (#56), a citation that isn't a reporter citation gives
    None: the fallback can't use it.
    """
    official, printed_in = facts.get("reporter_citation"), facts.get("printed_in")
    if official is None:
        return reporter_citation(printed_in)
    official = reporter_citation(official)
    if official is None:
        return None
    printed_in = reporter_citation(printed_in)
    if (
        printed_in is not None
        and official["volume"] == printed_in["volume"]
        and reporter_slug(official["reporter"]).replace("-", "")
        != reporter_slug(printed_in["reporter"]).replace("-", "")
    ):
        return {**official, "reporter": printed_in["reporter"]}
    return official


def court_for_cap(cap_courts: dict[str, Any], cap_id: str, decided: str | None) -> str:
    """Section 4: the registry code registry/cap-courts.json gives a CAP court id, or Refusal."""
    entry = cap_courts["courts"].get(cap_id)
    if entry is None:
        raise Refusal("unregistered-court")
    if entry.get("review"):
        raise Refusal("court-under-review")
    return _dated(entry["codes"], "code", decided)


def compute(
    facts: dict[str, Any],
    courts: dict[str, Any],
    judges: dict[str, Any],
    cap_courts: dict[str, Any] | None = None,
    reporters: dict[str, Any] | None = None,
) -> str:
    """Spec section 12: a key from facts, or Refusal.

    courts is the court registry's "courts" map; judges is a judge registry's
    "judges" map (spec section 10.2; the vectors use a fixture); cap_courts is
    registry/cap-courts.json, for facts that name the court by its CAP id; reporters is
    registry/reporters.json, for a Supreme Court citation a source files under another court.
    """
    fact = facts.get("decided")
    decided = zeroed(fact) if fact is not None else None
    if "court" in facts:
        court = facts["court"]
    else:
        assert cap_courts is not None
        court = court_for_cap(cap_courts, facts["cap_court"], decided)
    if court not in courts:
        raise Refusal("unregistered-court")
    if fact is None:
        raise Refusal("no-decision-date")
    if decided is None:
        raise Refusal("date")
    if court != "scotus" and supreme_court_citation(facts.get("reporter_citation")):
        # Section 4: from 0.5.0 refused; from 0.6.0 (#50) keyed under the Supreme Court, unless
        # the citation's volume can't be the decision's.
        assert reporters is not None
        if not supreme_court_volume_fits(facts["reporter_citation"], decided, reporters):
            raise Refusal("court-conflict")
        court = "scotus"
        facts = {
            **facts,
            "court": court,
            "reporter_citation": supreme_court_fallback_citation(facts),
        }
    # Section 3: the registry's jurisdiction code, never the facts'.
    jurisdiction = jurisdiction_for(courts[court], decided)
    if profile_for(courts[court], decided) is None:
        raise Refusal("no-docket-profile")  # before the docket: no rpt. fallback (5.6)
    citation = fallback_citation(facts)
    printed = facts.get("docket")
    try:
        # Section 5.6 (from 0.6.0, #56): the docket first, whatever the citation.
        if printed is None:
            raise Refusal("no-docket")
        docket = docket_segment(courts, court, printed, decided)
    except Refusal:
        if citation is None:
            if facts.get("reporter_citation") is not None or facts.get("printed_in") is not None:
                raise Refusal("citation") from None  # a citation, but no reporter citation
            raise
        docket = rpt_segment(citation)
    ordinal = facts.get("decision_ordinal", 1)
    if docket.startswith("rpt.") and "volume_decisions" in facts:
        # Section 5.6 (from 0.5.0): count, in printed order, the decisions in the volume whose
        # fallback citation is the same and that share the date.
        before = facts["volume_decisions"][: facts["volume_position"]]
        ordinal = sum(
            1
            for d in before
            if d["decided"] == fact
            and (c := fallback_citation(d)) is not None
            and rpt_segment(c) == docket
        )
    elif docket.startswith("rpt.") and "page_decisions" in facts:
        # Section 5.6: count every decision that begins on the page and shares the date.
        before = facts["page_decisions"][: facts["page_position"]]
        ordinal = sum(1 for d in before if d["decided"] == fact)
    if ordinal < 1:
        raise Refusal("ordinal")
    parts: dict[str, Any] = {
        "jurisdiction": jurisdiction,
        "court": court,
        "docket": docket,
        "decided": decided,
        "decision_ordinal": ordinal,
        "role": None,
        "authors": [],
        "part_ordinal": None,
        "revised": None,
    }
    if (role := facts.get("role")) is not None:
        if role not in ROLES:
            raise Refusal("role")
        authors = facts.get("authors", [])
        if role == "per-curiam" and authors:
            raise Refusal("per-curiam-author")
        for author in authors:
            if court not in judges.get(author, {}).get("courts", []):
                raise Refusal("unregistered-author")
        part_ordinal = facts.get("part_ordinal", 1)
        if part_ordinal < 1:
            raise Refusal("ordinal")
        parts.update(role=role, authors=authors, part_ordinal=part_ordinal)
    if (revised := facts.get("revised")) is not None:
        if not is_date(revised) or revised < period_start(decided):
            raise Refusal("revised")
        parts["revised"] = revised
    key = format_key(parts)
    assert classify(key) is None, key
    return key


def printed_alias(
    facts: dict[str, Any],
    courts: dict[str, Any],
    judges: dict[str, Any],
    cap_courts: dict[str, Any] | None = None,
    reporters: dict[str, Any] | None = None,
) -> str:
    """Section 6.3: the printed-date alias, the decision key computed from the printing alone.

    facts' printed_decided is the date the printing prints (decided when absent), page_decisions'
    likewise, and printed_ordinal the decision's position in printed order among decisions
    whose aliases are otherwise the same (1 when absent).
    """
    printed = {
        k: v
        for k, v in facts.items()
        if k not in ("role", "authors", "part_ordinal", "revised", "decision_ordinal")
    }
    printed["decided"] = facts.get("printed_decided", facts.get("decided"))
    printed["decision_ordinal"] = facts.get("printed_ordinal", 1)
    if "volume_decisions" in facts:
        printed["volume_decisions"] = [
            {**d, "decided": d.get("printed_decided", d["decided"])}
            for d in facts["volume_decisions"]
        ]
    if "page_decisions" in facts:
        printed["page_decisions"] = [
            {**d, "decided": d.get("printed_decided", d["decided"])}
            for d in facts["page_decisions"]
        ]
    return "crk-printed:" + compute(printed, courts, judges, cap_courts, reporters)


def consolidated_aliases(facts: dict[str, Any], courts: dict[str, Any], key: str) -> list[str]:
    """Key-shaped aliases for the other dockets of a consolidated case (section 11.1)."""
    printed = facts.get("docket")
    if printed is None or parse(key)["fallback"]:
        return []
    others = other_dockets(courts, facts["court"], printed, facts["decided"])
    decision = parse(key)
    return ["crk:" + decision_key({**decision, "docket": d, "decision_ordinal": 1}) for d in others]


# The minted-key ledger (spec section 13.2).


def stem(key: str) -> str:
    """The decision key without its decision ordinal."""
    return decision_key({**parse(key), "decision_ordinal": 1})


def mint(ledger: list[dict[str, Any]], decision: str, candidate: str) -> dict[str, Any]:
    """Section 13.2: the key a ledger confirms or advances a candidate to.

    Returns {key, minted (false when the ledger confirms the decision's active key), replaces
    (the decision's active key the new one supersedes, or None)}.
    """
    active = [e for e in ledger if e["decision"] == decision and e["status"] == "active"]
    assert len(active) <= 1, decision
    if active and stem(active[0]["key"]) == stem(candidate):
        return {"key": active[0]["key"], "minted": False, "replaces": None}
    held = {e["key"] for e in ledger}
    parts = parse(candidate)
    key = candidate
    while key in held:
        parts["decision_ordinal"] += 1
        key = decision_key(parts)
    return {"key": key, "minted": True, "replaces": active[0]["key"] if active else None}


OVERRIDING_SOURCES = frozenset({"official", "human-curated"})


def is_provisional(facts: dict[str, Any]) -> bool:
    """Section 13.3: whether second sources' dates make the key provisional.

    facts' second_sources is [{date (ISO 8601, reduced or not), kind}]: kind official or
    human-curated may override a date the printing gives in full; any other kind (courtlistener,
    engine-output, another printing, ...) only a date the printing gives to the month or year.
    """
    printed = facts.get("printed_decided", facts["decided"])
    sources = facts.get("second_sources", [])
    if len(printed) == 10:
        return any(s["kind"] in OVERRIDING_SOURCES and s["date"] != printed for s in sources)
    return any(not s["date"].startswith(printed) for s in sources)


def resolve(ledger: list[dict[str, Any]], key: str) -> dict[str, Any]:
    """Section 13.1: follow replaced-by to the current key; {key, decision, provisional}."""
    entries = {e["key"]: e for e in ledger}
    entry, seen = entries[key], {key}
    while entry.get("replaced_by"):
        entry = entries[entry["replaced_by"]]
        assert entry["key"] not in seen, key
        seen.add(entry["key"])
    return {
        "key": entry["key"],
        "decision": entry["decision"],
        "provisional": entry.get("provisional", False),
    }


def errata_problem(errata: dict[str, Any], previous: dict[str, Any] | None = None) -> str | None:
    """Section 13.4, past what schema/crk-errata.schema.json checks: seq, keys, append-only."""
    entries = errata["entries"]
    if [e["seq"] for e in entries] != list(range(1, len(entries) + 1)):
        return "seq"
    for e in entries:
        if classify(e["key"]) is not None or (
            "replaced_by" in e and classify(e["replaced_by"]) is not None
        ):
            return "key"
    if previous is not None and entries[: len(previous["entries"])] != previous["entries"]:
        return "append-only"
    return None


def author_for(printed: str, court: str, judges: dict[str, Any]) -> str:
    """Section 10.2: the slug whose name or printed forms equal a byline's name after case
    folding, for the court."""
    name = printed.casefold()
    found = [
        slug
        for slug, entry in sorted(judges.items())
        if court in entry.get("courts", [])
        and name
        in [entry["name"].casefold()] + [f["form"].casefold() for f in entry.get("printed", [])]
    ]
    if len(found) != 1:
        raise Refusal("unregistered-author")
    return found[0]


# Aliases (spec section 11.1).


def normalize_alias(scheme: str, printed: str) -> str:
    if scheme == "cite":
        m = re.fullmatch(r"([0-9]+(?:\s+[0-9]+/[0-9]+)?)\s+(.+?)\s+([0-9]+)", printed.strip())
        assert m, printed
        return f"cite:{volume_text(m.group(1))}-{reporter_slug(m.group(2))}-{m.group(3)}"
    if scheme == "neutral":
        return f"neutral:{slug(printed)}"
    if scheme == "ca6":
        return f"ca6:{printed.strip().lower()}"
    if scheme == "govinfo":
        return f"govinfo:{printed.strip()}"
    if scheme == "cap":
        m = re.fullmatch(r"([a-z0-9-]+)/([0-9]+)/cases/([0-9]+-[0-9]{2})\.json", printed.strip())
        assert m, printed
        return f"cap:{m.group(1)}/{m.group(2)}/{m.group(3)}"
    raise ValueError(f"no printed form for scheme {scheme!r}")


# Several printings, and several decisions with one candidate (sections 5.9 and 7.1, from 0.6.0).

# Section 5.9: link sources that confirm printings are one decision. A parallel citation, two
# printings listing one citation, is the other; a link from any other source (courtlistener,
# engine-output) confirms nothing.
CONFIRMING_SOURCES = frozenset({"official", "human-curated"})


def _cite_aliases(printing: dict[str, Any]) -> set[tuple[str, str, str]]:
    """A printing's citations as (volume, reporter slug without `-`, page). Section 5.9 also
    counts another abbreviation of the same reporter (`App. Div.` for `A.D.`) as the same; this
    reading has no table of abbreviations, so the vectors write each reporter one way."""
    found = set()
    for c in printing.get("citations", []):
        if (parsed := reporter_citation(c)) is not None:
            reporter = reporter_slug(parsed["reporter"]).replace("-", "")
            found.add((volume_text(parsed["volume"]), reporter, parsed["page"]))
    return found


def _components(ids: list[str], pairs: list[tuple[str, str]]) -> list[list[str]]:
    parent = {i: i for i in ids}

    def find(i: str) -> str:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a, b in pairs:
        if a in parent and b in parent:
            parent[find(a)] = find(b)
    groups: dict[str, list[str]] = {}
    for i in ids:
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def _dates_fit(a: str, b: str) -> bool:
    """Whether two decided segments can be one decision's date (section 5.9 rule 1)."""
    for x, y in zip(a.split("-"), b.split("-"), strict=True):
        if x != y and "00" not in (x, y):
            return False
        if "00" in (x, y) and x != y:
            return True
    return True


def _merge_dates(dates: list[str]) -> str | None:
    """Section 5.9 rule 1: the most precise date every printing's date fits, or None."""
    best = dates[0].split("-")
    for d in dates[1:]:
        parts = d.split("-")
        for i in range(3):
            if parts[i] == "00":
                continue
            if best[i] == "00" and all(best[j] != "00" for j in range(i)):
                best[i] = parts[i]
            elif best[i] != parts[i] and best[i] != "00":
                return None
    return "-".join(best)


def _official(court: str, decided: str, official: dict[str, Any]) -> set[str]:
    steps = official.get(court)
    if not steps:
        return set()
    chosen = _dated(steps, "reporters", decided) or []
    return {r.replace("-", "") for r in chosen}


def one_decision(
    printings: list[dict[str, Any]],
    official: dict[str, Any],
    key_printing: str | None = None,
) -> tuple[str, bool]:
    """Section 5.9: the candidate key of a decision printed more than once, from its printings'
    candidates, or Refusal(printings-disagree). official is the reporter registry's official;
    key_printing is the printing a person's ruling names to decide the key (from 0.6.2, D167),
    which stands in for rule 4 only where the official-reporter table can't decide. Returns the
    key and whether the ruling's key_printing contradicts what rules 1 to 4 give (a conflict;
    the table wins)."""
    parts = [(p, parse(p["candidate"])) for p in printings]
    chosen = next((q for p, q in parts if p["id"] == key_printing), None)
    if len({q["court"] for _, q in parts}) > 1:
        raise Refusal("printings-disagree")
    decided = _merge_dates([q["decided"] for _, q in parts])
    if decided is None:
        raise Refusal("printings-disagree")
    dockets = {q["docket"] for _, q in parts if not q["fallback"]}
    citations = {q["docket"] for _, q in parts if q["fallback"]}
    if len(dockets) == 1 or (not dockets and len(citations) == 1):
        segment = dockets.pop() if dockets else citations.pop()
    else:
        # Rules 2 to 4: the printing in the decision's official reporter decides.
        court = parts[0][1]["court"]
        names = _official(court, decided, official)
        top = [(p, q) for p, q in parts if p["reporter"].replace("-", "") in names]
        segments = {q["docket"] for _, q in top}
        if dockets:
            segments = {s for s in segments if not s.startswith("rpt.")} or segments
        if len(segments) == 1:
            segment = segments.pop()
        elif chosen is not None:
            # From 0.6.2 (D167 (1)): the table names no reporter for the court and date, none
            # of the printings is in it, or its printings disagree; the ruling's printing decides.
            segment = chosen["docket"]
        else:
            raise Refusal("printings-disagree")
    conflict = chosen is not None and chosen["docket"] != segment
    ordinal = min(q["decision_ordinal"] for _, q in parts if q["docket"] == segment)
    first = parts[0][1]
    key = decision_key(
        {**first, "docket": segment, "decided": decided, "decision_ordinal": ordinal}
    )
    return key, conflict


def _same_name(a: str, b: str) -> bool:
    """Section 7.1 rule 1(a): case names compared after case folding, letters and digits only."""

    def norm(n: str) -> str:
        return "".join(c for c in n.casefold() if c.isalnum())

    return norm(a) == norm(b)


def _printed_order(p: dict[str, Any]) -> tuple[Any, ...]:
    number = re.match(r"[0-9]+", p["volume"])
    return (
        p["reporter"],
        int(number.group(0)) if number else 0,
        p["volume"],
        p["page"],
        p["position"],
    )


def decisions(
    printings: list[dict[str, Any]],
    links: list[dict[str, Any]],
    reporters: dict[str, Any],
    rulings: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Sections 5.9, 7.1 and 13.2 with an empty ledger: the decisions a producer holds, from
    their printings, each with its key or refusal.

    printings: [{id, candidate, reporter (slug), volume, page, position, name, citations}];
    links: [{printings: [id, id, ...], source}], the producer's links between printings, each
    linking every pair of the printings it lists (from 0.6.3, D187 (1): a CourtListener cluster
    links every pair of its printings, not only neighbouring ones); reporters:
    the reporter registry, or a fixture with its official and editions; rulings: a person's
    rulings (from 0.6.2, D167), [{id, printings: [ids], ruling (one-decision or
    distinct-decisions), key_printing (one-decision only, optional), evidence, by, date}].
    Returns [{printings: [ids], key} or {printings: [ids], error}] in minting order, with
    conflicts: [ruling ids] on a decision a ruling contradicts. With no rulings, the result is
    what 0.6.1 gives.
    """
    by_id = {p["id"]: p for p in printings}
    ids = [p["id"] for p in printings]
    official = reporters.get("official", {})
    editions = [{r.replace("-", "") for r in e["reporters"]} for e in reporters.get("editions", [])]
    rulings = rulings or []
    # A person's ruling that printings are one decision links them as a second source would;
    # one that they are distinct parts every pair of them.
    one = [r for r in rulings if r["ruling"] == "one-decision"]
    apart = {
        frozenset((a, b)): r["id"]
        for r in rulings
        if r["ruling"] == "distinct-decisions"
        for a in r["printings"]
        for b in r["printings"]
        if a != b
    }
    links = links + [{"printings": r["printings"], "source": "human-curated"} for r in one]
    # From 0.6.3 (D187 (1)): a link, a cluster among them, links every pair of its printings.
    links = [
        {"printings": [a, b], "source": lk["source"]}
        for lk in links
        for x, a in enumerate(lk["printings"])
        for b in lk["printings"][x + 1 :]
    ]
    conflicts: dict[str, set[str]] = {}  # printing id -> ruling ids that contradict

    # The producer's links make groups, except between printings that can't be one decision; such a
    # pair breaks none of the link's other pairs (from 0.6.3, D187 (1)).
    def can_be_one(a: str, b: str) -> bool:
        pa, pb = parse(by_id[a]["candidate"]), parse(by_id[b]["candidate"])
        return pa["court"] == pb["court"] and _dates_fit(pa["decided"], pb["decided"])

    linked = [
        (lk["printings"][0], lk["printings"][1])
        for lk in links
        if can_be_one(lk["printings"][0], lk["printings"][1])
    ]
    cites = {i: _cite_aliases(by_id[i]) for i in ids}
    confirmed = [
        (lk["printings"][0], lk["printings"][1])
        for lk in links
        if lk["source"] in CONFIRMING_SOURCES
    ] + [(a, b) for a in ids for b in ids if a < b and cites[a] & cites[b]]
    confirmed_pairs = {(a, b) for a, b in confirmed} | {(b, a) for a, b in confirmed}
    units: list[tuple[list[str], str | None, str | None]] = []  # (printings, candidate, error)
    grouped: set[str] = set()
    for group in _components(ids, linked):
        if len({by_id[i]["candidate"] for i in group}) < 2:
            continue
        grouped |= set(group)
        # Section 5.9: only a link a second source confirms makes them one decision.
        if len(_components(group, confirmed)) > 1:
            units.append((group, None, "printings-disagree"))
            continue
        ruling = next((r for r in one if r.get("key_printing") in group), None)
        key_printing = ruling["key_printing"] if ruling else None
        try:
            key, conflict = one_decision([by_id[i] for i in group], official, key_printing)
            units.append((group, key, None))
            if conflict:
                conflicts.setdefault(group[0], set()).add(ruling["id"])
        except Refusal as refusal:
            units.append((group, None, refusal.args[0]))
    for unit_ids, candidate, _ in list(units):
        for i in unit_ids:
            by_id[i] = {**by_id[i], "candidate": candidate or by_id[i]["candidate"]}

    # Section 7.1: printings and decisions with one candidate.
    by_candidate: dict[str, list[str]] = {}
    for i in ids:
        if i not in grouped:
            by_candidate.setdefault(by_id[i]["candidate"], []).append(i)
    for unit_ids, candidate, _ in units:
        if candidate is not None:
            by_candidate.setdefault(candidate, []).extend(unit_ids)
    units = [u for u in units if u[2] is not None]
    hint: dict[str, tuple[Any, ...]] = {}
    for candidate, members in by_candidate.items():
        key = parse(candidate)
        full_docket = not key["fallback"] and not key["decided"].endswith("-00")
        sure = [(a, b) for a in members for b in members if a < b and cites[a] & cites[b]]
        sure += [
            (a, b) for a, b in linked if a in members and b in members and (a, b) in confirmed_pairs
        ]
        pairs = [(a, b) for a, b in linked if a in members and b in members]
        for a in members:
            for b in members:
                pa, pb = by_id[a], by_id[b]
                if a >= b or (pa["reporter"], pa["volume"]) == (pb["reporter"], pb["volume"]):
                    continue
                editions_pair = {pa["reporter"].replace("-", ""), pb["reporter"].replace("-", "")}
                if full_docket and (
                    _same_name(pa["name"], pb["name"]) or editions_pair in editions
                ):
                    pairs.append((a, b))  # rule 1
        # From 0.6.2 (D167 (3)): a person's ruling that they are distinct parts what rule 1 or an
        # engine link joins; one a second source contradicts is a conflict, and the source stands.
        for a, b in sure:
            if (r := apart.get(frozenset((a, b)))) is not None:
                conflicts.setdefault(a, set()).add(r)
        pairs = [(a, b) for a, b in pairs if frozenset((a, b)) not in apart] + sure
        found = _components(members, pairs)
        if len(found) == 1:
            units.append((found[0], candidate, None))
            continue
        volumes = None
        for group in found:
            in_group = {(by_id[i]["reporter"], by_id[i]["volume"]) for i in group}
            volumes = in_group if volumes is None else volumes & in_group
        if volumes:
            # Rule 2: one volume prints every one of them separately: its printed order.
            volume = sorted(volumes)[0]
            for group in found:
                hint[group[0]] = min(
                    _printed_order(by_id[i])
                    for i in group
                    if (by_id[i]["reporter"], by_id[i]["volume"]) == volume
                )
        elif (
            full_docket
            and len({by_id[i]["reporter"] for i in members}) == 1
            and all(
                not any(_same_name(by_id[a]["name"], by_id[b]["name"]) for a in g for b in h)
                for x, g in enumerate(found)
                for h in found[x + 1 :]
            )
        ):
            # Rule 3: one reporter, different case names: printed order.
            for group in found:
                hint[group[0]] = min(_printed_order(by_id[i]) for i in group)
        elif len({by_id[i]["reporter"] for i in members}) == 1 and all(
            any(frozenset((a, b)) in apart for a in g for b in h)
            for x, g in enumerate(found)
            for h in found[x + 1 :]
        ):
            # From 0.6.2 (D167 (3)): a person ruled them distinct; printed order in their reporter.
            for group in found:
                hint[group[0]] = min(_printed_order(by_id[i]) for i in group)
        else:
            units += [(group, None, "shared-candidate") for group in found]
            continue
        units += [(group, candidate, None) for group in found]

    # Section 13.2, an empty ledger: in candidate order, then printed order.
    def order(unit: tuple[list[str], str | None, str | None]) -> tuple[Any, ...]:
        group, candidate, _ = unit
        first = hint.get(group[0]) or min(_printed_order(by_id[i]) for i in group)
        if candidate is None:
            return (1, "", 0, first)
        return (0, stem(candidate), parse(candidate)["decision_ordinal"], first)

    held: dict[str, set[int]] = {}
    result = []
    for group, candidate, error in sorted(units, key=order):
        found_conflicts = sorted(set().union(*(conflicts.get(i, set()) for i in group)))
        extra = {"conflicts": found_conflicts} if found_conflicts else {}
        if candidate is None:
            result.append({"printings": sorted(group), "error": error, **extra})
            continue
        key = parse(candidate)
        used = held.setdefault(stem(candidate), set())
        while key["decision_ordinal"] in used:
            key["decision_ordinal"] += 1
        used.add(key["decision_ordinal"])
        result.append({"printings": sorted(group), "key": decision_key(key), **extra})
    return result
