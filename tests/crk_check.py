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

COURT = re.compile(r"[a-z][a-z0-9-]*")
DOCKET = re.compile(r"[a-z0-9][a-z0-9_.-]*")
RPT = re.compile(r"rpt\.[0-9]+-[a-z0-9][a-z0-9-]*-[0-9]+")
AUTHOR = re.compile(r"[a-z][a-z-]*")
ORD = re.compile(r"[2-9]|[1-9][0-9]+")
DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
PARTIAL_DATE = re.compile(r"[0-9]{4}(-[0-9]{2})?")


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


def classify(key: str) -> str | None:
    """The error class of spec section 2.5, or None for a valid key."""
    if key.count("@") > 1:
        return "structure"
    body, at, revised = key.partition("@")
    segments = body.split("/")
    if len(segments) not in (4, 5):
        return "structure"
    country, court, docket, decided = segments[:4]
    if country != "us":
        return "country"
    if not COURT.fullmatch(court):
        return "court"
    if not DOCKET.fullmatch(docket) or (docket.startswith("rpt.") and not RPT.fullmatch(docket)):
        return "docket"
    day, tilde, ordinal = decided.partition("~")
    if not is_date(day):
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
    if at and (not is_date(revised) or revised < day):
        return "revised"
    return None


def parse(key: str) -> dict[str, Any]:
    """Split a valid key into the parts recorded in parse.jsonl."""
    assert classify(key) is None, key
    body, _, revised = key.partition("@")
    segments = body.split("/")
    country, court, docket, decided = segments[:4]
    day, _, ordinal = decided.partition("~")
    parts: dict[str, Any] = {
        "country": country,
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
    key = f"{parts['country']}/{parts['court']}/{parts['docket']}/{parts['decided']}"
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


def _coa(text: str) -> str | None:
    text = re.sub(r"\s*\(L\)$", "", text)
    text = re.sub(r"(?<=[0-9])-[A-Za-z]$", "", text)
    return text if re.fullmatch(r"[0-9]{2}-[0-9]{3,5}", text) else None


def _district(text: str) -> str | None:
    m = re.fullmatch(
        r"([0-9]):([0-9]{2})-([a-z]{1,4})-([0-9]{1,5})(?:-[a-z]{2,4})*", text, re.IGNORECASE
    )
    return f"{m.group(1)}_{m.group(2)}-{m.group(3).lower()}-{m.group(4)}" if m else None


def _printed(text: str) -> str | None:
    text = re.sub(r"(?<=[0-9]),(?=\s*[0-9])", "_", text.lower()).replace(",", "")
    text = re.sub(r"\s+", "", text).replace(":", "_").replace("/", "_")
    return text if DOCKET.fullmatch(text) and not text.startswith("rpt.") else None


PROFILES = {"scotus-ot1971": _scotus, "us-coa": _coa, "us-district": _district, "printed": _printed}


def profile_for(court: dict[str, Any], decided: str | None) -> str | None:
    chosen = None
    for entry in court["profiles"]:
        if entry["from"] is None or decided is None or entry["from"] <= decided:
            chosen = entry["profile"]
    return chosen


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
    text = re.sub(r"[.'’(),]", "", text.lower())
    return re.sub(r"\s+", "-", text.strip())


def rpt_segment(citation: dict[str, str]) -> str:
    return f"rpt.{citation['volume']}-{slug(citation['reporter'])}-{citation['page']}"


def compute(facts: dict[str, Any], courts: dict[str, Any], judges: dict[str, Any]) -> str:
    """Spec section 12: a key from facts, or Refusal.

    courts is the court registry's "courts" map; judges is a judge registry's
    "judges" map (spec section 10.2; the vectors use a fixture).
    """
    court = facts["court"]
    if facts.get("country") != "us" or court not in courts:
        raise Refusal("unregistered-court")
    decided = facts.get("decided")
    if decided is None:
        raise Refusal("no-decision-date")
    if PARTIAL_DATE.fullmatch(decided):
        raise Refusal("incomplete-date")
    if not is_date(decided):
        raise Refusal("date")
    if profile_for(courts[court], decided) is None:
        raise Refusal("no-docket-profile")  # before the docket: no rpt. fallback (5.6)
    citation = facts.get("reporter_citation")
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
    if docket.startswith("rpt.") and "page_decisions" in facts:
        # Section 5.6: count every decision that begins on the page and shares the date.
        before = facts["page_decisions"][: facts["page_position"]]
        ordinal = sum(1 for d in before if d["decided"] == decided)
    if ordinal < 1:
        raise Refusal("ordinal")
    parts: dict[str, Any] = {
        "country": "us",
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
        if not is_date(revised) or revised < decided:
            raise Refusal("revised")
        parts["revised"] = revised
    key = format_key(parts)
    assert classify(key) is None, key
    return key


def consolidated_aliases(facts: dict[str, Any], courts: dict[str, Any], key: str) -> list[str]:
    """Key-shaped aliases for the other dockets of a consolidated case (section 11.1)."""
    printed = facts.get("docket")
    if printed is None or parse(key)["fallback"]:
        return []
    others = other_dockets(courts, facts["court"], printed, facts["decided"])
    decision = parse(key)
    return ["crk:" + decision_key({**decision, "docket": d, "decision_ordinal": 1}) for d in others]


def author_for(printed: str, court: str, judges: dict[str, Any]) -> str:
    """Section 10.2: the slug whose name or printed forms equal a byline's name, for the court."""
    found = [
        slug
        for slug, entry in sorted(judges.items())
        if court in entry.get("courts", [])
        and (
            printed == entry.get("name") or printed in [f["form"] for f in entry.get("printed", [])]
        )
    ]
    if len(found) != 1:
        raise Refusal("unregistered-author")
    return found[0]


# Aliases (spec section 11.1).


def normalize_alias(scheme: str, printed: str) -> str:
    if scheme == "cite":
        m = re.fullmatch(r"([0-9]+)\s+(.+?)\s+([0-9]+)", printed.strip())
        assert m, printed
        return f"cite:{m.group(1)}-{slug(m.group(2))}-{m.group(3)}"
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
