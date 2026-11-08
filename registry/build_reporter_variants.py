# SPDX-FileCopyrightText: Copyright (c) 2026 Codex Publicus contributors
# SPDX-License-Identifier: BSD-3-Clause

"""Build registry/reporter-variants.json from the vendored reporters-db snapshot.

    uv run python registry/build_reporter_variants.py          # rewrite the registry
    uv run python registry/build_reporter_variants.py --check  # exit 1 if it is out of date

The variant map (spec sections 5.6 and 10.1, from 0.7.0) gives, for a spelling of a reporter's
abbreviation, the abbreviation whose slug a key uses. Its entries are a pure function of
registry/sources/reporters-db/reporters.json and CURATED below, so
tests/test_reporter_variants.py can rebuild it and compare:

- every variation reporters-db lists for exactly one edition, and that isn't itself an edition,
  maps to that edition (basis reporters-db);
- CURATED adds the spellings the Caselaw Access Project uses that reporters-db lacks, resolves the
  one spelling CAP uses that reporters-db gives several editions for, keeps separate the series
  reporters-db's variations would join, and gives the Puerto Rico Reports one abbreviation, `P.R.`,
  for every spelling, reporters-db's edition `P.R.R.` included (basis curated). A curated entry
  overrides reporters-db's.

A spelling that is a reporters-db edition and has no curated entry, or that the map doesn't list,
is its own abbreviation. Every abbreviation the map gives is its own abbreviation, so one lookup
gives it.
"""

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "registry" / "sources" / "reporters-db" / "reporters.json"
OUTPUT = ROOT / "registry" / "reporter-variants.json"

VERSION = "2026.11.05"
SPEC_VERSION = "0.7.0"

PROVENANCE = {
    "name": "reporters-db",
    "publisher": "Free Law Project",
    "repository": "https://github.com/freelawproject/reporters-db",
    "release": "v3.2.67",
    "commit": "4dd4e64e2fdbdb99215a8040bdb65eb74f8e1542",
    "commit_date": "2026-10-09T19:48:51Z",
    "path": "reporters_db/data/reporters.json",
    "vendored_copy": "registry/sources/reporters-db/reporters.json",
    "retrieved": "2026-11-05",
    "license_as_stated": (
        "BSD 2-Clause License, per the repository's LICENSE file at that commit "
        "(copied verbatim to registry/sources/reporters-db/LICENSE)"
    ),
}

# Spelling -> (abbreviation, note). The spellings are as the Caselaw Access Project's metadata
# prints them, in a citation or as a volume's reporter, with whitespace collapsed (D192,
# codexpublicus/exemplar#31).
KEPT_SEPARATE = "Kept separate, as the owner ruled in A246 (2026-11-08)"
CURATED: dict[str, tuple[str, str]] = {
    # Three variations reporters-db lists that would put two series under one slug.
    "Cai.": (
        "Cai.",
        f"{KEPT_SEPARATE}: Caines' Reports (New York Supreme Court, CAP volumes `cai`), a series "
        "of its own; reporters-db lists `Cai.` as a variation of `Cai. Cas.`, Caines' Cases "
        "(CAP volumes `cai-cas`), which would join them (513 CAP fallback keys)",
    ),
    "Supp. Tex.": (
        "Supp. Tex.",
        f"{KEPT_SEPARATE}: the Supplement to 25 Texas Reports (CAP volume `tex/25-supp`), paged "
        "apart from 25 Tex.; reporters-db lists `Supp. Tex.` as a variation of `Tex.`, which "
        "would make `rpt.25-tex-1` page 1 of both books (100 CAP fallback keys)",
    ),
    "Miss. (S. & M. Ch.)": (
        "Miss. (S. & M. Ch.)",
        f"{KEPT_SEPARATE}: Smedes and Marshall's Chancery Reports (the Superior Court of "
        "Chancery of Mississippi, CAP volumes `miss-s-m-ch`), a series of its own; reporters-db "
        "lists it as a variation of `S. & M.`, the Mississippi Reports of Smedes and Marshall "
        "(the High Court of Errors and Appeals), which would join them (70 CAP fallback keys)",
    ),
    # The Puerto Rico Reports: reporters-db gives `P.R.` three editions (`P.`, `P.R.R.`,
    # `Pen. & W.`) and abbreviates the report `P.R.R.`; the map gives all of its spellings `P.R.`,
    # the slug `pr` CAP's volumes and earlier versions of this spec use (D195).
    "P.R.": (
        "P.R.",
        "CAP's volumes named `P.R.` are the Puerto Rico Reports, the English edition of the "
        "Supreme Court of Puerto Rico's decisions, slug `pr` (D195); reporters-db also lists "
        "`P.R.` as a variation of `P.` (the Pacific Reporter) and `Pen. & W.` (Penrose and "
        "Watts), which CAP doesn't spell `P.R.`",
    ),
    "P.R.R.": (
        "P.R.",
        "reporters-db's abbreviation of the Puerto Rico Reports, which CAP's volumes name `P.R.`; "
        "mapped to `P.R.`, so that both spellings take the slug `pr` (D195)",
    ),
    "Puerto Rico": (
        "P.R.",
        "reporters-db's variation of `P.R.R.`, the Puerto Rico Reports; mapped with it (D195)",
    ),
    # Spellings CAP uses that reporters-db 3.2.67 lacks.
    "Davis L. Ct. Cas.": (
        "Davis. L. Ct. Cas.",
        "CAP's volume name for the Massachusetts Land Court decisions, 1898-1908, whose "
        "citations CAP prints `Davis. L. Ct. Cas.`, the reporters-db edition",
    ),
    "Ga. Supp.": (
        "Ga. Supp.",
        "The Supplement to 33 Georgia Reports (CAP volume `ga/33-suppl`), paged apart from "
        "33 Ga.; reporters-db lacks it, and its `Suppl. Ga.`, a variation of `Ga.`, would join "
        "it to the volume",
    ),
    "A.D": ("A.D.", "the period dropped; CAP prints these citations in volumes of A.D."),
    "A.D.3dv": ("A.D.3d", "a stray letter; 4 A.D.3d 863, which CAP prints in 4 A.D.3d"),
    "A.D.6d": ("A.D.3d", "a misprint: there is no sixth series; CAP prints it in 39 A.D.3d"),
    "F. Cas. page": ("F. Cas.", "the word `page` read into the reporter; volumes of F. Cas."),
    "F. Cas. Page": ("F. Cas.", "the word `Page` read into the reporter; volumes of F. Cas."),
    "F.2": ("F.2d", "773 F.2d 306, a Federal Circuit decision of 1985"),
    "F.3": ("F.3d", "665 F.3d 408, a Second Circuit decision of 2011"),
    "F3.d": ("F.3d", "the period misplaced; decisions of the 1990s cited to F.3d"),
    "F.485Supp.": ("F. Supp.", "283 F. Supp. 470, which CAP prints in 283 F. Supp."),
    "Fed.Appx": ("F. App'x", "the spaces dropped from reporters-db's variation `Fed. Appx`"),
    "Mass": ("Mass.", "the period dropped; CAP prints it in 430 Mass."),
    "Misc .2d": ("Misc. 2d", "a misplaced space; CAP prints it in 29 Misc. 2d"),
    "N.P. (n.s.)": ("Ohio N.P. (n.s.)", "`Ohio` dropped; CAP prints it in 14 Ohio N.P. (n.s.)"),
    "N.Y.S": ("N.Y.S.", "the period dropped; CAP prints these in 40 N.Y.S."),
    "Ohio C.C. (n.s)": ("Ohio C.C. (n.s.)", "the last period dropped; CAP volume 17 of it"),
    "Pa. D. & C": ("Pa. D. & C.", "the period dropped; CAP prints it in 67 Pa. D. & C."),
    "S. Ct. (2006)": ("S. Ct.", "the year read into the reporter; 126 S. Ct., of 2006"),
    "St. Ct.": ("S. Ct.", "a misprint; 107 S. Ct. 667, a Supreme Court decision of 1986"),
    "U.S": ("U.S.", "the period dropped; CAP prints it in 500 U.S."),
}


def spelling(text: str) -> str:
    """A spelling as the map lists it: whitespace runs collapsed to one space, trimmed."""
    return " ".join(text.split())


def build() -> dict[str, Any]:
    raw = SOURCE.read_bytes()
    source = json.loads(raw)
    editions: set[str] = set()
    variations: dict[str, list[str]] = {}
    for books in source.values():
        for book in books:
            editions |= {spelling(e) for e in book["editions"]}
            for variation, edition in book["variations"].items():
                targets = variations.setdefault(spelling(variation), [])
                if spelling(edition) not in targets:
                    targets.append(spelling(edition))
    variants: dict[str, dict[str, str]] = {}
    unresolved: dict[str, list[str]] = {}
    for variation, targets in variations.items():
        if variation in editions:
            continue
        if len(targets) == 1:
            variants[variation] = {"abbreviation": targets[0], "basis": "reporters-db"}
        else:
            unresolved[variation] = sorted(targets)
    for variation, (abbreviation, note) in CURATED.items():
        assert variation == spelling(variation), variation
        # A curated abbreviation is an edition, or a spelling a curated entry keeps as its own.
        assert abbreviation in editions or CURATED.get(abbreviation, ("",))[0] == abbreviation
        unresolved.pop(variation, None)
        variants[variation] = {"abbreviation": abbreviation, "basis": "curated", "note": note}
    for variation, entry in variants.items():
        # One lookup gives the abbreviation: it is its own abbreviation.
        target = variants.get(entry["abbreviation"])
        assert target is None or target["abbreviation"] == entry["abbreviation"], variation
    return {
        "registry": "reporter-variants",
        "version": VERSION,
        "spec": "spec/court-record-key.md",
        "spec_version": SPEC_VERSION,
        "description": (
            "The reporter variant map (spec sections 5.6 and 10.1, from 0.7.0): for a spelling of "
            "a reporter's abbreviation, with whitespace runs collapsed to one space, the "
            "abbreviation whose slug a key and a cite: alias use. A spelling the map doesn't list "
            "is its own abbreviation. Entries with basis reporters-db are the variations the "
            "reporters-db snapshot named in source lists for exactly one edition; entries with "
            "basis curated are this registry's (registry/build_reporter_variants.py) and override "
            "reporters-db's. unresolved lists the variations reporters-db gives several editions "
            "for that no curated entry resolves; each is its own abbreviation."
        ),
        "source": {**PROVENANCE, "sha256": hashlib.sha256(raw).hexdigest()},
        "variants": dict(sorted(variants.items())),
        "unresolved": dict(sorted(unresolved.items())),
    }


def dumps(registry: dict[str, Any]) -> str:
    """Pretty JSON with one spelling per line, so a diff shows exactly the spellings changed."""
    head = {k: v for k, v in registry.items() if k not in ("variants", "unresolved")}
    lines = json.dumps(head, indent=2, ensure_ascii=False)[:-2].splitlines()
    lines[-1] += ","
    for name in ("variants", "unresolved"):
        lines.append(f"  {json.dumps(name)}: {{")
        items = list(registry[name].items())
        for i, (key, value) in enumerate(items):
            comma = "," if i < len(items) - 1 else ""
            lines.append(
                f"    {json.dumps(key, ensure_ascii=False)}: "
                f"{json.dumps(value, ensure_ascii=False)}{comma}"
            )
        lines.append("  }," if name == "variants" else "  }")
    lines.append("}")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    text = dumps(build())
    if "--check" in argv:
        if OUTPUT.read_text(encoding="utf-8") != text:
            print(f"{OUTPUT.relative_to(ROOT)} is out of date; run {Path(__file__).name}")
            return 1
        return 0
    OUTPUT.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
