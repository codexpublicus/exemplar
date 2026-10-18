"""Check registry/courts.json: its schema, its source pin, and the spec's rules for it."""

import hashlib
import importlib.util
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from tests import crk_check
from tests.test_court_record_key import abnf_accepts

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "registry" / "courts.json"
REGISTRY: dict[str, Any] = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
SCHEMA = json.loads((ROOT / "schema" / "courts-registry.schema.json").read_text(encoding="utf-8"))
SPEC = (ROOT / "spec" / "court-record-key.md").read_text(encoding="utf-8")


def _builder() -> Any:
    spec = importlib.util.spec_from_file_location(
        "build_courts", ROOT / "registry" / "build_courts.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_schema_is_valid() -> None:
    jsonschema.Draft202012Validator.check_schema(SCHEMA)


def test_registry_matches_schema() -> None:
    validator = jsonschema.Draft202012Validator(
        SCHEMA, format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER
    )
    errors = sorted(validator.iter_errors(REGISTRY), key=lambda e: list(e.path))
    assert not errors, [f"{list(e.path)}: {e.message}" for e in errors[:5]]


def test_vendored_source_matches_its_pin() -> None:
    source = REGISTRY["source"]
    vendored = ROOT / source["vendored_copy"]
    assert hashlib.sha256(vendored.read_bytes()).hexdigest() == source["sha256"]
    assert (vendored.parent / "LICENSE").is_file()


def test_registry_is_the_build_of_the_vendored_source() -> None:
    builder = _builder()
    assert REGISTRY_PATH.read_text(encoding="utf-8") == builder.dumps(builder.build())


def test_every_source_court_is_registered_or_excluded() -> None:
    source = json.loads((ROOT / REGISTRY["source"]["vendored_copy"]).read_bytes())
    ids = {c["id"] for c in source}
    assert ids == set(REGISTRY["courts"]) | set(REGISTRY["excluded"])
    assert not set(REGISTRY["courts"]) & set(REGISTRY["excluded"])


def test_spec_names_this_registry_version() -> None:
    assert f"| Courts | `registry/courts.json` | `{REGISTRY['version']}` |" in SPEC
    assert f"Specification version: **{REGISTRY['spec_version']}**" in SPEC


@pytest.mark.parametrize("code", sorted(REGISTRY["courts"]))
def test_code_matches_the_court_rule(code: str) -> None:
    assert abnf_accepts("court", code)


@pytest.mark.parametrize(
    ("code", "entry"), sorted(REGISTRY["courts"].items()), ids=sorted(REGISTRY["courts"])
)
def test_profiles_are_known_and_in_date_order(code: str, entry: dict[str, Any]) -> None:
    starts = []
    for i, step in enumerate(entry["profiles"]):
        assert step["profile"] in crk_check.PROFILES, code
        if step["from"] is None:
            assert i == 0, f"{code}: only the first profile may start at null"
            starts.append("")
        else:
            date.fromisoformat(step["from"])
            starts.append(step["from"])
    assert starts == sorted(set(starts)), code
    if (replaced_by := entry.get("replaced-by")) is not None:
        assert replaced_by in REGISTRY["courts"], code


def test_spec_profiles_are_the_ones_the_registry_may_assign() -> None:
    assigned = set(
        SCHEMA["$defs"]["court"]["properties"]["profiles"]["items"]["properties"]["profile"]["enum"]
    )
    in_spec = set(re.findall(r"^### 5\.\d+ Profile `([a-z0-9-]+)`", SPEC, re.M))
    assert assigned == in_spec == set(crk_check.PROFILES)
