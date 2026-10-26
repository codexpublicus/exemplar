# SPDX-FileCopyrightText: Copyright (c) 2026 <COPYRIGHT HOLDER>
# SPDX-License-Identifier: BSD-3-Clause

"""Check the examples built from Caselaw Access Project data (examples/cap).

The documents and sidecars themselves are checked like every other example, by
test_akn_profile.py and the reference validator. These checks cover what is particular to them:
their sources are the pinned files, the build reproduces them byte for byte, and their keys are
the ones tests/crk_check.py computes from the CAP case's own fields.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from lxml import etree

from tests import crk_check

ROOT = Path(__file__).resolve().parent.parent
CAP = ROOT / "examples" / "cap"
MANIFEST = json.loads((CAP / "manifest.json").read_text(encoding="utf-8"))
COURTS = json.loads((ROOT / "registry" / "courts.json").read_text(encoding="utf-8"))["courts"]
JUDGES = json.loads((CAP / "judges.json").read_text(encoding="utf-8"))["judges"]
ENTRIES = MANIFEST["examples"]

AKN = "http://docs.oasis-open.org/legaldocml/ns/akn/3.0"
CX = "https://codexpublicus.org/ns/exemplar"
NS = {"a": AKN, "cx": CX}


def ids(entries: list[dict[str, Any]]) -> list[str]:
    return [e["cap"] for e in entries]


def source(entry: dict[str, Any], kind: str) -> Path:
    reporter, volume, name = entry["cap"].split("/")
    sub, ext = ("cases", "json") if kind == "json" else ("html", "html")
    return CAP / "source" / reporter / volume / sub / f"{name}.{ext}"


def document(entry: dict[str, Any]) -> Path:
    return CAP / (entry["key"].replace("/", "-") + ".akn.xml")


@pytest.mark.parametrize("entry", ENTRIES, ids=ids(ENTRIES))
def test_sources_match_their_pins(entry: dict[str, Any]) -> None:
    for kind in ("json", "html"):
        info = entry["source"][kind]
        reporter, volume, _ = entry["cap"].split("/")
        assert info["url"].startswith(f"https://static.case.law/{reporter}/{volume}/")
        digest = hashlib.sha256(source(entry, kind).read_bytes()).hexdigest()
        assert digest == info["sha256"]


def test_build_reproduces_the_examples() -> None:
    from examples.cap import build

    assert build.main(["--check"]) == 0


def test_cap_judges_list_no_letter_case_variants() -> None:
    for slug, entry in JUDGES.items():
        names = [entry["name"]] + [f["form"] for f in entry.get("printed", [])]
        assert len({n.casefold() for n in names}) == len(names), slug


def test_fallback_ordinal_from_volume_records() -> None:
    """CRK 5.6 from CAP's case list: Glover, printed second on 500 Pa. 524 after the docketed
    Kibler and decided the same day, takes ~2 (the compute vector rpt-fallback-mixed-page)."""
    from examples.cap import build

    volumes = build.Volumes(json.loads(build.LOCK.read_text(encoding="utf-8")))
    page = volumes.records("pa", "500").page("524")
    keys = [build.decision_key(c, "pa", COURTS, page).key for c in page]
    vector = next(
        json.loads(line)
        for line in (ROOT / "vectors" / "court-record-key" / "compute.jsonl").open()
        if '"rpt-fallback-mixed-page"' in line
    )
    assert keys == ["us/pa/petitionno.216w.d.alloc.dkt.1982/1983-04-27", vector["key"]]


def test_every_cap_document_is_in_the_manifest() -> None:
    built = sorted(CAP.glob("*.akn.xml"))
    assert built == sorted(document(e) for e in ENTRIES)


@pytest.mark.parametrize("entry", ENTRIES, ids=ids(ENTRIES))
def test_keys_follow_from_cap_fields(entry: dict[str, Any]) -> None:
    case = json.loads(source(entry, "json").read_text(encoding="utf-8"))
    official = next(c["cite"] for c in case["citations"] if c["type"] == "official")
    volume, reporter, page = official.split(" ", 1)[0], *official.split(" ", 1)[1].rsplit(" ", 1)
    facts = {
        "jurisdiction": "us",
        "court": MANIFEST["courts"][case["court"]["name"]],
        "docket": case["docket_number"] or None,
        "decided": case["decision_date"],
        "reporter_citation": {"volume": volume, "reporter": reporter, "page": page},
    }
    work = crk_check.compute(facts, COURTS, JUDGES)
    assert work == entry["key"]
    doc = etree.parse(str(document(entry)))
    assert doc.xpath("string(//a:FRBRWork/a:FRBRthis/@value)", namespaces=NS) == "crk:" + work
    for hc in doc.xpath("//a:hcontainer[@cx:part]", namespaces=NS):
        authors = hc.get(f"{{{CX}}}authors", "").split()
        part = crk_check.compute(dict(facts, role=hc.get("name"), authors=authors), COURTS, JUDGES)
        assert part == hc.get(f"{{{CX}}}part")
