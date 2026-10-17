"""Check the court record key vectors against the spec's ABNF, its regex, and its rules.

The ABNF and the regex are read out of spec/court-record-key.md, so the spec,
the vectors and these checks can't drift apart silently.
"""

import json
import re
from functools import cache
from pathlib import Path
from typing import Any

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


REGISTRY = json.loads((VECTORS / "registry-fixture.json").read_text(encoding="utf-8"))
MANIFEST = json.loads((VECTORS / "manifest.json").read_text(encoding="utf-8"))


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
            key = crk_check.compute(v["facts"], REGISTRY)
            assert key == v["key"]
            assert abnf_accepts("crk", key)
            assert regex_accepts(key)
            assert crk_check.parse(key)["fallback"] is v["fallback"]
        else:
            with pytest.raises(crk_check.Refusal) as refusal:
                crk_check.compute(v["facts"], REGISTRY)
            assert refusal.value.args[0] == v["error"]


class TestDocket:
    """docket.jsonl: each profile's printed-to-segment mapping."""

    @pytest.mark.parametrize("v", load("docket.jsonl"), ids=ids("docket.jsonl"))
    def test_vector(self, v: dict[str, Any]) -> None:
        if "segment" in v:
            segment = crk_check.docket_segment(REGISTRY, v["court"], v["printed"])
            assert segment == v["segment"]
            assert abnf_accepts("docket", segment)
        else:
            with pytest.raises(crk_check.Refusal) as refusal:
                crk_check.docket_segment(REGISTRY, v["court"], v["printed"])
            assert refusal.value.args[0] == v["error"]


class TestAlias:
    """alias.jsonl: printed forms normalize, aliases parse, targets are keys."""

    @pytest.mark.parametrize("v", load("alias.jsonl"), ids=ids("alias.jsonl"))
    def test_vector(self, v: dict[str, Any]) -> None:
        alias = v["alias"]
        assert abnf_accepts("alias", alias)
        if v["scheme"] == "docket":
            assert regex_accepts(alias)
        else:
            assert alias.startswith(f"{v['scheme']}:")
            assert not regex_accepts(alias)
        if "printed" in v:
            assert crk_check.normalize_alias(v["scheme"], v["printed"]) == alias
        for key in v.get("resolves_to", []):
            assert regex_accepts(key)
            assert crk_check.classify(key) is None
            assert alias != key


class TestGrammarAgreement:
    """The ABNF and the regex agree on every string any vector file mentions."""

    def test_agree(self) -> None:
        strings = {v["key"] for v in load("parse.jsonl") + load("reject.jsonl")}
        strings |= {v["key"] for v in load("compute.jsonl") if "key" in v}
        strings |= {v["alias"] for v in load("alias.jsonl")}
        for text in strings:
            assert abnf_accepts("crk", text) == regex_accepts(text), repr(text)
