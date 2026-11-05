# SPDX-FileCopyrightText: Copyright (c) 2026 Codex Publicus contributors
# SPDX-License-Identifier: BSD-3-Clause

"""Check the licence files and the SPDX annotations README.md's Licensing section describes."""

import hashlib
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# SHA-256 of each legal code as creativecommons.org serves it, retrieved 2026-10-26:
# https://creativecommons.org/licenses/by-nd/4.0/legalcode.txt and
# https://creativecommons.org/publicdomain/zero/1.0/legalcode.txt.
LEGAL_CODE_SHA256 = {
    "CC-BY-ND-4.0.txt": "9cc97638cf0185884ac800144b6246c7772f94ff2cc70686afa9574aaea4fa2b",
    "CC0-1.0.txt": "a2010f343487d3f7618affe54f789f5487602331c0a8d03f49e9a7c547cf0499",
}
# Built up so that REUSE tooling doesn't read this file's source as a licence tag.
BSD_TAG = "SPDX-License-" + "Identifier: BSD-3-Clause"

CODE_DIRS = ["validator", "tests", "registry", "examples"]
SKIP_PARTS = {"vendor", "sources", "__pycache__"}


def code_files() -> list[Path]:
    files = [
        path
        for directory in CODE_DIRS
        for path in (ROOT / directory).rglob("*.py")
        if not SKIP_PARTS & set(path.relative_to(ROOT).parts)
    ]
    files += sorted((ROOT / ".mise" / "tasks").iterdir())
    files += sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    return files


@pytest.mark.parametrize("name", sorted(LEGAL_CODE_SHA256))
def test_cc_legal_code_is_the_official_text(name: str) -> None:
    text = (ROOT / "LICENSES" / name).read_bytes()
    assert hashlib.sha256(text).hexdigest() == LEGAL_CODE_SHA256[name]


def test_license_is_bsd_3_clause() -> None:
    text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert text.startswith("BSD 3-Clause License\n")
    assert "Neither the name of the copyright holder" in text
    assert (ROOT / "LICENSES" / "BSD-3-Clause.txt").read_text(encoding="utf-8") == text


def test_courts_db_notice_reproduces_its_license() -> None:
    notice = (ROOT / "registry" / "NOTICE-courts-db.txt").read_text(encoding="utf-8")
    vendored = (ROOT / "registry" / "sources" / "courts-db" / "LICENSE").read_text(encoding="utf-8")
    assert notice.endswith(vendored)
    assert "registry/courts.json is built from data in Free Law Project's courts-db" in notice


def test_reporters_db_notice_reproduces_its_license() -> None:
    notice = (ROOT / "registry" / "NOTICE-reporters-db.txt").read_text(encoding="utf-8")
    vendored = (ROOT / "registry" / "sources" / "reporters-db" / "LICENSE").read_text("utf-8")
    assert notice.endswith(vendored)
    assert "registry/reporter-variants.json is built from data in Free Law Project's" in notice


def test_code_files_carry_spdx_headers() -> None:
    files = code_files()
    assert files
    missing = [
        str(path.relative_to(ROOT))
        for path in files
        if BSD_TAG not in "".join(path.read_text(encoding="utf-8").splitlines(keepends=True)[:6])
    ]
    assert not missing, f"no BSD-3-Clause SPDX header: {missing}"


def test_reuse_annotations_name_existing_files() -> None:
    reuse = tomllib.loads((ROOT / "REUSE.toml").read_text(encoding="utf-8"))
    assert reuse["version"] == 1
    for annotation in reuse["annotations"]:
        assert annotation["SPDX-License-Identifier"] in {"BSD-3-Clause", "CC-BY-ND-4.0", "CC0-1.0"}
        for pattern in annotation["path"]:
            assert list(ROOT.glob(pattern)), f"REUSE.toml path matches nothing: {pattern}"
