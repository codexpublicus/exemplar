# SPDX-FileCopyrightText: Copyright (c) 2026 Codex Publicus contributors
# SPDX-License-Identifier: BSD-3-Clause

"""Check registry/reporter-variants.json: its schema, its source pin, and that it is the build."""

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import jsonschema

from tests import crk_check

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "registry" / "reporter-variants.json"
REGISTRY: dict[str, Any] = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
SCHEMA = json.loads((ROOT / "schema" / "reporter-variants.schema.json").read_text("utf-8"))
COURTS = json.loads((ROOT / "registry" / "courts.json").read_text(encoding="utf-8"))
SPEC = (ROOT / "spec" / "court-record-key.md").read_text(encoding="utf-8")


def _builder() -> Any:
    spec = importlib.util.spec_from_file_location(
        "build_reporter_variants", ROOT / "registry" / "build_reporter_variants.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_matches_schema() -> None:
    jsonschema.Draft202012Validator.check_schema(SCHEMA)
    errors = list(jsonschema.Draft202012Validator(SCHEMA).iter_errors(REGISTRY))
    assert not errors, [f"{list(e.path)}: {e.message}" for e in errors[:5]]


def test_vendored_source_matches_its_pin() -> None:
    source = REGISTRY["source"]
    vendored = ROOT / source["vendored_copy"]
    assert hashlib.sha256(vendored.read_bytes()).hexdigest() == source["sha256"]
    assert (vendored.parent / "LICENSE").is_file()


def test_registry_is_the_build_of_the_vendored_source() -> None:
    builder = _builder()
    assert REGISTRY_PATH.read_text(encoding="utf-8") == builder.dumps(builder.build())


def test_pins_this_spec_and_spec_names_it() -> None:
    assert REGISTRY["spec_version"] == COURTS["spec_version"]
    uri = (
        "https://raw.githubusercontent.com/codexpublicus/exemplar/{tag}/"
        "registry/reporter-variants.json"
    )
    assert f"| Reporter variants | `{uri}` | `{REGISTRY['version']}` |" in SPEC


def test_every_abbreviation_slugs_to_a_valid_slug() -> None:
    for spelling, entry in REGISTRY["variants"].items():
        slug = crk_check.slug(entry["abbreviation"])
        assert crk_check.RPT.fullmatch(f"rpt.1-{slug}-1"), spelling


def test_an_abbreviation_is_its_own_abbreviation() -> None:
    # One lookup gives the abbreviation: no entry maps to a spelling another entry maps on
    # elsewhere, though a curated entry may keep a spelling as its own (`P.R.`, `Cai.`).
    for spelling, entry in REGISTRY["variants"].items():
        target = REGISTRY["variants"].get(entry["abbreviation"])
        assert target is None or target["abbreviation"] == entry["abbreviation"], spelling


def test_the_puerto_rico_reports_take_pr() -> None:
    # D195: CAP's `P.R.`, reporters-db's `P.R.R.` and its variation `Puerto Rico` are one slug.
    assert {crk_check.reporter_slug(s) for s in ("P.R.", "P.R.R.", "Puerto Rico")} == {"pr"}
