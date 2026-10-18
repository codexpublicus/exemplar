"""Check schema/profile.sch, schema/sidecar.schema.json and the reference validator.

The document vectors in vectors/akn-profile/documents.jsonl each edit a base document and name
the rules the result breaks; the sidecar vectors in sidecars.jsonl do the same for a sidecar
with a JSON Patch. Every vector must fail exactly the rules it names, no more and no fewer.
"""

import copy
import hashlib
import json
import re
from functools import cache
from pathlib import Path
from typing import Any

import pytest
from lxml import etree

from tests import crk_check
from validator import validate

ROOT = Path(__file__).resolve().parent.parent
VECTORS = ROOT / "vectors" / "akn-profile"
CRK_VECTORS = ROOT / "vectors" / "court-record-key"
SCHXSLT = ROOT / "validator" / "vendor" / "schxslt2"
CRK_SPEC = ROOT / "spec" / "court-record-key.md"
PROFILE_SPEC = ROOT / "spec" / "akoma-ntoso-profile.md"
SCHEMATRON = ROOT / "schema" / "profile.sch"

NS = validate.NS
XSL = "http://www.w3.org/1999/XSL/Transform"
SCH = "http://purl.oclc.org/dsdl/schematron"
FUNCTIONS = "https://codexpublicus.org/ns/exemplar/functions"
PROVENANCE = {"human-curated", "hand-checked", "engine-output", "spec-derived"}


def jsonl(path: Path) -> list[dict[str, Any]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


DOCUMENTS = jsonl(VECTORS / "documents.jsonl")
SIDECARS = jsonl(VECTORS / "sidecars.jsonl")
MANIFEST = json.loads((VECTORS / "manifest.json").read_text(encoding="utf-8"))
SCHXSLT_SOURCE = json.loads((SCHXSLT / "source.json").read_text(encoding="utf-8"))


# Applying the vectors' edits.


def _fragment(xml: str) -> list[etree._Element]:
    wrapper = etree.fromstring(
        f'<wrapper xmlns="{validate.AKN}" xmlns:cx="{validate.CX}">{xml}</wrapper>'
    )
    return list(wrapper)


def _attr(name: str) -> str:
    prefix, _, local = name.rpartition(":")
    return f"{{{NS[prefix]}}}{local}" if prefix else local


def apply_ops(doc: etree._ElementTree, ops: list[dict[str, Any]]) -> etree._ElementTree:
    doc = copy.deepcopy(doc)
    for op in ops:
        targets = doc.xpath(op["xpath"], namespaces=NS)
        assert targets, f"{op['xpath']} matches nothing"
        for target in targets:
            match op["op"]:
                case "set":
                    target.set(_attr(op["attr"]), op["value"])
                case "unset":
                    del target.attrib[_attr(op["attr"])]
                case "remove":
                    target.getparent().remove(target)
                case "append":
                    target.extend(_fragment(op["xml"]))
                case "after":
                    for node in reversed(_fragment(op["xml"])):
                        target.addnext(node)
                case other:
                    raise ValueError(f"unknown op {other}")
    return doc


def apply_patch(value: Any, patch: list[dict[str, Any]]) -> Any:
    """RFC 6902 add, remove and replace: the operations the sidecar vectors use."""
    value = copy.deepcopy(value)
    for op in patch:
        *parents, last = [
            p.replace("~1", "/").replace("~0", "~") for p in op["path"].split("/")[1:]
        ]
        node = value
        for p in parents:
            node = node[int(p)] if isinstance(node, list) else node[p]
        key: Any = (len(node) if last == "-" else int(last)) if isinstance(node, list) else last
        match op["op"]:
            case "add" if isinstance(node, list):
                node.insert(key, op["value"])
            case "add" | "replace":
                node[key] = op["value"]
            case "remove":
                del node[key]
            case other:
                raise ValueError(f"unknown op {other}")
    return value


@cache
def base_document(path: str) -> etree._ElementTree:
    return etree.parse(str(ROOT / path))


def rules(findings: list[validate.Finding]) -> list[str]:
    return sorted({f.rule for f in findings})


# The vendored transpiler.


@pytest.mark.parametrize("name", sorted(SCHXSLT_SOURCE["files"]))
def test_vendored_transpiler_matches_pin(name: str) -> None:
    digest = hashlib.sha256((SCHXSLT / name).read_bytes()).hexdigest()
    assert digest == SCHXSLT_SOURCE["files"][name]["sha256"]


# The Schematron against the specs.


def test_schematron_uses_the_crk_regex_verbatim() -> None:
    (spec_regex,) = re.findall(r"^```regex\n(.*?)\n^```", CRK_SPEC.read_text("utf-8"), re.M | re.S)
    tree = etree.parse(str(SCHEMATRON))
    (select,) = tree.xpath(
        "//xsl:function[@name='f:crk-regex']/xsl:sequence/@select",
        namespaces={"xsl": XSL},
    )
    assert select == f"'{spec_regex}'"


def test_schematron_covers_every_rule_the_profile_assigns_it() -> None:
    table = PROFILE_SPEC.read_text("utf-8").split("### 16.2", 1)[1].split("### 16.3", 1)[0]
    assigned = set()
    for row in table.splitlines():
        cells = [c.strip() for c in row.strip("|").split("|")]
        if len(cells) == 3 and "Schematron" in cells[2]:
            for item in cells[0].split(","):
                ids = [int(n) for n in re.findall(r"AKN-(\d+)", item)]
                assigned |= {f"AKN-{n}" for n in range(ids[0], ids[-1] + 1)}
    text = SCHEMATRON.read_text("utf-8")
    checked = set(re.findall(r"\[(AKN-\d+)\]", text))
    # Assigned to Schematron by a range in the table but not checkable on their own: AKN-28
    # (parts in printed order) and AKN-45 (an eop sits where the page begins). AKN-53 is
    # covered by AKN-51: legislation stays unmarked, so every ref must target a decision.
    assert assigned - checked <= {"AKN-28", "AKN-45", "AKN-53"}
    assert checked <= assigned | {"AKN-1"}


def test_every_profile_rule_is_exercised_by_a_vector() -> None:
    text = SCHEMATRON.read_text("utf-8")
    checked = set(re.findall(r">\[((?:AKN-)?[0-9][0-9.]*)\]", text))
    exercised = {rule for v in DOCUMENTS for rule in v["expect"]}
    assert checked - exercised == set()


# Key and alias functions against the court record key vectors.


@cache
def _functions() -> Any:
    """The Schematron's xsl:functions, wrapped in a stylesheet that applies f:is-key,
    f:alias-scheme and f:is-key(f:key-of-uri(.)) to each line of its input."""
    tree = etree.parse(str(SCHEMATRON))
    functions = "".join(
        etree.tostring(f, encoding="unicode")
        for f in tree.xpath("/sch:schema/xsl:function", namespaces={"sch": SCH, "xsl": XSL})
    )
    stylesheet = f"""<xsl:stylesheet version="2.0" xmlns:xsl="{XSL}"
        xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:f="{FUNCTIONS}"
        xmlns:a="{validate.AKN}" exclude-result-prefixes="#all">
      <xsl:output method="text"/>
      {functions}
      <xsl:template match="/">
        <xsl:for-each select="/strings/s">
          <xsl:value-of select="f:is-key(string(.)), f:alias-scheme(string(.)),
            f:is-key(f:key-of-uri(string(.)))" separator="|"/>
          <xsl:text>&#10;</xsl:text>
        </xsl:for-each>
      </xsl:template>
    </xsl:stylesheet>"""
    processor = validate._saxon().new_xslt30_processor()
    return processor.compile_stylesheet(stylesheet_text=stylesheet)


def evaluate(strings: list[str]) -> list[tuple[bool, str]]:
    return [(is_key, scheme) for is_key, scheme, _ in evaluate_all(strings)]


def evaluate_all(strings: list[str]) -> list[tuple[bool, str, bool]]:
    root = etree.Element("strings")
    for s in strings:
        etree.SubElement(root, "s").text = s
    node = validate._saxon().parse_xml(xml_text=etree.tostring(root, encoding="unicode"))
    out = _functions().transform_to_string(xdm_node=node)
    results = []
    for line in out.splitlines():
        is_key, scheme, is_reference = line.split("|")
        results.append((is_key == "true", scheme, is_reference == "true"))
    assert len(results) == len(strings)
    return results


def test_is_key_accepts_every_parse_vector() -> None:
    keys = [v["key"] for v in jsonl(CRK_VECTORS / "parse.jsonl")]
    assert [k for k, (ok, _) in zip(keys, evaluate(keys), strict=True) if not ok] == []


def test_is_key_rejects_every_reject_vector() -> None:
    keys = [v["key"] for v in jsonl(CRK_VECTORS / "reject.jsonl")]
    assert [k for k, (ok, _) in zip(keys, evaluate(keys), strict=True) if ok] == []


def test_is_key_agrees_with_the_crk_reading_on_computed_keys() -> None:
    keys = [v["key"] for v in jsonl(CRK_VECTORS / "compute.jsonl") if "key" in v]
    for key, (ok, _) in zip(keys, evaluate(keys), strict=True):
        assert ok == (crk_check.classify(key) is None), key


def test_alias_scheme_recognizes_every_alias_vector() -> None:
    vectors = [v for v in jsonl(CRK_VECTORS / "alias.jsonl") if v["scheme"] != "crk"]
    results = evaluate([v["alias"] for v in vectors])
    for v, (_, scheme) in zip(vectors, results, strict=True):
        assert scheme == v["scheme"], v["alias"]


def test_key_shaped_aliases_are_key_references() -> None:
    vectors = [v for v in jsonl(CRK_VECTORS / "alias.jsonl") if v["scheme"] == "crk"]
    assert vectors
    results = evaluate_all([v["alias"] for v in vectors])
    for v, (is_key, scheme, is_reference) in zip(vectors, results, strict=True):
        assert is_reference and not is_key and scheme == "", v["alias"]


def test_key_of_uri_reads_only_key_references() -> None:
    keys = [v["key"] for v in jsonl(CRK_VECTORS / "parse.jsonl")]
    results = evaluate_all(keys + ["crk:" + k for k in keys] + ["CRK:" + k for k in keys])
    n = len(keys)
    assert [r[2] for r in results[:n]] == [False] * n, "a bare key is not a key reference"
    assert [r[2] for r in results[n : 2 * n]] == [True] * n
    assert [r[2] for r in results[2 * n :]] == [False] * n, "the scheme name is lowercase"


# The document vectors.


def test_vector_files_are_described_in_the_manifest() -> None:
    files = {p.name for p in VECTORS.iterdir() if p.suffix in {".jsonl", ".xml", ".json"}}
    assert files - {"manifest.json"} == set(MANIFEST["files"])


@pytest.mark.parametrize("vector", DOCUMENTS, ids=[v["id"] for v in DOCUMENTS])
def test_document_vector(vector: dict[str, Any]) -> None:
    assert vector["provenance"] in PROVENANCE
    assert vector["expect"] == sorted(set(vector["expect"]))
    doc = apply_ops(base_document(vector["base"]), vector["ops"])
    findings = validate.check_document(doc)
    assert rules(findings) == vector["expect"], "\n".join(map(str, findings))


def test_document_vector_ids_are_unique() -> None:
    ids = [v["id"] for v in DOCUMENTS]
    assert len(ids) == len(set(ids))


# The sidecar vectors.


@pytest.mark.parametrize("vector", SIDECARS, ids=[v["id"] for v in SIDECARS])
def test_sidecar_vector(vector: dict[str, Any]) -> None:
    assert vector["provenance"] in PROVENANCE
    sidecar = json.loads((ROOT / vector["base"]).read_text(encoding="utf-8"))
    sidecar = apply_patch(sidecar, vector["patch"])
    doc = base_document(vector["document"]) if vector["document"] else None
    if doc is not None and vector.get("ops"):
        doc = apply_ops(doc, vector["ops"])
    assert rules(validate.check_sidecar(sidecar, doc)) == vector["expect"]


def test_sidecar_vector_ids_are_unique() -> None:
    ids = [v["id"] for v in SIDECARS]
    assert len(ids) == len(set(ids))


# The validator over the published files.


def test_every_example_document_has_a_sidecar() -> None:
    for path in ROOT.glob("examples/**/*.akn.xml"):
        assert path.with_name(path.name.removesuffix(".akn.xml") + ".sidecar.json").exists()


def test_validator_passes_examples_and_vector_bases() -> None:
    assert validate.main([str(ROOT / "examples"), str(VECTORS)]) == 0


def test_validator_fails_a_bad_document(tmp_path: Path) -> None:
    doc = apply_ops(base_document(DOCUMENTS[0]["base"]), [{"op": "remove", "xpath": "//a:header"}])
    path = tmp_path / "bad.akn.xml"
    doc.write(str(path))
    assert validate.main([str(path)]) == 1
