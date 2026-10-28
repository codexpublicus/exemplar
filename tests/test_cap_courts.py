# SPDX-FileCopyrightText: Copyright (c) 2026 Codex Publicus contributors
# SPDX-License-Identifier: BSD-3-Clause

"""Check registry/cap-courts.json: its schema, and that every code it gives is registered."""

import json
from pathlib import Path
from typing import Any

import jsonschema

from tests.crk_check import period

ROOT = Path(__file__).resolve().parent.parent
TABLE: dict[str, Any] = json.loads((ROOT / "registry" / "cap-courts.json").read_text("utf-8"))
SCHEMA = json.loads((ROOT / "schema" / "cap-courts.schema.json").read_text("utf-8"))
REGISTRY = json.loads((ROOT / "registry" / "courts.json").read_text("utf-8"))


def test_matches_schema() -> None:
    jsonschema.Draft202012Validator.check_schema(SCHEMA)
    errors = list(jsonschema.Draft202012Validator(SCHEMA).iter_errors(TABLE))
    assert not errors, [f"{list(e.path)}: {e.message}" for e in errors[:5]]


def test_pins_this_registry_and_spec() -> None:
    assert TABLE["courts_registry_version"] == REGISTRY["version"]
    assert TABLE["spec_version"] == REGISTRY["spec_version"]


def test_every_code_is_registered_and_in_date_order() -> None:
    for cap_id, entry in TABLE["courts"].items():
        codes = entry["codes"]
        assert codes[0]["from"] is None, cap_id
        starts = [c["from"] for c in codes[1:]]
        assert starts == sorted(set(starts)), cap_id
        for step in codes:
            assert step["code"] in REGISTRY["courts"], (cap_id, step["code"])
        assert entry["basis"] in TABLE["bases"], cap_id


def test_generic_federal_codes_are_marked_or_ruled() -> None:
    """D105: CourtListener's generic usdistct and uscirct are never minted on unreviewed. D154
    (codexpublicus/exemplar#26 question 8): a CAP court that holds several federal districts
    within the same dates keeps the generic code without the mark, with a note saying why."""
    for cap_id, entry in TABLE["courts"].items():
        generic = {s["code"] for s in entry["codes"]} & {"usdistct", "uscirct"}
        if generic and not entry.get("review"):
            assert entry["basis"] == "head-matter", cap_id
            assert "generic" in entry["note"], cap_id
        elif generic:
            assert entry["review_reason"], cap_id


def test_reporter_registry() -> None:
    """registry/reporters.json: its schema, its pins, and that its courts are registered."""
    schema = json.loads((ROOT / "schema" / "reporters.schema.json").read_text("utf-8"))
    reporters = json.loads((ROOT / "registry" / "reporters.json").read_text("utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(reporters))
    assert not errors, [f"{list(e.path)}: {e.message}" for e in errors[:5]]
    assert reporters["courts_registry_version"] == REGISTRY["version"]
    assert reporters["version"] == REGISTRY["version"]
    assert reporters["spec_version"] == REGISTRY["spec_version"]
    for code in reporters["official"]:
        assert code in REGISTRY["courts"], code
    for edition in reporters["editions"]:
        assert edition["court"] in REGISTRY["courts"], edition
    for name, volumes in reporters["supreme_court_volumes"]["reporters"].items():
        for volume, span in volumes.items():
            assert period(span["first"])[0] <= period(span["last"])[1], (name, volume)


def test_a_court_is_mapped_or_unmapped_never_both() -> None:
    assert not set(TABLE["courts"]) & set(TABLE["unmapped"])
