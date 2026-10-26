# SPDX-FileCopyrightText: Copyright (c) 2026 Codex Publicus contributors
# SPDX-License-Identifier: BSD-3-Clause

"""Check the licence files and the SPDX annotations README.md's Licensing section describes."""

import hashlib
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# SHA-256 of https://creativecommons.org/licenses/by-nd/4.0/legalcode.txt, retrieved 2026-10-26.
CC_BY_ND_SHA256 = "9cc97638cf0185884ac800144b6246c7772f94ff2cc70686afa9574aaea4fa2b"

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


def test_cc_by_nd_legal_code_is_the_official_text() -> None:
    text = (ROOT / "LICENSES" / "CC-BY-ND-4.0.txt").read_bytes()
    assert hashlib.sha256(text).hexdigest() == CC_BY_ND_SHA256


def test_license_is_bsd_3_clause() -> None:
    text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert text.startswith("BSD 3-Clause License\n")
    assert "Neither the name of the copyright holder" in text


def test_code_files_carry_spdx_headers() -> None:
    files = code_files()
    assert files
    missing = [
        str(path.relative_to(ROOT))
        for path in files
        if "SPDX-License-Identifier: BSD-3-Clause"
        not in "".join(path.read_text(encoding="utf-8").splitlines(keepends=True)[:6])
    ]
    assert not missing, f"no BSD-3-Clause SPDX header: {missing}"


def test_reuse_annotations_name_existing_files() -> None:
    reuse = tomllib.loads((ROOT / "REUSE.toml").read_text(encoding="utf-8"))
    assert reuse["version"] == 1
    for annotation in reuse["annotations"]:
        assert annotation["SPDX-License-Identifier"] in {"BSD-3-Clause", "CC-BY-ND-4.0"}
        for pattern in annotation["path"]:
            assert list(ROOT.glob(pattern)), f"REUSE.toml path matches nothing: {pattern}"
