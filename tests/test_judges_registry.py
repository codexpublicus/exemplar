# SPDX-FileCopyrightText: Copyright (c) 2026 Codex Publicus contributors
# SPDX-License-Identifier: BSD-3-Clause

"""Check schema/judges-registry.schema.json, the judge registry shape proposed as P8.

The schema is a draft pending the owner's ruling (codexpublicus/exemplar#47). These checks show
that it is a valid JSON Schema, that the fixtures standing in for a consumer's judge registry
validate against it unchanged, and that an entry in the proposed shape does.
"""

import copy
import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((ROOT / "schema" / "judges-registry.schema.json").read_text(encoding="utf-8"))
FIXTURES = [
    ROOT / "vectors" / "court-record-key" / "judges-fixture.json",
    ROOT / "examples" / "minimal" / "judges.json",
    ROOT / "examples" / "cap" / "judges.json",
]

# A registry in the proposed shape. The judge is made up and the court is a US court the court
# registry has, since no CCJ or Belize court is registered yet (codexpublicus/exemplar#25).
PROPOSED: dict[str, Any] = {
    "registry": "judges",
    "version": "2026.10.27",
    "spec": "spec/court-record-key.md",
    "spec_version": "0.5.1",
    "description": "Spec-derived example of the P8 shape; not a registry.",
    "judges": {
        "doe": {
            "name": "Doe",
            "full_name": "Jane Q. Doe",
            "courts": ["dc"],
            "offices": {
                "dc": [
                    {
                        "office": "Associate Judge",
                        "abbreviation": "J",
                        "from": "1990-01-02",
                        "to": "1999-12-31",
                    },
                    {"office": "Chief Judge", "abbreviation": "CJ", "from": "2000-01-03"},
                ]
            },
            "printed": [
                {
                    "form": "Dce",
                    "source": "https://example.org/judgment.pdf",
                    "provenance": "spec-derived",
                }
            ],
            "provenance": "spec-derived",
            "sources": ["https://example.org/judgment.pdf"],
        }
    },
}


def validator() -> jsonschema.Draft202012Validator:
    return jsonschema.Draft202012Validator(SCHEMA)


def test_schema_is_valid() -> None:
    jsonschema.Draft202012Validator.check_schema(SCHEMA)


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: str(p.relative_to(ROOT)))
def test_existing_fixtures_validate_unchanged(path: Path) -> None:
    validator().validate(json.loads(path.read_text(encoding="utf-8")))


def test_proposed_shape_validates() -> None:
    validator().validate(PROPOSED)


def test_published_registry_needs_its_version() -> None:
    registry = copy.deepcopy(PROPOSED)
    del registry["version"]
    assert not validator().is_valid(registry)


def test_office_needs_its_abbreviation() -> None:
    registry = copy.deepcopy(PROPOSED)
    del registry["judges"]["doe"]["offices"]["dc"][0]["abbreviation"]
    assert not validator().is_valid(registry)


def test_slug_follows_the_author_rule() -> None:
    registry = copy.deepcopy(PROPOSED)
    registry["judges"]["harlan2"] = registry["judges"].pop("doe")
    assert not validator().is_valid(registry)
