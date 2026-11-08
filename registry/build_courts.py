# SPDX-FileCopyrightText: Copyright (c) 2026 Codex Publicus contributors
# SPDX-License-Identifier: BSD-3-Clause

"""Build registry/courts.json from the vendored courts-db snapshot.

    uv run python registry/build_courts.py          # rewrite registry/courts.json
    uv run python registry/build_courts.py --check  # exit 1 if it is out of date

The output is a pure function of registry/sources/courts-db/courts.json and the
rules below, so tests/test_courts_registry.py can rebuild it and compare. The
registry is append-only (spec section 10.3): when a later courts-db snapshot is
vendored, a rebuild may add courts and nothing else; the tests don't check that
against earlier releases, so check it in review.
"""

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "registry" / "sources" / "courts-db" / "courts.json"
OUTPUT = ROOT / "registry" / "courts.json"

VERSION = "2026.11.05"
SPEC_VERSION = "0.7.0"

PROVENANCE = {
    "name": "courts-db",
    "publisher": "Free Law Project",
    "repository": "https://github.com/freelawproject/courts-db",
    "commit": "c22604dff8b6819d022cc5ddfd6d9080101149e3",
    "commit_date": "2026-10-07T13:50:54-06:00",
    "path": "courts_db/data/courts.json",
    "vendored_copy": "registry/sources/courts-db/courts.json",
    "retrieved": "2026-10-18",
    "license_as_stated": (
        "BSD 2-Clause License, per the repository's LICENSE file at that commit "
        "(copied verbatim to registry/sources/courts-db/LICENSE)"
    ),
}

COURT_RULE = re.compile(r"[a-z][a-z0-9-]*")
COURTS_OF_APPEALS = {f"ca{n}" for n in range(1, 12)} | {"cadc"}
US_COA_FROM = "1971-01-01"  # the regional circuits' yy-nnnnn dockets (#36)
NOT_A_COURT = {"usdistct"}  # courts-db's generic "United States District Court"


def profiles(court: dict[str, Any]) -> list[dict[str, str | None]]:
    """The docket profiles (spec section 5) this registry assigns to a courts-db court."""
    code = court["id"]
    if code == "scotus":
        return [
            {"from": None, "profile": "scotus-numbered"},
            {"from": "1971-07-01", "profile": "scotus-ot1971"},
        ]
    if code == "ca11":
        # spec section 5.3: the Eleventh Circuit from its start (1981-10-01)
        return [{"from": None, "profile": "us-coa"}]
    if code in COURTS_OF_APPEALS:
        # spec section 5.3, from 0.7.0 (#36, D192): us-coa from 1971-01-01, printed before
        return [
            {"from": None, "profile": "printed"},
            {"from": US_COA_FROM, "profile": "us-coa"},
        ]
    if code == "cafc":
        # spec section 5.8, from 0.5.0: from the court's first day, 1982-10-01
        return [{"from": "1982-10-01", "profile": "us-cafc"}]
    federal = court.get("system") == "federal"
    if (
        federal
        and court.get("type") in ("trial", "bankruptcy")
        and not code.startswith("bap")
        and code not in NOT_A_COURT
    ):
        return [{"from": None, "profile": "us-district"}]
    return [{"from": None, "profile": "printed"}]


def exclusion(court: dict[str, Any]) -> str | None:
    if not COURT_RULE.fullmatch(court["id"]):
        return "id does not match the court rule (spec section 2.1)"
    return None


# Spec section 3: the jurisdiction code of the sovereign that issued a court's decisions.

# A territory's local courts take the territory's ISO 3166-1 code; the federal courts seated
# there (prd, prb, vid, vib, gud, gub, nmid, nmib) stay under us.
TERRITORIAL = {
    "prsupreme": "pr",
    "prapp": "pr",
    "virginislands": "vi",
    "visuper": "vi",
    "vimunict": "vi",
    "vipolct": "vi",
    "guam": "gu",
    "superctguam": "gu",
    "amsamoa": "as",
    "amsamoatc": "as",
    "nmi": "mp",
    "cnmisuperct": "mp",
    "cnmitrialct": "mp",
}

# The first day of the Kingdom of Great Britain (the Acts of Union 1707). An English court's
# decision before it, a colonial court's included, is the Kingdom of England's.
UNION = "1707-05-01"
ENGLAND = [("england", None), ("gb", UNION)]

# Courts outside the United States in courts-db (systems "international" and "colonial"). Each
# takes the code of the country it sits in (spec section 3): the Privy Council's committees
# sat in London.
FOREIGN = {
    "kingsbench": ENGLAND,
    "highctjchuk": ENGLAND,
    "houseoflordsuk": ENGLAND,
    "privycoun": ENGLAND,
    "nhprivycounnh": ENGLAND,
    "phillipines": [("ph", None)],
}

# The sovereigns that issued a US state court's decisions, by the court's location, each with
# the first day it did. A court courts-db dates as starting on or after the last step's day
# takes only that step; any other takes them all, since courts-db's start dates for colonial
# courts are not reliable (it starts ctchansc in 1721; CAP has its decisions from 1700).
COLONIES = (
    "Connecticut", "Delaware", "Georgia", "Maine", "Maryland", "Massachusetts",
    "New Hampshire", "New Jersey", "New York", "North Carolina", "Pennsylvania",
    "Rhode Island", "South Carolina", "Virginia",
)  # fmt: skip
EARLIER = {
    **{location: [*ENGLAND, ("us", "1776-07-04")] for location in COLONIES},
    "Hawaii": [("hawaii", None), ("us", "1898-08-12")],
    "Texas": [("texas", None), ("us", "1846-02-19")],
    "Vermont": [("vermont", None), ("us", "1791-03-04")],
}


def steps(court: dict[str, Any]) -> list[tuple[str, str | None]]:
    """The court's jurisdiction codes in date order, from the first that covers its start."""
    if court["id"] in FOREIGN:
        chain = FOREIGN[court["id"]]
    elif court["id"] in TERRITORIAL:
        chain = [(TERRITORIAL[court["id"]], None)]
    elif court.get("system") == "state" and (court.get("location") or "") in EARLIER:
        chain = EARLIER[court["location"]]
    else:
        chain = [("us", None)]
    starts = [d.get("start") for d in court.get("dates") or []]
    if starts and None not in starts and min(starts) >= (chain[-1][1] or ""):
        return [(chain[-1][0], None)]
    return chain


def jurisdiction(court: dict[str, Any]) -> str:
    return steps(court)[-1][0]


def jurisdictions(court: dict[str, Any]) -> list[dict[str, str | None]] | None:
    """Date-ranged codes for a court whose decisions span a change of sovereign."""
    dated = steps(court)
    if len(dated) == 1:
        return None
    return [{"from": start, "jurisdiction": code} for code, start in dated]


# Courts courts-db lacks, as CourtListener names them (codexpublicus/exemplar#27; from 2026.10.28,
# the three CAP courts of codexpublicus/exemplar#26 that CourtListener names). Each code is
# CourtListener's court id.
MINTED = {
    "coregsalina": "Salina Register and Receiver",
    "kyctapphigh": "Court of Appeals of Kentucky (pre-1976)",
    "mdgenct": "General Court of Maryland",
    "mspb": "Merit Systems Protection Board",
    "stp": "United States Special Tribunals of Pennsylvania",
    "tennsuperct": "Tennessee Superior Court for Law and Equity",
    "tennworkcompcl": "Tennessee Court of Workers' Compensation Claims",
}

# Courts neither courts-db nor CourtListener has, for CAP courts no registry court is
# (codexpublicus/exemplar#26, ruled D154, 2026-10-28): codes this registry mints, source exemplar,
# each with its jurisdiction code (spec section 3).
EXEMPLAR = {
    "calspectrib": (
        "us",
        "California Special Tribunal (1977, McComb v. Commission on Judicial Performance)",
    ),
    "colctyctelpaso": ("us", "El Paso County District Court, Colorado"),
    "colctyctlake": ("us", "Lake County District Court, Colorado"),
    "massctyctsuff": ("england", "Suffolk County Court (Massachusetts Bay Colony)"),
    "mdctcomplbalt": ("us", "Court of Common Pleas of Baltimore City"),
    "mdoytermct": ("us", "Maryland Court of Oyer and Terminer"),
    "njdistct": (
        "us",
        "New Jersey District Courts (county and municipal district courts, 1877-1983)",
    ),
    "washterrdistct": ("us", "District Court of Washington Territory"),
}

# Other services' ids for a registered court (spec section 10.1): CourtListener's ids for the
# fifteen districts of the Court of Appeals of Texas, which courts-db registers as one court,
# and its id for the Supreme Court of the Northern Mariana Islands.
ALIASES = {
    "texapp": [f"courtlistener:txctapp{n}" for n in range(1, 16)],
    "nmi": ["courtlistener:nmariana"],
}


def build() -> dict[str, Any]:
    raw = SOURCE.read_bytes()
    source = json.loads(raw)
    courts: dict[str, Any] = {}
    excluded: dict[str, str] = {}
    for court in sorted(source, key=lambda c: c["id"]):
        if reason := exclusion(court):
            excluded[court["id"]] = reason
            continue
        entry: dict[str, Any] = {"jurisdiction": jurisdiction(court)}
        if dated := jurisdictions(court):
            entry["jurisdictions"] = dated
        entry["name"] = " ".join(court["name"].split())
        entry["profiles"] = profiles(court)
        if court["id"] in ALIASES:
            entry["aliases"] = ALIASES[court["id"]]
        entry["source"] = "courts-db"
        courts[court["id"]] = entry
    for code, name in MINTED.items():
        assert code not in courts, code
        courts[code] = {
            "jurisdiction": "us",
            "name": name,
            "profiles": [{"from": None, "profile": "printed"}],
            "source": "courtlistener",
        }
    for code, (jurisdiction_code, name) in EXEMPLAR.items():
        assert code not in courts, code
        courts[code] = {
            "jurisdiction": jurisdiction_code,
            "name": name,
            "profiles": [{"from": None, "profile": "printed"}],
            "source": "exemplar",
        }
    courts = dict(sorted(courts.items()))
    return {
        "registry": "courts",
        "version": VERSION,
        "spec": "spec/court-record-key.md",
        "spec_version": SPEC_VERSION,
        "description": (
            "Court registry for the court record key (spec section 10.1). Every court code is "
            "a courts-db id from the snapshot named in source, or, where an entry's source says "
            "courtlistener, CourtListener's id for a court courts-db lacks, or, where it says "
            "exemplar, a code this registry mints for a court neither has; the jurisdiction "
            "codes, docket profiles and aliases are this registry's assignments "
            "(registry/build_courts.py)."
        ),
        "source": {**PROVENANCE, "sha256": hashlib.sha256(raw).hexdigest()},
        "excluded": excluded,
        "courts": courts,
    }


def dumps(registry: dict[str, Any]) -> str:
    """Pretty JSON with one court per line, so a diff shows exactly the courts added."""
    head = {k: v for k, v in registry.items() if k != "courts"}
    lines = json.dumps(head, indent=2, ensure_ascii=False)[:-2].splitlines()
    lines[-1] += ","
    lines.append('  "courts": {')
    items = list(registry["courts"].items())
    for i, (code, entry) in enumerate(items):
        comma = "," if i < len(items) - 1 else ""
        lines.append(f"    {json.dumps(code)}: {json.dumps(entry, ensure_ascii=False)}{comma}")
    lines += ["  }", "}"]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    text = dumps(build())
    if "--check" in argv:
        if OUTPUT.read_text(encoding="utf-8") != text:
            print(f"{OUTPUT.relative_to(ROOT)} is out of date; run registry/build_courts.py")
            return 1
        return 0
    OUTPUT.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
