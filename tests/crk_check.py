# SPDX-FileCopyrightText: Copyright (c) 2026 Codex Publicus contributors
# SPDX-License-Identifier: BSD-3-Clause

"""A minimal reading of spec/court-record-key.md, used only to check the vectors.

It is written from the spec's prose, not from any producer, so a vector that
disagrees with it points at either the vector or the spec. Nothing here is a
library; vectors MUST NOT be generated from it.
"""

import re
from datetime import date
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
    date, a year and month, or a year), or None when it is none of these."""
    if not ISO_DECIDED.fullmatch(fact):
        return None
    segment = {4: fact + "-00-00", 7: fact + "-00"}.get(len(fact), fact)
    return segment if is_decided(segment) else None


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


def _scotus(text: str) -> str | None:
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


def _scotus_numbered(text: str) -> str | None:
    if m := re.fullmatch(r"([0-9]{1,5})", text):
        return m.group(1)
    if m := re.fullmatch(r"([0-9]{1,5}),? misc\.?", text, re.IGNORECASE):
        return f"{m.group(1)}-misc"
    if m := re.fullmatch(r"([0-9]{1,3})[,.]? orig(?:inal)?\.?", text, re.IGNORECASE):
        return f"{m.group(1)}-orig"
    return None


def _coa(text: str) -> str | None:
    text = re.sub(r"\s*\(L\)$", "", text)
    text = re.sub(r"(?<=[0-9])-[A-Za-z]$", "", text)
    return text if re.fullmatch(r"[0-9]{2}-[0-9]{3,5}", text) else None


def _cafc(text: str) -> str | None:
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


def _district(text: str) -> str | None:
    m = re.fullmatch(
        r"([0-9]):([0-9]{2})-([a-z]{1,4})-([0-9]{1,5})(?:-[a-z]{2,4})*", text, re.IGNORECASE
    )
    return f"{m.group(1)}_{m.group(2)}-{m.group(3).lower()}-{m.group(4)}" if m else None


def _printed(text: str) -> str | None:
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


def docket_segment(
    courts: dict[str, Any], court: str, printed: str, decided: str | None = None
) -> str:
    """The docket segment, or Refusal(no-docket-profile / no-docket / docket-profile)."""
    profile = profile_for(courts[court], decided)
    if profile is None:
        raise Refusal("no-docket-profile")
    text = clean(printed)
    if not text:
        raise Refusal("no-docket")
    segment = PROFILES[profile](text)
    if segment is None:
        raise Refusal("docket-profile")
    return segment


def other_dockets(
    courts: dict[str, Any], court: str, printed: str, decided: str | None = None
) -> list[str]:
    """Docket segments of the other dockets a printed list names (sections 5.1, 11.1)."""
    profile = profile_for(courts[court], decided)
    segments = [PROFILES[profile](item) for item in clean_all(printed)[1:]] if profile else []
    return [s for s in segments if s is not None]


def slug(text: str) -> str:
    """Section 5.6: a reporter abbreviation reduced to a slug (`&` deleted from 0.5.0)."""
    text = re.sub(r"[.'’(),&]", "", text.lower())
    return re.sub(r"\s+", "-", text.strip())


def volume_text(volume: str) -> str:
    """Section 5.6 (from 0.5.0): a volume numbered with a fraction, `81 1/2`, is `81-1-2`."""
    return re.sub(r"[\s/]+", "-", volume.strip())


def rpt_segment(citation: dict[str, str]) -> str:
    return f"rpt.{volume_text(citation['volume'])}-{slug(citation['reporter'])}-{citation['page']}"


SUPREME_COURT_REPORTERS = frozenset({"us", "sct", "led", "led2d"})


def supreme_court_citation(citation: dict[str, str] | None) -> bool:
    """Section 4 (from 0.5.0): whether an official citation is one only the Supreme
    Court's decisions take: the United States Reports from volume 5, the Supreme Court Reporter,
    the Lawyers' Edition. 1 to 4 U.S. (Dallas) also print Pennsylvania and circuit decisions."""
    if citation is None:
        return False
    reporter = slug(citation["reporter"]).replace("-", "")
    if reporter not in SUPREME_COURT_REPORTERS:
        return False
    return not (reporter == "us" and int(citation["volume"].split()[0]) <= 4)


def fallback_citation(facts: dict[str, Any]) -> dict[str, str] | None:
    """Section 5.6 (from 0.5.0): the citation the fallback uses.

    reporter_citation is the decision's official citation; printed_in is the volume and page the
    source's volume prints it on, and that volume's reporter. With no official citation, printed_in.
    When the official citation names printed_in's volume number but another reporter, the
    reporter is printed_in's.
    """
    official, printed_in = facts.get("reporter_citation"), facts.get("printed_in")
    if official is None:
        return printed_in
    if (
        printed_in is not None
        and official["volume"] == printed_in["volume"]
        and slug(official["reporter"]).replace("-", "")
        != slug(printed_in["reporter"]).replace("-", "")
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
) -> str:
    """Spec section 12: a key from facts, or Refusal.

    courts is the court registry's "courts" map; judges is a judge registry's
    "judges" map (spec section 10.2; the vectors use a fixture); cap_courts is
    registry/cap-courts.json, for facts that name the court by its CAP id.
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
        raise Refusal("court-conflict")  # section 4, from 0.5.0
    # Section 3: the registry's jurisdiction code, never the facts'.
    jurisdiction = jurisdiction_for(courts[court], decided)
    if profile_for(courts[court], decided) is None:
        raise Refusal("no-docket-profile")  # before the docket: no rpt. fallback (5.6)
    citation = fallback_citation(facts)
    printed = facts.get("docket")
    try:
        if printed is None:
            raise Refusal("no-docket")
        docket = docket_segment(courts, court, printed, decided)
    except Refusal:
        if citation is None:
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
    return "crk-printed:" + compute(printed, courts, judges, cap_courts)


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
        return f"cite:{volume_text(m.group(1))}-{slug(m.group(2))}-{m.group(3)}"
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
