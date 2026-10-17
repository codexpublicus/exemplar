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

_LABEL = re.compile(r"^(?:Docket No\.|Case No\.|Nos?\.)\s*")
_DASHES = str.maketrans(dict.fromkeys("‐‑‒–—−", "-"))


def clean(printed: str) -> str:
    text = _LABEL.sub("", printed.strip()).translate(_DASHES)
    if text.endswith(".") and not text.endswith("Orig."):
        text = text[:-1]
    return text


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
    text = re.sub(r"\s+", "", text.lower()).replace(":", "_").replace("/", "_")
    return text if DOCKET.fullmatch(text) and not text.startswith("rpt.") else None


PROFILES = {"scotus-ot1971": _scotus, "us-coa": _coa, "us-district": _district, "printed": _printed}


def profile_for(court: dict[str, Any], decided: str | None) -> str | None:
    chosen = None
    for entry in court["profiles"]:
        if entry["from"] is None or decided is None or entry["from"] <= decided:
            chosen = entry["profile"]
    return chosen


def docket_segment(
    registry: dict[str, Any], court: str, printed: str, decided: str | None = None
) -> str:
    """The docket segment, or Refusal(no-docket / no-docket-profile / docket-profile)."""
    text = clean(printed)
    if not text:
        raise Refusal("no-docket")
    profile = profile_for(registry["courts"][court], decided)
    if profile is None:
        raise Refusal("no-docket-profile")
    segment = PROFILES[profile](text)
    if segment is None:
        raise Refusal("docket-profile")
    return segment


def slug(text: str) -> str:
    text = re.sub(r"[.'’(),]", "", text.lower())
    return re.sub(r"\s+", "-", text.strip())


def rpt_segment(citation: dict[str, str]) -> str:
    return f"rpt.{citation['volume']}-{slug(citation['reporter'])}-{citation['page']}"


def compute(facts: dict[str, Any], registry: dict[str, Any]) -> str:
    """Spec section 12: a key from facts, or Refusal."""
    court = facts["court"]
    if facts.get("country") != "us" or court not in registry["courts"]:
        raise Refusal("unregistered-court")
    decided = facts.get("decided")
    if decided is None:
        raise Refusal("no-decision-date")
    if PARTIAL_DATE.fullmatch(decided):
        raise Refusal("incomplete-date")
    if not is_date(decided):
        raise Refusal("date")
    citation = facts.get("reporter_citation")
    printed = facts.get("docket")
    try:
        if printed is None:
            raise Refusal("no-docket")
        docket = docket_segment(registry, court, printed, decided)
    except Refusal as refusal:
        if refusal.args[0] == "no-docket-profile" or citation is None:
            raise
        docket = rpt_segment(citation)
    ordinal = facts.get("decision_ordinal", 1)
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
            if court not in registry["judges"].get(author, {}).get("courts", []):
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
