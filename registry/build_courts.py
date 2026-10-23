"""Build registry/courts.json from the vendored courts-db snapshot.

    uv run python registry/build_courts.py          # rewrite registry/courts.json
    uv run python registry/build_courts.py --check  # exit 1 if it is out of date

The output is a pure function of registry/sources/courts-db/courts.json and the
rules below, so tests/test_courts_registry.py can rebuild it and compare. The
registry is append-only (spec section 10.3): when a later courts-db snapshot is
vendored, a rebuild may add courts and nothing else; the tests don't check that
against earlier releases, so check it in review.
"""

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "registry" / "sources" / "courts-db" / "courts.json"
OUTPUT = ROOT / "registry" / "courts.json"

VERSION = "2026.10.18"
SPEC_VERSION = "0.3.0"

PROVENANCE = {
    "name": "courts-db",
    "publisher": "Free Law Project",
    "repository": "https://github.com/freelawproject/courts-db",
    "commit": "c22604dff8b6819d022cc5ddfd6d9080101149e3",
    "commit_date": "2026-10-07T13:50:54-06:00",
    "path": "courts_db/data/courts.json",
    "vendored_copy": "registry/sources/courts-db/courts.json",
    "retrieved": "2026-10-18",
    "license_as_stated": (
        "BSD 2-Clause License, per the repository's LICENSE file at that commit "
        "(copied verbatim to registry/sources/courts-db/LICENSE)"
    ),
}

COURT_RULE = re.compile(r"[a-z][a-z0-9-]*")
NOT_US = {"international", "colonial"}
COURTS_OF_APPEALS = {f"ca{n}" for n in range(1, 12)} | {"cadc"}
NOT_A_COURT = {"usdistct"}  # courts-db's generic "United States District Court"


def profiles(court: dict[str, Any]) -> list[dict[str, str | None]]:
    """The docket profiles (spec section 5) this registry assigns to a courts-db court."""
    code = court["id"]
    if code == "scotus":
        return [{"from": "1971-07-01", "profile": "scotus-ot1971"}]
    if code in COURTS_OF_APPEALS:
        return [{"from": None, "profile": "us-coa"}]
    if code == "cafc":
        return []  # four-digit-year dockets; no profile yet (spec section 16)
    federal = court.get("system") == "federal"
    if (
        federal
        and court.get("type") in ("trial", "bankruptcy")
        and not code.startswith("bap")
        and code not in NOT_A_COURT
    ):
        return [{"from": None, "profile": "us-district"}]
    return [{"from": None, "profile": "printed"}]


def exclusion(court: dict[str, Any]) -> str | None:
    if not COURT_RULE.fullmatch(court["id"]):
        return "id does not match the court rule (spec section 2.1)"
    if court.get("system") in NOT_US:
        return f"not a US court (courts-db system {court['system']!r})"
    return None


def build() -> dict[str, Any]:
    raw = SOURCE.read_bytes()
    source = json.loads(raw)
    courts: dict[str, Any] = {}
    excluded: dict[str, str] = {}
    for court in sorted(source, key=lambda c: c["id"]):
        if reason := exclusion(court):
            excluded[court["id"]] = reason
            continue
        courts[court["id"]] = {
            "country": "us",
            "name": " ".join(court["name"].split()),
            "profiles": profiles(court),
            "source": "courts-db",
        }
    return {
        "registry": "courts",
        "version": VERSION,
        "spec": "spec/court-record-key.md",
        "spec_version": SPEC_VERSION,
        "description": (
            "Court registry for the court record key (spec section 10.1). Every court code is "
            "a courts-db id from the snapshot named in source; the docket profiles are this "
            "registry's assignments (registry/build_courts.py)."
        ),
        "source": {**PROVENANCE, "sha256": hashlib.sha256(raw).hexdigest()},
        "excluded": excluded,
        "courts": courts,
    }


def dumps(registry: dict[str, Any]) -> str:
    """Pretty JSON with one court per line, so a diff shows exactly the courts added."""
    head = {k: v for k, v in registry.items() if k != "courts"}
    lines = json.dumps(head, indent=2, ensure_ascii=False)[:-2].splitlines()
    lines[-1] += ","
    lines.append('  "courts": {')
    items = list(registry["courts"].items())
    for i, (code, entry) in enumerate(items):
        comma = "," if i < len(items) - 1 else ""
        lines.append(f"    {json.dumps(code)}: {json.dumps(entry, ensure_ascii=False)}{comma}")
    lines += ["  }", "}"]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    text = dumps(build())
    if "--check" in argv:
        if OUTPUT.read_text(encoding="utf-8") != text:
            print(f"{OUTPUT.relative_to(ROOT)} is out of date; run registry/build_courts.py")
            return 1
        return 0
    OUTPUT.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
