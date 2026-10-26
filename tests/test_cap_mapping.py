# SPDX-FileCopyrightText: Copyright (c) 2026 <COPYRIGHT HOLDER>
# SPDX-License-Identifier: BSD-3-Clause

"""Check vectors/akn-profile/cap-mapping.jsonl against a minimal reading of the CAP mappings.

The functions here are written from spec/akoma-ntoso-profile.md (sections 9.1, 15.2 and 15.4), not
from examples/cap/build.py, so a vector that disagrees with them points at the vector or the spec.
"""

import json
import re
from pathlib import Path
from typing import Any

import pytest

from tests import crk_check

ROOT = Path(__file__).resolve().parent.parent
VECTORS = [
    json.loads(line)
    for line in (ROOT / "vectors" / "akn-profile" / "cap-mapping.jsonl")
    .read_text(encoding="utf-8")
    .splitlines()
    if line.strip()
]
PROVENANCE = {"human-curated", "hand-checked", "engine-output", "spec-derived"}
ROLES = {
    "majority": "opinion",
    "unanimous": "opinion",
    "plurality": "plurality",
    "concurrence": "concurrence",
    "concurring-in-part-and-dissenting-in-part": "partial",
    "dissent": "dissent",
}


def role(source_type: str, byline: str) -> str:
    """Section 15.4."""
    if source_type == "majority" and re.sub(r"[^a-z]", "", byline.lower()) in (
        "percuriam",
        "bythecourt",
        "thecourt",
    ):
        return "per-curiam"
    return ROLES[source_type]


def cite_alias(cite: str) -> str:
    return crk_check.normalize_alias("cite", cite)


def href(link: dict[str, str], cites_to: list[dict[str, str]]) -> str | None:
    """Section 15.2: the ref target of a CAP citation link, or None for unmarked text."""
    cite = link["data-cite"]
    paths = [p for p in link.get("data-case-paths", "").split(",") if p]
    if len(paths) == 1:
        return "cap:" + paths[0].lstrip("/")
    if paths:
        return cite_alias(cite)
    bare = re.sub(r"\s", "", cite)
    for entry in cites_to:
        if re.sub(r"\s", "", entry["cite"]) == bare:
            if entry["category"] == "reporters:neutral":
                return crk_check.normalize_alias("neutral", cite)
            if entry["category"].startswith("reporters:"):
                return cite_alias(cite)
            return None
    return None


def scans(block_scans: list[int], labels: int, first_label_before_text: bool) -> list[int] | None:
    """Section 9.1: each label's @cx:scan, or None when the block has too few scan pages."""
    pages: list[int] = []
    for page in block_scans:
        if not pages or pages[-1] != page:
            pages.append(page)
    offset = 0 if first_label_before_text else 1
    if len(pages) < labels + offset:
        return None
    return pages[offset : offset + labels]


@pytest.mark.parametrize("v", VECTORS, ids=[v["id"] for v in VECTORS])
def test_vector(v: dict[str, Any]) -> None:
    assert v["provenance"] in PROVENANCE
    assert v["source"].strip()
    if v["kind"] == "role":
        assert role(v["source_type"], v["byline"]) == v["role"]
    elif v["kind"] == "citation":
        assert href(v["link"], v["cites_to"]) == v["href"]
    else:
        assert v["kind"] == "scan"
        assert scans(v["block_scans"], v["labels"], v["first_label_before_text"]) == v["scans"]


def test_ids_unique() -> None:
    assert len({v["id"] for v in VECTORS}) == len(VECTORS)
