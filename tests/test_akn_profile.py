"""Check the Akoma Ntoso examples against the vendored schema and spec/akoma-ntoso-profile.md.

The profile's own rules (Schematron) are checked in test_profile_rules.py; these checks cover
the base schema, the vendored schema's pins, and the keys the examples carry.
"""

import hashlib
import json
import re
from functools import cache
from pathlib import Path
from typing import Any

import pytest
from lxml import etree

from tests import crk_check

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "spec" / "akoma-ntoso-profile.md"
XSD_DIR = ROOT / "schema" / "akn" / "1.0"
SOURCE = json.loads((XSD_DIR / "source.json").read_text(encoding="utf-8"))
COURTS = json.loads((ROOT / "registry" / "courts.json").read_text(encoding="utf-8"))["courts"]
MINIMAL = ROOT / "examples" / "minimal" / "us-dc-57-1943-04-06.akn.xml"
MINIMAL_JUDGES = json.loads(
    (ROOT / "examples" / "minimal" / "judges.json").read_text(encoding="utf-8")
)["judges"]

AKN = "http://docs.oasis-open.org/legaldocml/ns/akn/3.0"
CX = "https://codexpublicus.org/ns/exemplar"
NS = {"a": AKN, "cx": CX}

EXAMPLES = sorted(ROOT.glob("examples/**/*.akn.xml"))


@cache
def schema() -> etree.XMLSchema:
    return etree.XMLSchema(etree.parse(str(XSD_DIR / "akomantoso30.xsd")))


def ids(paths: list[Path]) -> list[str]:
    return [str(p.relative_to(ROOT)) for p in paths]


def one(doc: etree._ElementTree, path: str) -> Any:
    (found,) = doc.xpath(path, namespaces=NS)
    return found


def spec_version() -> str:
    text = SPEC.read_text("utf-8")
    m = re.search(r"^Specification version: \*\*([0-9]+\.[0-9]+\.[0-9]+)\*\*", text, re.M)
    assert m
    return m.group(1)


@pytest.mark.parametrize("name", sorted(SOURCE["files"]))
def test_vendored_schema_matches_pin(name: str) -> None:
    digest = hashlib.sha256((XSD_DIR / name).read_bytes()).hexdigest()
    assert digest == SOURCE["files"][name]["sha256"]


def test_schema_rejects_a_judgment_without_header() -> None:
    doc = etree.parse(str(MINIMAL))
    header = one(doc, "//a:header")
    header.getparent().remove(header)
    assert not schema().validate(doc)


def test_there_are_examples() -> None:
    assert MINIMAL in EXAMPLES


@pytest.mark.parametrize("path", EXAMPLES, ids=ids(EXAMPLES))
def test_example_is_valid_akoma_ntoso(path: Path) -> None:
    doc = etree.parse(str(path))
    assert schema().validate(doc), str(schema().error_log)


@pytest.mark.parametrize("path", EXAMPLES, ids=ids(EXAMPLES))
def test_example_declares_this_profile_version(path: Path) -> None:
    doc = etree.parse(str(path))
    assert one(doc, "//a:proprietary/cx:profile/@version") == spec_version()


@pytest.mark.parametrize("path", EXAMPLES, ids=ids(EXAMPLES))
def test_frbr_uris_are_court_record_keys(path: Path) -> None:
    doc = etree.parse(str(path))
    work = one(doc, "//a:FRBRWork/a:FRBRuri/@value")
    assert one(doc, "//a:FRBRWork/a:FRBRthis/@value") == work
    assert crk_check.classify(work) is None
    parts = crk_check.parse(work)
    assert parts["role"] is None and parts["revised"] is None, "work URI is a decision key"

    expression = one(doc, "//a:FRBRExpression/a:FRBRuri/@value")
    assert one(doc, "//a:FRBRExpression/a:FRBRthis/@value") == expression
    assert crk_check.classify(expression) is None
    expr_parts = crk_check.parse(expression)
    assert expr_parts["role"] is None
    assert crk_check.decision_key(expr_parts) == work
    contains = one(doc, "/a:akomaNtoso/a:judgment/@contains")
    assert contains == ("singleVersion" if expr_parts["revised"] else "originalVersion")

    manifestation = one(doc, "//a:FRBRManifestation/a:FRBRuri/@value")
    assert manifestation == expression + ".akn.xml"


@pytest.mark.parametrize("path", EXAMPLES, ids=ids(EXAMPLES))
def test_parts_carry_their_keys(path: Path) -> None:
    doc = etree.parse(str(path))
    work = one(doc, "//a:FRBRWork/a:FRBRuri/@value")
    containers = doc.xpath("//a:judgmentBody//a:hcontainer[@cx:part]", namespaces=NS)
    assert containers
    for hc in containers:
        key = hc.get(f"{{{CX}}}part")
        assert crk_check.classify(key) is None, key
        parts = crk_check.parse(key)
        assert crk_check.decision_key(parts) == work
        assert hc.get("name") == parts["role"]
        assert hc.get("eId") == "opinion_" + key[len(work) + 1 :]
        assert hc.get(f"{{{CX}}}authors", "").split() == parts["authors"]


@pytest.mark.parametrize("path", EXAMPLES, ids=ids(EXAMPLES))
def test_page_markers_reference_printings(path: Path) -> None:
    doc = etree.parse(str(path))
    printings = {
        "#" + e for e in doc.xpath("//a:TLCReference[@name='printing']/@eId", namespaces=NS)
    }
    markers = doc.xpath("//a:eop | //a:eol", namespaces=NS)
    for marker in markers:
        assert marker.get("refersTo") in printings


@pytest.mark.parametrize("path", EXAMPLES, ids=ids(EXAMPLES))
def test_refs_have_targets(path: Path) -> None:
    doc = etree.parse(str(path))
    for ref in doc.xpath("//a:ref", namespaces=NS):
        assert ref.get("href")


def test_minimal_example_keys_follow_from_printed_facts() -> None:
    doc = etree.parse(str(MINIMAL))
    court = one(doc, "//a:TLCOrganization[starts-with(@eId, 'court_')]/@eId")[len("court_") :]
    facts = {
        "country": "us",
        "court": court,
        "docket": doc.xpath("string(//a:header//a:docketNumber)", namespaces=NS),
        "decided": one(doc, "//a:header//a:docDate/@date"),
    }
    work = crk_check.compute(facts, COURTS, MINIMAL_JUDGES)
    assert work == one(doc, "//a:FRBRWork/a:FRBRuri/@value")
    for hc in doc.xpath("//a:hcontainer[@cx:part]", namespaces=NS):
        part_facts = dict(
            facts, role=hc.get("name"), authors=hc.get(f"{{{CX}}}authors", "").split()
        )
        assert crk_check.compute(part_facts, COURTS, MINIMAL_JUDGES) == hc.get(f"{{{CX}}}part")


def test_spec_quotes_the_minimal_example_verbatim() -> None:
    blocks = re.findall(r"^```xml\n(.*?)^```", SPEC.read_text("utf-8"), re.M | re.S)
    quoted = [b for b in blocks if b.startswith("<?xml")]
    assert len(quoted) == 1
    assert quoted[0] == MINIMAL.read_text("utf-8")
