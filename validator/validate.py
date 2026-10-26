# SPDX-FileCopyrightText: Copyright (c) 2026 <COPYRIGHT HOLDER>
# SPDX-License-Identifier: BSD-3-Clause

"""Reference validator for exemplar documents and viewer sidecars.

An Akoma Ntoso document (*.akn.xml) is checked against the vendored Akoma Ntoso 1.0 XML Schema
and then, if it is schema-valid, against the profile's Schematron rules (schema/profile.sch).
A viewer sidecar (*.sidecar.json) is checked against schema/sidecar.schema.json and, when the
document it indexes sits beside it under the same stem, against that document.

Usage:
    uv run python validator/validate.py [PATH ...]

Each PATH is a file or a directory searched recursively; the default is examples/ and
vectors/akn-profile/. Exits 1 if anything fails, and prints one line per finding: the file, the
rule id and the message.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from lxml import etree
from saxonche import PySaxonProcessor

ROOT = Path(__file__).resolve().parent.parent
XSD = ROOT / "schema" / "akn" / "1.0" / "akomantoso30.xsd"
SCHEMATRON = ROOT / "schema" / "profile.sch"
SIDECAR_SCHEMA = ROOT / "schema" / "sidecar.schema.json"
TRANSPILER = ROOT / "validator" / "vendor" / "schxslt2" / "transpile.xsl"

AKN = "http://docs.oasis-open.org/legaldocml/ns/akn/3.0"
CX = "https://codexpublicus.org/ns/exemplar"
NS = {"a": AKN, "cx": CX}
SVRL = {"svrl": "http://purl.oclc.org/dsdl/svrl"}
LABEL = re.compile(r"^\[([^\]]+)\]\s*")

# Rule ids for findings that don't come from the Schematron.
XSD_RULE = "AKN-1"
SIDECAR_SCHEMA_RULE = "sidecar-schema"
SIDECAR_DOCUMENT_RULE = "sidecar-document"


@dataclass(frozen=True)
class Finding:
    rule: str
    message: str
    location: str = ""


@cache
def _saxon() -> PySaxonProcessor:
    return PySaxonProcessor(license=False)


@cache
def _schematron() -> Any:
    """The profile's Schematron, transpiled to XSLT by SchXslt2 and compiled."""
    xslt = _saxon().new_xslt30_processor()
    transpiler = xslt.compile_stylesheet(stylesheet_file=str(TRANSPILER))
    validation = transpiler.transform_to_string(source_file=str(SCHEMATRON))
    return xslt.compile_stylesheet(stylesheet_text=validation)


@cache
def _xsd() -> etree.XMLSchema:
    return etree.XMLSchema(etree.parse(str(XSD)))


@cache
def _sidecar_schema() -> Draft202012Validator:
    schema = json.loads(SIDECAR_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def schematron_findings(doc: etree._ElementTree) -> list[Finding]:
    """Run schema/profile.sch over doc and return its failed assertions and reports."""
    source = _saxon().parse_xml(xml_text=etree.tostring(doc, encoding="unicode"))
    report = etree.fromstring(_schematron().transform_to_string(xdm_node=source).encode("utf-8"))
    findings = []
    for node in report.xpath("//svrl:failed-assert | //svrl:successful-report", namespaces=SVRL):
        text = " ".join("".join(node.itertext()).split())
        m = LABEL.match(text)
        rule = m.group(1) if m else node.get("id", "schematron")
        findings.append(Finding(rule, text[m.end() :] if m else text, node.get("location", "")))
    return findings


def check_document(doc: etree._ElementTree) -> list[Finding]:
    """XSD first; the Schematron rules only run on a schema-valid document."""
    xsd = _xsd()
    if not xsd.validate(doc):
        return [Finding(XSD_RULE, f"line {e.line}: {e.message}") for e in xsd.error_log]
    return schematron_findings(doc)


# The viewer sidecar (profile section 16.3).


def _nearest_eid(element: etree._Element) -> str | None:
    for node in element.iterancestors():
        if node.get("eId"):
            return node.get("eId")
    return None


def derive_sidecar(doc: etree._ElementTree) -> dict[str, Any]:
    """Every sidecar field the document determines; blocks maps each block id to None.

    The bounding boxes are the one thing a sidecar holds that the document lacks.
    """

    def value(path: str) -> str:
        return doc.xpath(f"string({path})", namespaces=NS)

    parts = []
    for hc in doc.xpath(
        "//a:judgmentBody/*[self::a:motivation or self::a:decision]/a:hcontainer", namespaces=NS
    ):
        parts.append(
            {
                "eId": hc.get("eId"),
                "key": hc.get(f"{{{CX}}}part"),
                "role": hc.get("name"),
                "authors": hc.get(f"{{{CX}}}authors", "").split(),
            }
        )

    printings = []
    for ref in doc.xpath("//a:references/a:TLCReference[@name='printing']", namespaces=NS):
        eid = ref.get("eId")
        records = doc.xpath(f"//cx:printing[@ref='#{eid}']", namespaces=NS)
        record = records[0] if records else etree.Element("missing")
        pages = []
        for eop in doc.xpath(f"//a:eop[@refersTo='#{eid}']", namespaces=NS):
            page: dict[str, Any] = {"number": eop.get("number"), "eId": _nearest_eid(eop)}
            if (scan := eop.get(f"{{{CX}}}scan")) is not None:
                page["scan"] = int(scan)
            pages.append(page)
        printing: dict[str, Any] = {
            "ref": eid,
            "citation": ref.get("showAs"),
            "type": record.get("type"),
            "firstPage": record.get("firstPage"),
        }
        if record.get("lastPage") is not None:
            printing["lastPage"] = record.get("lastPage")
        printing.update(text=record.get("text"), pages=pages)
        printings.append(printing)

    blocks: dict[str, None] = {}
    for tokens in doc.xpath("//@cx:blocks", namespaces=NS):
        blocks.update(dict.fromkeys(tokens.split()))

    return {
        "profile": value("//a:proprietary/cx:profile/@version"),
        "document": value("//a:FRBRManifestation/a:FRBRthis/@value"),
        "work": value("//a:FRBRWork/a:FRBRthis/@value"),
        "expression": value("//a:FRBRExpression/a:FRBRthis/@value"),
        "parts": parts,
        "printings": printings,
        "blocks": blocks,
    }


def check_sidecar(sidecar: Any, doc: etree._ElementTree | None = None) -> list[Finding]:
    """JSON Schema first; then, given its document, that the sidecar agrees with it."""
    errors = sorted(_sidecar_schema().iter_errors(sidecar), key=lambda e: list(e.absolute_path))
    if errors:
        return [
            Finding(SIDECAR_SCHEMA_RULE, e.message, "/" + "/".join(map(str, e.absolute_path)))
            for e in errors
        ]
    if doc is None:
        return []
    findings = []
    derived = derive_sidecar(doc)
    for field in ("profile", "document", "work", "expression", "parts", "printings"):
        if sidecar[field] != derived[field]:
            findings.append(
                Finding(
                    SIDECAR_DOCUMENT_RULE,
                    f"{field} is {json.dumps(sidecar[field])}; the document gives "
                    f"{json.dumps(derived[field])}",
                    "/" + field,
                )
            )
    missing = sorted(set(derived["blocks"]) - set(sidecar["blocks"]))
    extra = sorted(set(sidecar["blocks"]) - set(derived["blocks"]))
    if missing:
        findings.append(
            Finding(SIDECAR_DOCUMENT_RULE, f"no entry for block ids {missing}", "/blocks")
        )
    if extra:
        findings.append(
            Finding(SIDECAR_DOCUMENT_RULE, f"block ids {extra} are not in the document", "/blocks")
        )
    return findings


def sidecar_document(path: Path) -> Path:
    """The document a sidecar file indexes: the *.akn.xml beside it with the same stem."""
    return path.with_name(path.name.removesuffix(".sidecar.json") + ".akn.xml")


def validate_file(path: Path) -> list[Finding]:
    if path.name.endswith(".akn.xml"):
        return check_document(etree.parse(str(path)))
    if path.name.endswith(".sidecar.json"):
        sidecar = json.loads(path.read_text(encoding="utf-8"))
        doc_path = sidecar_document(path)
        doc = etree.parse(str(doc_path)) if doc_path.exists() else None
        return check_sidecar(sidecar, doc)
    raise ValueError(f"{path}: not an .akn.xml document or a .sidecar.json sidecar")


def collect(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files += sorted(path.rglob("*.akn.xml")) + sorted(path.rglob("*.sidecar.json"))
        else:
            files.append(path)
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "paths", nargs="*", type=Path, default=[ROOT / "examples", ROOT / "vectors" / "akn-profile"]
    )
    args = parser.parse_args(argv)
    if missing := [p for p in args.paths if not p.exists()]:
        print(f"no such file or directory: {', '.join(map(str, missing))}", file=sys.stderr)
        return 1
    files = collect(args.paths)
    if not files:
        print("no .akn.xml or .sidecar.json files found", file=sys.stderr)
        return 1
    failed = 0
    for path in files:
        findings = validate_file(path)
        failed += bool(findings)
        for f in findings:
            where = f" ({f.location})" if f.location else ""
            print(f"{path}: [{f.rule}] {f.message}{where}")
    print(f"{len(files) - failed} of {len(files)} files valid", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
