"""Check the court record key vectors against the spec's ABNF, its regex, and its rules.

The ABNF and the regex are read out of spec/court-record-key.md, so the spec,
the vectors and these checks can't drift apart silently.
"""

import json
import re
from functools import cache
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from abnf.parser import ParseError, Rule

from tests import crk_check

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "spec" / "court-record-key.md"
VECTORS = ROOT / "vectors" / "court-record-key"
PROVENANCE = {"human-curated", "hand-checked", "engine-output", "spec-derived"}


def _blocks(lang: str) -> list[str]:
    return re.findall(rf"^```{lang}\n(.*?)^```", SPEC.read_text(encoding="utf-8"), re.M | re.S)


class Grammar(Rule):
    """The spec's ABNF, every ```abnf block concatenated."""


Grammar.load_grammar("".join(_blocks("abnf")))
(_REGEX_TEXT,) = _blocks("regex")
CRK_RE = re.compile(_REGEX_TEXT.strip())


def abnf_accepts(rule: str, text: str) -> bool:
    try:
        Grammar(rule).parse_all(text)
    except ParseError:
        return False
    return True


def regex_accepts(text: str) -> bool:
    return CRK_RE.fullmatch(text) is not None


@cache
def load(name: str) -> list[dict[str, Any]]:
    lines = (VECTORS / name).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


COURTS = json.loads((ROOT / "registry" / "courts.json").read_text(encoding="utf-8"))["courts"]
JUDGES = json.loads((VECTORS / "judges-fixture.json").read_text(encoding="utf-8"))["judges"]
CAP_COURTS = json.loads((ROOT / "registry" / "cap-courts.json").read_text(encoding="utf-8"))
MANIFEST = json.loads((VECTORS / "manifest.json").read_text(encoding="utf-8"))
ERRATA_SCHEMA = json.loads((ROOT / "schema" / "crk-errata.schema.json").read_text("utf-8"))


def ids(name: str) -> list[str]:
    return [v["id"] for v in load(name)]


class TestVectorFiles:
    """Every vector file is listed, well formed, and says where it came from."""

    def test_manifest_lists_exactly_the_files_present(self) -> None:
        assert set(MANIFEST["files"]) == {p.name for p in VECTORS.glob("*.jsonl")}

    def test_manifest_spec_version_matches_the_spec(self) -> None:
        assert f"Specification version: **{MANIFEST['spec_version']}**" in SPEC.read_text()

    @pytest.mark.parametrize("name", sorted(MANIFEST["files"]))
    def test_ids_unique_and_provenance_recorded(self, name: str) -> None:
        vectors = load(name)
        assert vectors
        assert len({v["id"] for v in vectors}) == len(vectors)
        for v in vectors:
            assert v["provenance"] in PROVENANCE, v["id"]
            assert v["source"].strip(), v["id"]


class TestParse:
    """parse.jsonl: accepted by the ABNF, the regex and the rules; parts round-trip."""

    @pytest.mark.parametrize("v", load("parse.jsonl"), ids=ids("parse.jsonl"))
    def test_vector(self, v: dict[str, Any]) -> None:
        key = v["key"]
        assert abnf_accepts("crk", key)
        assert regex_accepts(key)
        assert crk_check.classify(key) is None
        assert crk_check.parse(key) == v["parts"]
        assert crk_check.format_key(v["parts"]) == key
        assert crk_check.decision_key(v["parts"]) == v["decision"]


class TestReject:
    """reject.jsonl: the grammar and the rules reject each string, for the stated reason."""

    @pytest.mark.parametrize("v", load("reject.jsonl"), ids=ids("reject.jsonl"))
    def test_vector(self, v: dict[str, Any]) -> None:
        key = v["key"]
        syntactic = v["layer"] == "syntax"
        assert abnf_accepts("crk", key) is not syntactic
        assert regex_accepts(key) is not syntactic
        assert crk_check.classify(key) == v["error"]


class TestCompute:
    """compute.jsonl: facts give the key, or the stated refusal."""

    @pytest.mark.parametrize("v", load("compute.jsonl"), ids=ids("compute.jsonl"))
    def test_vector(self, v: dict[str, Any]) -> None:
        if "key" in v:
            key = crk_check.compute(v["facts"], COURTS, JUDGES, CAP_COURTS)
            assert key == v["key"]
            assert abnf_accepts("crk", key)
            assert regex_accepts(key)
            assert crk_check.parse(key)["fallback"] is v["fallback"]
            if "aliases" in v:
                aliases = crk_check.consolidated_aliases(v["facts"], COURTS, key)
                assert aliases == v["aliases"]
                for alias in aliases:
                    assert abnf_accepts("crk-ref", alias)
            if "provisional" in v:
                assert crk_check.is_provisional(v["facts"]) is v["provisional"]
            if "printed_alias" in v:
                alias = crk_check.printed_alias(v["facts"], COURTS, JUDGES, CAP_COURTS)
                assert alias == v["printed_alias"]
                assert abnf_accepts("printed-alias", alias)
        else:
            with pytest.raises(crk_check.Refusal) as refusal:
                crk_check.compute(v["facts"], COURTS, JUDGES, CAP_COURTS)
            assert refusal.value.args[0] == v["error"]


class TestLedger:
    """ledger.jsonl: a ledger confirms or advances a candidate; a resolver follows replaced-by."""

    @pytest.mark.parametrize("v", load("ledger.jsonl"), ids=ids("ledger.jsonl"))
    def test_ledger_is_well_formed(self, v: dict[str, Any]) -> None:
        keys = [e["key"] for e in v["ledger"]]
        assert len(set(keys)) == len(keys)
        active: set[str] = set()
        for e in v["ledger"]:
            # Section 13.2: decision keys only; at most one active key per decision.
            assert crk_check.classify(e["key"]) is None, e["key"]
            assert crk_check.decision_key(crk_check.parse(e["key"])) == e["key"]
            assert e["status"] in {"active", "replaced", "errata"}
            assert ("replaced_by" in e) is (e["status"] == "replaced") or e["status"] == "errata"
            if "replaced_by" in e:
                assert e["replaced_by"] in keys
            if e["status"] == "active":
                assert e["decision"] not in active
                active.add(e["decision"])

    @pytest.mark.parametrize("v", load("ledger.jsonl"), ids=ids("ledger.jsonl"))
    def test_vector(self, v: dict[str, Any]) -> None:
        assert crk_check.classify(v["key"]) is None
        if "candidate" in v:
            assert crk_check.classify(v["candidate"]) is None
            got = crk_check.mint(v["ledger"], v["decision"], v["candidate"])
            assert got == {"key": v["key"], "minted": v["minted"], "replaces": v["replaces"]}
            if v["minted"]:
                # Never a key the ledger already holds, whatever its status.
                assert v["key"] not in {e["key"] for e in v["ledger"]}
                assert crk_check.stem(v["key"]) == crk_check.stem(v["candidate"])
        else:
            got = crk_check.resolve(v["ledger"], v["resolve"])
            assert got == {
                "key": v["key"],
                "decision": v["decision"],
                "provisional": v["provisional"],
            }


class TestErrata:
    """errata.jsonl and the spec's example: errata lists against the schema and section 13.4."""

    @staticmethod
    def problem(errata: dict[str, Any], previous: dict[str, Any] | None = None) -> str | None:
        validator = jsonschema.Draft202012Validator(
            ERRATA_SCHEMA, format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER
        )
        if any(validator.iter_errors(errata)):
            return "schema"
        return crk_check.errata_problem(errata, previous)

    def test_schema_is_valid(self) -> None:
        jsonschema.Draft202012Validator.check_schema(ERRATA_SCHEMA)

    @pytest.mark.parametrize("v", load("errata.jsonl"), ids=ids("errata.jsonl"))
    def test_vector(self, v: dict[str, Any]) -> None:
        if "previous" in v:
            assert self.problem(v["previous"]) is None
        assert self.problem(v["errata"], v.get("previous")) == v.get("problem")
        assert v["valid"] is ("problem" not in v)

    def test_spec_example(self) -> None:
        (example,) = _blocks("json")
        assert self.problem(json.loads(example)) is None


class TestDocket:
    """docket.jsonl: each profile's printed-to-segment mapping."""

    @pytest.mark.parametrize("v", load("docket.jsonl"), ids=ids("docket.jsonl"))
    def test_vector(self, v: dict[str, Any]) -> None:
        if "segment" in v:
            segment = crk_check.docket_segment(COURTS, v["court"], v["printed"], v.get("decided"))
            assert segment == v["segment"]
            assert abnf_accepts("docket", segment)
        else:
            with pytest.raises(crk_check.Refusal) as refusal:
                crk_check.docket_segment(COURTS, v["court"], v["printed"], v.get("decided"))
            assert refusal.value.args[0] == v["error"]


class TestByline:
    """byline.jsonl: a byline's printed name maps to a slug only through a name or printed form."""

    @pytest.mark.parametrize("v", load("byline.jsonl"), ids=ids("byline.jsonl"))
    def test_vector(self, v: dict[str, Any]) -> None:
        if "author" in v:
            assert crk_check.author_for(v["printed"], v["court"], JUDGES) == v["author"]
            assert abnf_accepts("author", v["author"])
        else:
            with pytest.raises(crk_check.Refusal) as refusal:
                crk_check.author_for(v["printed"], v["court"], JUDGES)
            assert refusal.value.args[0] == v["error"]

    def test_printed_forms_name_their_source(self) -> None:
        for slug, entry in JUDGES.items():
            for form in entry.get("printed", []):
                assert form["form"].strip() and form["source"].strip(), slug

    def test_printed_forms_differ_beyond_letter_case(self) -> None:
        # Section 10.2 matches after case folding, so a form that differs from the name or from
        # another form only in letter case adds nothing.
        for slug, entry in JUDGES.items():
            names = [entry["name"]] + [f["form"] for f in entry.get("printed", [])]
            folded = [n.casefold() for n in names]
            assert len(set(folded)) == len(folded), slug


class TestAlias:
    """alias.jsonl: printed forms normalize, aliases parse, targets are keys."""

    @pytest.mark.parametrize("v", load("alias.jsonl"), ids=ids("alias.jsonl"))
    def test_vector(self, v: dict[str, Any]) -> None:
        alias = v["alias"]
        assert abnf_accepts("alias", alias)
        assert alias.startswith(f"{v['scheme']}:")
        assert not regex_accepts(alias)
        if v["scheme"] == "crk":
            assert abnf_accepts("crk-ref", alias)
            assert regex_accepts(alias.removeprefix("crk:"))
        if v["scheme"] == "crk-printed":
            # Section 6.3: a decision key after the prefix, never a key reference.
            value = alias.removeprefix("crk-printed:")
            assert crk_check.classify(value) is None
            assert crk_check.parse(value)["role"] is None and "@" not in value
            assert not abnf_accepts("crk-ref", alias)
        if "printed" in v:
            assert crk_check.normalize_alias(v["scheme"], v["printed"]) == alias
        for key in v.get("resolves_to", []):
            assert regex_accepts(key)
            assert crk_check.classify(key) is None
            assert alias != key

    def test_a_bare_key_is_not_an_alias(self) -> None:
        for v in load("alias.jsonl"):
            if v["scheme"] == "crk":
                assert not abnf_accepts("alias", v["alias"].removeprefix("crk:"))


class TestKeyReference:
    """Section 2.6: a key reference is crk: followed by a key, and nothing else."""

    @pytest.mark.parametrize("v", load("parse.jsonl"), ids=ids("parse.jsonl"))
    def test_every_key_has_a_reference(self, v: dict[str, Any]) -> None:
        assert abnf_accepts("crk-ref", "crk:" + v["key"])
        assert not abnf_accepts("crk-ref", v["key"])

    @pytest.mark.parametrize(
        "text",
        [
            "CRK:us/ca10/14-9585/2016-08-23",
            "crk:/us/ca10/14-9585/2016-08-23",
            "crk://us/ca10/14-9585/2016-08-23",
            "crk:us/ca10/14-9585/2016-08-23#opinion",
            "crk:us/ca10/14-9585/2016-08-23?v=1",
            "crk:us/ca10/14-9585/2016-08-23.akn.xml",
            "crk:us%2Fca10%2F14-9585%2F2016-08-23",
            "crk:",
        ],
    )
    def test_rejects(self, text: str) -> None:
        assert not abnf_accepts("crk-ref", text)


def _vector_courts() -> list[tuple[str, str]]:
    """(vector id, court code) for every court code a vector resolves or names in a valid key."""
    found = []
    for v in load("compute.jsonl"):
        if v.get("error") != "unregistered-court" and "court" in v["facts"]:
            found.append((v["id"], v["facts"]["court"]))
        if "key" in v:
            found.append((v["id"], crk_check.parse(v["key"])["court"]))
    found += [(v["id"], v["court"]) for v in load("docket.jsonl")]
    found += [(v["id"], v["court"]) for v in load("byline.jsonl")]
    found += [(v["id"], crk_check.parse(v["key"])["court"]) for v in load("parse.jsonl")]
    for v in load("alias.jsonl"):
        keys = v.get("resolves_to", []) + (
            [v["alias"].removeprefix("crk:")] if v["scheme"] == "crk" else []
        )
        found += [(v["id"], crk_check.parse(key)["court"]) for key in keys]
    return found


class TestVectorCourts:
    """Every court code the vectors resolve is in registry/courts.json."""

    @pytest.mark.parametrize(("vid", "court"), _vector_courts())
    def test_registered(self, vid: str, court: str) -> None:
        assert court in COURTS, f"{vid}: {court} is not in registry/courts.json"

    def test_unregistered_court_vectors_are_unregistered(self) -> None:
        for v in load("compute.jsonl"):
            if v.get("error") == "unregistered-court" and "court" in v["facts"]:
                assert v["facts"]["court"] not in COURTS, v["id"]
            if v.get("error") == "unregistered-court" and "cap_court" in v["facts"]:
                assert v["facts"]["cap_court"] not in CAP_COURTS["courts"], v["id"]
            if v.get("error") == "court-under-review":
                assert CAP_COURTS["courts"][v["facts"]["cap_court"]]["review"], v["id"]


class TestGrammarAgreement:
    """The ABNF and the regex agree on every string any vector file mentions."""

    def test_agree(self) -> None:
        strings = {v["key"] for v in load("parse.jsonl") + load("reject.jsonl")}
        strings |= {v["key"] for v in load("compute.jsonl") if "key" in v}
        strings |= {v["alias"] for v in load("alias.jsonl")}
        for text in strings:
            assert abnf_accepts("crk", text) == regex_accepts(text), repr(text)
