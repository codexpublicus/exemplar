"""Build the CAP examples: Akoma Ntoso documents and sidecars from Caselaw Access Project cases.

Usage:
    uv run python examples/cap/build.py          # rebuild every example from examples/cap/source/
    uv run python examples/cap/build.py --fetch  # download the source files, then rebuild
    uv run python examples/cap/build.py --check  # rebuild in memory; fail if a file differs
    uv run python examples/cap/build.py --lock   # pin the CAP volume records again, then rebuild

The examples and their sources are listed in examples/cap/manifest.json. Each source file is checked
against the SHA-256 recorded there before it is read.

A printing's @ordinal and @text, and a reporter fallback key's decision ordinal, come from CAP's
volume records: metadata/VolumeMetadata.json and metadata/CasesMetadata.json in each volume zip on
data.stare.pub, read with HTTP range requests so no whole zip is downloaded. examples/cap/
volumes.lock.json pins each zip by its ETag and size and each member read by its SHA-256; a build
refuses a zip or member that doesn't match. Members are cached in .cache/stare/ at the repository
root, so a build with a warm cache makes no requests. Nothing from the volume records is vendored.

The build is deterministic: the same sources, volume records, manifest, judge fixture and court
registry give byte-identical output.

This is a producer of spec/akoma-ntoso-profile.md written for these examples, not a general CAP
converter. It refuses, rather than guesses, whenever a case needs something the profile or the court
record key spec leaves open, and says why.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from lxml import etree, html

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
MANIFEST = HERE / "manifest.json"
SOURCE = HERE / "source"
COURTS = ROOT / "registry" / "courts.json"
LOCK = HERE / "volumes.lock.json"
CACHE = ROOT / ".cache" / "stare"

CAP_ZIP = "https://data.stare.pub/cap/{slug}/{volume}.zip"
REPORTERS = "https://stare.pub/reporters.json"
INDEX_MANIFEST = "https://idx.stare.pub/manifest.json"
USER_AGENT = "exemplar-cap-examples (+https://github.com/codexpublicus/exemplar)"
VOLUME_RECORDS = ("metadata/VolumeMetadata.json", "metadata/CasesMetadata.json")

AKN = "http://docs.oasis-open.org/legaldocml/ns/akn/3.0"
CX = "https://codexpublicus.org/ns/exemplar"
NSMAP = {None: AKN, "cx": CX}

HEADER_CLASSES = {
    "parties",
    "docketnumber",
    "court",
    "decisiondate",
    "otherdate",
    "attorneys",
    "judges",
    "syllabus",
    "headnotes",
    "summary",
    "synopsis",
    "history",
    "disposition",
    "posture",
    "arguments",
    "statement",
    "citation",
    "headmatter",
}

# CAP opinion types to CRK roles (profile section 15.4). Types not listed are refused (O8).
ROLES = {
    "majority": "opinion",
    "unanimous": "opinion",
    "plurality": "plurality",
    "concurrence": "concurrence",
    "concurring-in-part-and-dissenting-in-part": "partial",
    "dissent": "dissent",
}
DECISION_ROLES = {"order", "judgment", "decree"}
OPINION_TYPES = {
    "concurrence": "agreeing",
    "concurrence-in-judgment": "agreeing",
    "concurrence-in-part-and-judgment": "agreeing",
    "dissent": "dissenting",
}

KEY = re.compile(
    r"^us/([a-z][a-z0-9-]*)/([a-z0-9][a-z0-9_.-]*)/([0-9]{4}-[0-9]{2}-[0-9]{2})(~([2-9]|[1-9][0-9]+))?"
    r"(/(opinion|per-curiam|plurality|concurrence|concurrence-in-judgment|"
    r"concurrence-in-part-and-judgment|partial|partial-majority|dissent|statement|order|judgment|"
    r"decree)(\.[a-z][a-z-]*(\+[a-z][a-z-]*)*)?(~([2-9]|[1-9][0-9]+))?)?(@[0-9]{4}-[0-9]{2}-[0-9]{2})?$"
)
DOCKET = re.compile(r"[a-z0-9][a-z0-9_.-]*")
CITATION = re.compile(r"^(\d+) (.+?) (\d+)$")
WS = re.compile(r"[ \t\r\n]+")


class Refusal(Exception):
    """The producer refuses the case; args[0] says why."""


class PinError(Exception):
    """A file the build reads doesn't match its pin; args[0] says which."""


def q(name: str) -> str:
    """Clark name of an AKN element or of a cx: attribute (cx:name)."""
    if name.startswith("cx:"):
        return f"{{{CX}}}{name[3:]}"
    return f"{{{AKN}}}{name}"


def el(
    parent: etree._Element | None, tag_name: str, attrs: dict[str, str] | None = None, /, **kw: str
):
    """Add an element; attribute names may be cx:-prefixed. None values are skipped."""
    a = {**(attrs or {}), **kw}
    tag = q(tag_name)
    e = (
        etree.SubElement(parent, tag, nsmap=NSMAP)
        if parent is not None
        else etree.Element(tag, nsmap=NSMAP)
    )
    for k, v in a.items():
        if v is not None:
            e.set(q(k) if k.startswith("cx:") else k, v)
    return e


def add_text(dst: etree._Element, text: str | None) -> None:
    if not text:
        return
    if len(dst):
        dst[-1].tail = (dst[-1].tail or "") + text
    else:
        dst.text = (dst.text or "") + text


def slug(text: str) -> str:
    """A reporter abbreviation reduced to a slug (CRK spec section 5.6)."""
    s = re.sub(r"[.'’(),]", "", text.lower())
    return "-".join(s.split())


def cite_parts(cite: str) -> tuple[str, str, str]:
    m = CITATION.match(cite.strip())
    if not m:
        raise Refusal(f"citation {cite!r} is not '{{volume}} {{reporter}} {{page}}'")
    return m.group(1), m.group(2), m.group(3)


def cite_alias(cite: str) -> str:
    volume, reporter, page = cite_parts(cite)
    return f"cite:{volume}-{slug(reporter)}-{page}"


def try_cite_alias(cite: str) -> str | None:
    """The cite: alias of a citation, or None when it isn't '{volume} {reporter} {page}'."""
    try:
        return cite_alias(cite)
    except Refusal:
        return None


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def registry_uri(manifest: dict[str, Any], name: str) -> str:
    """A registry's URI: its raw file URL at the release tag (profile section 5.3)."""
    registries = manifest["registries"]
    return registries["uriBase"] + registries[name]


# Keys (spec/court-record-key.md).


def profile_for(court: dict[str, Any], decided: str) -> str | None:
    found = None
    for p in court["profiles"]:
        if p["from"] is None or p["from"] <= decided:
            found = p["profile"]
    return found


DOCKET_LABEL = re.compile(
    r"(?:(?:docket|case|appeals|appeal|record|file|gen\.|general),?\s*)?"
    r"(numbers|number|nos|no)\b\.?\s*[,:]?\s*",
    re.IGNORECASE,
)


def remove_label(s: str) -> tuple[str, bool]:
    """CRK section 5.1 step 2: s without a leading label, and whether the label was plural."""
    m = DOCKET_LABEL.match(s)
    if not m:
        return s, False
    return s[m.end() :], m.group(1).lower() in ("nos", "numbers")


def clean_docket(printed: str) -> list[str]:
    """CRK section 5.1: the docket, then the other dockets a list names; [] for no docket."""
    s = re.sub("[‐‑‒–—−]", "-", printed.strip())
    s, plural = remove_label(s)
    s = re.sub(r"(?<=\d),(?=\d{3}(?:\D|$))", "", s)
    dockets = [s]
    if plural or ";" in s:
        dockets = [d.strip() for d in re.split(r";|,|&|\band\b" if plural else ";", s)]
        dockets = [remove_label(d)[0].strip() for d in dockets if d]
        shared = re.fullmatch(r"\d+(\s+.+)", dockets[-1]) if len(dockets) > 1 else None
        if shared and re.fullmatch(r"\d+", dockets[0]):
            dockets[0] += shared.group(1)
    dockets = [d[:-1] if d.endswith(".") and not d.endswith("Orig.") else d for d in dockets]
    if not dockets or not re.search(r"\d", dockets[0]):
        return []
    return dockets


def printed_profile(cleaned: str) -> str | None:
    """CRK section 5.5; None when the profile rejects the docket."""
    s = re.sub(r"(?<=\d),(?=\s*\d)", "_", cleaned.lower()).replace(",", "")
    s = re.sub(r"\s+", "", s).replace(":", "_").replace("/", "_")
    if DOCKET.fullmatch(s) and not s.startswith("rpt."):
        return s
    return None


@dataclass
class DecisionKey:
    key: str
    court: str
    docket: str
    decided: str
    fallback: bool
    others: list[str] = field(default_factory=list)  # docket segments of a consolidated case
    ordinal: int = 1  # the decision ordinal (CRK section 7)


def decision_key(
    case: dict[str, Any], court_code: str, courts: dict[str, Any], page: list[dict[str, Any]]
) -> DecisionKey:
    """The decision key. page is every case CAP's volume records list as beginning on the case's
    first page, in printed order (CAP's file ordinal)."""
    if court_code not in courts:
        raise Refusal(f"unregistered-court: {court_code}")
    decided = case["decision_date"]
    if not decided:
        raise Refusal("no-decision-date")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", decided):
        raise Refusal(f"incomplete-date: CAP gives {decided!r}")
    try:
        date.fromisoformat(decided)
    except ValueError as e:
        raise Refusal(f"date: {decided!r}") from e
    profile = profile_for(courts[court_code], decided)
    if profile is None:
        raise Refusal(f"no-docket-profile: {court_code} on {decided}")
    if profile != "printed":
        raise Refusal(f"docket profile {profile} is not implemented by this builder")
    printed = case.get("docket_number") or ""
    dockets = clean_docket(printed)
    segment = printed_profile(dockets[0]) if dockets else None
    fallback = segment is None
    others = [] if fallback else [s for s in map(printed_profile, dockets[1:]) if s]
    ordinal = 1
    if fallback:
        official = [c["cite"] for c in case["citations"] if c["type"] == "official"]
        if not official:
            raise Refusal("no-docket" if not dockets else "docket-profile")
        volume, reporter, first = cite_parts(official[0])
        segment = f"rpt.{volume}-{slug(reporter)}-{first}"
        # CRK 5.6: the decision ordinal is the position among every decision that begins on the
        # page and shares the date, whether or not it takes the fallback.
        same_day = [c["file_name"] for c in page if c["decision_date"] == decided]
        ordinal = same_day.index(case["file_name"]) + 1
    key = f"us/{court_code}/{segment}/{decided}" + (f"~{ordinal}" if ordinal > 1 else "")
    if not KEY.fullmatch(key):
        raise Refusal(f"computed key {key!r} is not valid")
    return DecisionKey(key, court_code, segment, decided, fallback, others, ordinal)


def author_slugs(byline: str, court: str, judges: dict[str, Any]) -> list[str]:
    """Judge slugs for a byline (CRK section 10.2); [] for a per curiam byline.

    The name is the byline's text before its first comma. After case folding it must equal an
    entry's name or one of its printed forms exactly, for the court; nothing is approximated.
    """
    if per_curiam(byline):
        return []
    name = byline.split(",")[0].strip().casefold()
    found = [
        s
        for s, j in sorted(judges.items())
        if court in j["courts"]
        and name in [j["name"].casefold()] + [f["form"].casefold() for f in j.get("printed", [])]
    ]
    if len(found) != 1:
        raise Refusal(f"unregistered-author: byline {byline!r} matches {found or 'no judge'}")
    return found


def per_curiam(byline: str) -> bool:
    """Profile section 15.4: a majority byline that marks an unsigned opinion of the court."""
    return re.sub(r"[^a-z]", "", byline.lower()) in ("percuriam", "bythecourt", "thecourt")


def byline_text(author: html.HtmlElement) -> str:
    """A byline's text without the page labels CAP prints inside it."""
    parts: list[str] = [author.text or ""]
    for child in author.iterdescendants():
        if not isinstance(child.tag, str):
            parts.append(child.tail or "")
            continue
        if not (child.tag == "a" and "page-label" in (child.get("class") or "").split()):
            parts.append(child.text or "")
        parts.append(child.tail or "")
    return WS.sub(" ", "".join(parts)).strip()


# Conversion.


@dataclass
class Context:
    case: dict[str, Any]
    source: html.HtmlElement
    key: DecisionKey
    printing_ref: str  # eId of the printing CAP transcribed
    categories: dict[str, str]  # whitespace-free citation -> cites_to category
    footnotes: dict[str, html.HtmlElement]
    blocks: dict[str, dict[str, Any]] = field(default_factory=dict)
    head_notes: list[etree._Element] = field(default_factory=list)


def data_blocks(src: html.HtmlElement) -> list[list[Any]]:
    raw = src.get("data-blocks")
    return json.loads(raw) if raw else []


def set_blocks(dst: etree._Element, src: html.HtmlElement, ctx: Context) -> None:
    entries = data_blocks(src)
    if not entries:
        return
    dst.set(q("cx:blocks"), " ".join(b[0] for b in entries))
    for block_id, scan, rect in entries:
        ctx.blocks[block_id] = {"scan": scan, "rect": rect}


def label_key(label: html.HtmlElement) -> str:
    return label.get("id") or label.get("data-label") or ""


def text_before(src: html.HtmlElement, target: html.HtmlElement) -> str:
    """The text of src that comes before target, in document order."""
    out: list[str] = []

    def walk(e: html.HtmlElement) -> bool:
        if e is target:
            return True
        out.append(e.text or "")
        for c in e:
            if walk(c):
                return True
            out.append(c.tail or "")
        return False

    walk(src)
    return "".join(out)


def label_scans(src: html.HtmlElement) -> dict[str, int]:
    """Scan page of each page label in a source block, keyed by label_key.

    A block's data-blocks list its ALTO blocks in order with their scan pages. The k-th page label
    in the block begins the k-th change of scan page; a label at the very start of the block
    begins the block's first scan page. When the counts don't agree, no scan page is given.
    """
    scans: list[int] = []
    for _, scan, _ in data_blocks(src):
        if not scans or scans[-1] != scan:
            scans.append(scan)
    labels = [a for a in src.iter("a") if "page-label" in (a.get("class") or "").split()]
    if not labels:
        return {}
    offset = 1 if text_before(src, labels[0]).strip() else 0
    result = {}
    if len(scans) >= len(labels) + offset:
        for i, label in enumerate(labels):
            result[label_key(label)] = scans[i + offset]
    return result


def convert_inline(
    src: html.HtmlElement, dst: etree._Element, ctx: Context, scans: dict[str, int], part: Any
) -> None:
    """Copy src's inline content (text and children, not src's tail) into dst."""
    add_text(dst, src.text)
    for child in src:
        if not isinstance(child.tag, str):
            add_text(dst, child.tail)
            continue
        classes = (child.get("class") or "").split()
        if child.tag == "a" and "page-label" in classes:
            eop = el(
                dst,
                "eop",
                refersTo=f"#{ctx.printing_ref}",
                number=child.get("data-label"),
            )
            if label_key(child) in scans:
                eop.set(q("cx:scan"), str(scans[label_key(child)]))
                eop.set(q("cx:provenance"), "engine-output")
        elif child.tag == "a" and "footnotemark" in classes:
            note_footnote(child, dst, ctx, part)
        elif child.tag == "a" and "citation" in classes:
            citation(child, dst, ctx, scans, part)
        elif child.tag in ("em", "i"):
            convert_inline(child, el(dst, "i"), ctx, scans, part)
        elif child.tag in ("strong", "b"):
            convert_inline(child, el(dst, "b"), ctx, scans, part)
        else:
            convert_inline(child, dst, ctx, scans, part)
        add_text(dst, child.tail)


def citation(
    a: html.HtmlElement, dst: etree._Element, ctx: Context, scans: dict[str, int], part: Any
) -> None:
    """A CAP citation link: a ref to a decision, or plain text (profile sections 10 and 15.2)."""
    cite = a.get("data-cite") or ""
    paths = [p for p in (a.get("data-case-paths") or "").split(",") if p]
    href = None
    if paths:
        if len(paths) == 1:
            if not re.fullmatch(r"/[a-z0-9][a-z0-9-]*/\d+/\d+-\d{2}", paths[0]):
                raise Refusal(f"data-case-paths {paths[0]!r} is not a CAP case path")
            href = "cap:" + paths[0][1:]
        else:
            href = try_cite_alias(cite)
    else:
        category = ctx.categories.get(re.sub(r"\s", "", cite), "")
        if category == "reporters:neutral":
            href = f"neutral:{slug(cite)}"
        elif category.startswith("reporters:"):
            href = try_cite_alias(cite)
    if href is None:
        convert_inline(a, dst, ctx, scans, part)
        return
    convert_inline(a, el(dst, "ref", {"href": href, "cx:cite": cite}), ctx, scans, part)


def note_footnote(mark: html.HtmlElement, dst: etree._Element, ctx: Context, part: Any) -> None:
    target = (mark.get("href") or "").lstrip("#")
    aside = ctx.footnotes.get(target)
    if aside is None:
        raise Refusal(f"footnote mark {target!r} has no footnote")
    marker = aside.get("data-label") or mark.text_content().strip()
    if part is None:
        n = len(ctx.head_notes) + 1
        note = el(None, "note", {"eId": f"note_{n}", "marker": marker, "cx:origin": "unknown"})
        for child in aside:
            if child.tag in ("p", "blockquote"):
                p = el(note, "p")
                set_blocks(p, child, ctx)
                convert_inline(child, p, ctx, label_scans(child), None)
                normalize(p)
        ctx.head_notes.append(note)
        el(dst, "noteRef", href=f"#note_{n}", marker=marker)
        return
    part.notes += 1
    eid = f"{part.eid}__authorialNote_{part.notes}"
    note = el(dst, "authorialNote", eId=eid, marker=marker, placement="bottom")
    n = 0
    for child in aside:
        if child.tag in ("p", "blockquote"):
            n += 1
            p = el(note, "p" if child.tag == "p" else "block", eId=f"{eid}__p_{n}")
            if child.tag == "blockquote":
                p.set("name", "blockquote")
            set_blocks(p, child, ctx)
            convert_inline(child, p, ctx, label_scans(child), part)
            normalize(p)


def normalize(block: etree._Element) -> None:
    """Collapse whitespace in a block's text and strip it at the block's ends."""
    for node in block.iter():
        if node.text:
            node.text = WS.sub(" ", node.text)
        if node is not block and node.tail:
            node.tail = WS.sub(" ", node.tail)
    if block.text:
        block.text = block.text.lstrip()
    if len(block):
        last = block[-1]
        if last.tail:
            last.tail = last.tail.rstrip()
    elif block.text:
        block.text = block.text.rstrip()
    if not block.text:
        block.text = None


def head_matter_attrs(src: html.HtmlElement, eid: str) -> dict[str, str]:
    """eId, and for a paragraph CAP classes as head matter its class and origin (section 8.4)."""
    cls = (src.get("class") or "").split()
    if not cls:
        return {"eId": eid}
    return {
        "eId": eid,
        "class": cls[0] if cls[0] in HEADER_CLASSES else "headmatter",
        "cx:origin": "unknown",
    }


@dataclass
class Part:
    eid: str
    notes: int = 0


def header(ctx: Context, parent: etree._Element) -> None:
    hm = ctx.source.find("section")
    n = 0
    for src in hm if hm is not None else []:
        if src.tag == "aside":
            continue
        cls = (src.get("class") or "").split()
        kind = cls[0] if cls else "headmatter"
        n += 1
        p = el(
            parent,
            "p",
            {
                "eId": f"header__p_{n}",
                "class": kind if kind in HEADER_CLASSES else "headmatter",
                "cx:origin": "unknown",
            },
        )
        set_blocks(p, src, ctx)
        scans = label_scans(src)
        inner = p
        if kind == "parties":
            inner = el(p, "docTitle")
        elif kind == "docketnumber":
            inner = el(p, "docketNumber")
        elif kind == "court" and "court" in src.text_content().lower():
            # Profile section 6: courtType only on text that names the court. This builder
            # takes a court line that says "court" to name it, and marks the claim as derived.
            inner = el(
                p,
                "courtType",
                {"refersTo": f"#court_{ctx.key.court}", "cx:provenance": "engine-output"},
            )
        elif kind == "decisiondate":
            inner = el(p, "docDate", date=ctx.key.decided)
        convert_inline(src, inner, ctx, scans, None)
        normalize(p)
        if inner is not p:
            normalize(inner)


def parts(ctx: Context, judges: dict[str, Any], body: etree._Element) -> list[dict[str, Any]]:
    articles = ctx.source.findall("article")
    if not articles:
        raise Refusal("the case has no opinions")
    built = []
    seen: dict[tuple[str, tuple[str, ...]], int] = {}
    for article in articles:
        source_type = article.get("data-type") or ""
        author = next(
            (p for p in article if p.tag == "p" and "author" in (p.get("class") or "").split()),
            None,
        )
        if author is None:
            raise Refusal(f"a {source_type} opinion has no byline")
        byline = byline_text(author)
        if source_type not in ROLES:
            raise Refusal(f"CAP opinion type {source_type!r} has no CRK role (open question O8)")
        role = ROLES[source_type]
        if role == "opinion" and source_type == "majority" and per_curiam(byline):
            role = "per-curiam"
        authors = author_slugs(byline, ctx.key.court, judges)
        n = seen.get((role, tuple(authors)), 0) + 1
        seen[(role, tuple(authors))] = n
        segment = role + ("." + "+".join(authors) if authors else "") + (f"~{n}" if n > 1 else "")
        part_key = f"{ctx.key.key}/{segment}"
        if not KEY.fullmatch(part_key):
            raise Refusal(f"computed part key {part_key!r} is not valid")
        built.append(
            {
                "article": article,
                "author": author,
                "role": role,
                "authors": authors,
                "segment": segment,
                "key": part_key,
                "type": source_type,
            }
        )

    block = None
    for info in built:
        kids = [c for c in info["article"] if isinstance(c.tag, str) and c.tag != "aside"]
        if kids[-1] is info["author"]:
            raise Refusal(f"part {info['key']}: the byline is the writing's last element")
        block_name = "decision" if info["role"] in DECISION_ROLES else "motivation"
        if block is None or etree.QName(block).localname != block_name:
            block = el(body, block_name)
        eid = f"opinion_{info['segment']}"
        hc = el(
            block,
            "hcontainer",
            {
                "name": info["role"],
                "eId": eid,
                "cx:part": info["key"],
                "cx:authors": " ".join(info["authors"]) or None,
                "cx:sourceType": info["type"],
            },
        )
        part = Part(eid)
        heading = el(hc, "heading")
        titles = kids[: kids.index(info["author"])]
        # Profile section 7.2: paragraphs printed before the byline ("OPINION", "ORDER") are
        # spans in the heading, numbered with the part's paragraphs; the byline moves to the
        # subheading.
        n = 0
        for src in titles:
            if src.tag not in ("p", "blockquote"):
                raise Refusal(f"unexpected <{src.tag}> before a byline")
            n += 1
            if n > 1:
                el(heading, "br")
            span = el(heading, "span", head_matter_attrs(src, f"{eid}__p_{n}"))
            set_blocks(span, src, ctx)
            convert_inline(src, span, ctx, label_scans(src), part)
            normalize(span)
        byline = el(hc, "subheading") if titles else heading
        set_blocks(byline, info["author"], ctx)
        by = f"#{info['authors'][0]}" if info["authors"] else f"#court_{ctx.key.court}"
        opinion = el(byline, "opinion", by=by, type=OPINION_TYPES.get(info["role"]))
        convert_inline(info["author"], opinion, ctx, label_scans(info["author"]), part)
        normalize(opinion)
        content = el(hc, "content")
        for src in kids[kids.index(info["author"]) + 1 :]:
            if src.tag not in ("p", "blockquote"):
                raise Refusal(f"unexpected <{src.tag}> in an opinion")
            n += 1
            if src.tag == "p":
                p = el(content, "p", head_matter_attrs(src, f"{eid}__p_{n}"))
            else:
                p = el(content, "block", {"name": "blockquote", "eId": f"{eid}__p_{n}"})
            set_blocks(p, src, ctx)
            convert_inline(src, p, ctx, label_scans(src), part)
            normalize(p)
        if n == len(titles):
            raise Refusal(f"part {info['key']} has no paragraphs")
    return built


@dataclass
class Printing:
    eid: str
    cite: str
    type: str
    reporter: str
    volume: str
    first: str
    last: str | None
    text: str
    ordinal: str | None
    scans: tuple[str, int, int] | None
    nominative: list[str]


def printings(
    case: dict[str, Any], cap_volume: str, page: list[dict[str, Any]], volumes: Volumes
) -> list[Printing]:
    """The decision's printings, with @ordinal and @text from CAP's volume records (section 5.3)."""
    result = []
    nominative = [c["cite"] for c in case["citations"] if c["type"] == "nominative"]
    official = next((c["cite"] for c in case["citations"] if c["type"] == "official"), None)
    for c in case["citations"]:
        if c["type"] not in ("official", "parallel"):
            continue
        volume, reporter, first = cite_parts(c["cite"])
        eid = f"printing_{volume}-{slug(reporter)}-{first}"
        if c["type"] == "official":
            if first != case["first_page"]:
                raise Refusal(f"official citation {c['cite']} doesn't start at CAP's first_page")
            # @ordinal only when several decisions begin on the page, counted from the volume's
            # case list; CAP's file ordinal must agree with it.
            files = [p["file_name"] for p in page]
            n = files.index(case["file_name"]) + 1
            if case["file_name"] != f"{int(first):04d}-{n:02d}":
                raise Refusal(f"{case['file_name']} is decision {n} on its page in CasesMetadata")
            result.append(
                Printing(
                    eid,
                    c["cite"],
                    "official",
                    reporter,
                    volume,
                    first,
                    case["last_page"],
                    "transcribed",
                    str(n) if len(page) > 1 else None,
                    (cap_volume, case["first_page_order"], case["last_page_order"]),
                    nominative,
                )
            )
        else:
            text = parallel_text(c["cite"], official, volumes)
            result.append(
                Printing(
                    eid, c["cite"], "parallel", reporter, volume, first, None, text, None, None, []
                )
            )
    if not result or result[0].type != "official":
        raise Refusal("the case has no official citation")
    return result


def parallel_text(cite: str, official: str | None, volumes: Volumes) -> str:
    """@text of a parallel printing, from the volume records of the volume it is printed in."""
    volume, reporter, first = cite_parts(cite)
    records = volumes.get(reporter, volume)
    if records is None:
        return "unavailable"
    on_page = records.page(first)
    if any(cite in cites(p) and official in cites(p) for p in on_page):
        return "released"
    if not on_page:
        return "withheld"
    raise Refusal(
        f"{cite}: CAP's volume has a case beginning on page {first} that isn't recorded as this "
        "decision, so whether this decision's text was released can't be told"
    )


def cites(case: dict[str, Any]) -> list[str]:
    return [c["cite"] for c in case.get("citations", [])]


def build(
    entry: dict[str, Any],
    manifest: dict[str, Any],
    courts: dict[str, Any],
    judges_doc: dict[str, Any],
    volumes: Volumes,
) -> tuple[bytes, bytes, str]:
    cap = entry["cap"]
    reporter, volume, file_name = cap.split("/")
    case_bytes = read_source(entry, "json")
    html_bytes = read_source(entry, "html")
    case = json.loads(case_bytes)
    source = html.fragment_fromstring(html_bytes.decode("utf-8"))
    if case["file_name"] != file_name:
        raise Refusal(f"{cap}: file_name is {case['file_name']}")
    court_code = manifest["courts"].get(case["court"]["name"])
    if court_code is None:
        raise Refusal(f"no court registry code for CAP court {case['court']['name']!r}")
    page = volumes.case_page(reporter, volume, case)
    key = decision_key(case, court_code, courts["courts"], page)
    judges = judges_doc["judges"]
    prints = printings(case, f"{reporter}/{volume}", page, volumes)
    categories = {re.sub(r"\s", "", c["cite"]): c["category"] for c in case.get("cites_to", [])}
    footnotes = {a.get("id"): a for a in source.iter("aside") if a.get("id")}
    ctx = Context(case, source, key, prints[0].eid, categories, footnotes)

    producer = manifest["producer"]
    root = el(None, "akomaNtoso")
    judgment = el(root, "judgment", name="judgment", contains="originalVersion")
    meta = el(judgment, "meta")

    # Body first: it collects the block ids, notes and authors the metadata needs.
    hdr = etree.Element(q("header"), nsmap=NSMAP)
    header(ctx, hdr)
    body = etree.Element(q("judgmentBody"), nsmap=NSMAP)
    built = parts(ctx, judges, body)

    ident = el(meta, "identification", source=f"#{producer['eId']}")
    work = el(ident, "FRBRWork")
    el(work, "FRBRthis", value=f"crk:{key.key}")
    el(work, "FRBRuri", value=f"crk:{key.key}")
    if key.ordinal == 1:
        # Profile section 5.1.1: no akn-nc value is fixed for a key with a decision ordinal.
        el(
            work,
            "FRBRalias",
            name="akn-nc",
            value=f"/akn/us/judgment/{key.court}/{key.decided}/{key.docket}",
        )
    for p in prints:
        el(work, "FRBRalias", name="cite", value=cite_alias(p.cite), showAs=p.cite)
    for c in case["citations"]:
        if c["type"] == "neutral":
            el(
                work,
                "FRBRalias",
                name="neutral",
                value=f"neutral:{slug(c['cite'])}",
                showAs=c["cite"],
            )
        elif c["type"] == "vendor":
            el(work, "FRBRalias", name="vendor", value=c["cite"])
    el(work, "FRBRalias", name="cap", value=f"cap:{cap}")
    for other in key.others:
        el(work, "FRBRalias", name="crk", value=f"crk:us/{key.court}/{other}/{key.decided}")
    el(work, "FRBRdate", date=key.decided, name="decided")
    el(work, "FRBRauthor", href=f"#court_{key.court}")
    el(work, "FRBRcountry", value="us")
    if not key.fallback:
        printed = source.find(".//p[@class='docketnumber']")
        shown = (
            WS.sub(" ", printed.text_content()).strip()
            if printed is not None
            else case["docket_number"]
        )
        el(work, "FRBRnumber", value=key.docket, showAs=shown)
    el(work, "FRBRname", value=case["name_abbreviation"])
    expr = el(ident, "FRBRExpression")
    el(expr, "FRBRthis", value=f"crk:{key.key}")
    el(expr, "FRBRuri", value=f"crk:{key.key}")
    el(expr, "FRBRdate", date=key.decided, name="decided")
    el(expr, "FRBRauthor", href=f"#court_{key.court}")
    el(expr, "FRBRauthoritative", value="false")
    el(expr, "FRBRlanguage", language="eng")
    man = el(ident, "FRBRManifestation")
    el(man, "FRBRthis", value=f"crk:{key.key}.akn.xml")
    el(man, "FRBRuri", value=f"crk:{key.key}.akn.xml")
    el(man, "FRBRdate", date=manifest["generated"], name="generated")
    el(man, "FRBRauthor", href=f"#{producer['eId']}")
    el(man, "FRBRformat", value="application/akn+xml")

    refs = el(meta, "references", source=f"#{producer['eId']}")
    el(
        refs,
        "TLCOrganization",
        eId=f"court_{key.court}",
        href=f"{registry_uri(manifest, 'courts')}#{key.court}",
        showAs=courts["courts"][key.court]["name"],
    )
    el(
        refs,
        "TLCOrganization",
        eId=producer["eId"],
        href=producer["href"],
        showAs=producer["showAs"],
    )
    el(
        refs,
        "TLCOrganization",
        eId="org_cap",
        href="https://case.law/",
        showAs="Caselaw Access Project",
    )
    for s in sorted({a for info in built for a in info["authors"]}):
        el(
            refs,
            "TLCPerson",
            eId=s,
            href=f"{registry_uri(manifest, 'judges')}#{s}",
            showAs=judges[s]["name"],
        )
    for p in prints:
        el(refs, "TLCReference", eId=p.eid, name="printing", href=cite_alias(p.cite), showAs=p.cite)
    el(
        refs,
        "TLCReference",
        eId="source_cap",
        name="source",
        href=f"cap:{cap}",
        showAs=f"Caselaw Access Project, {cap}",
    )

    if ctx.head_notes:
        notes = el(meta, "notes", source=f"#{producer['eId']}")
        for note in ctx.head_notes:
            notes.append(note)

    prop = el(meta, "proprietary", source=f"#{producer['eId']}")
    el(prop, "cx:profile", version=manifest["profile"])
    keys = el(prop, "cx:keys", provenance="engine-output")
    el(
        keys,
        "cx:registry",
        name="courts",
        uri=registry_uri(manifest, "courts"),
        version=courts["version"],
    )
    if any(info["authors"] for info in built):
        el(
            keys,
            "cx:registry",
            name="judges",
            uri=registry_uri(manifest, "judges"),
            version=judges_doc["version"],
        )
    for p in prints:
        rec = el(
            prop,
            "cx:printing",
            {
                "ref": f"#{p.eid}",
                "type": p.type,
                "reporter": p.reporter,
                "volume": p.volume,
                "firstPage": p.first,
                "lastPage": p.last,
                "ordinal": p.ordinal,
                "text": p.text,
                # Profile section 5.3: every @text but transcribed is derived from volume records.
                "cx:provenance": None if p.text == "transcribed" else "engine-output",
            },
        )
        for nom in p.nominative:
            el(rec, "cx:cite", type="nominative", value=nom)
        if p.scans:
            el(
                rec,
                "cx:scans",
                source="#source_cap",
                volume=p.scans[0],
                first=str(p.scans[1]),
                last=str(p.scans[2]),
            )
    src = el(
        prop,
        "cx:source",
        {
            "ref": "#source_cap",
            "agent": "#org_cap",
            "record": f"cap:{cap}",
            "caseId": str(case["id"]),
            "lastUpdated": case["last_updated"],
            "sha256": case["analysis"]["sha256"],
            "method": "ocr",
        },
    )
    if "ocr_confidence" in case["analysis"]:
        el(
            src,
            "cx:confidence",
            value=str(case["analysis"]["ocr_confidence"]),
            scope="case",
            basis="CAP analysis.ocr_confidence",
        )

    judgment.append(hdr)
    judgment.append(body)

    indent(root)
    comment = (
        f"<!--\n  Built by examples/cap/build.py from the Caselaw Access Project case {cap}\n"
        f"  ({case['name_abbreviation']}, {prints[0].cite}). The text is CAP's, OCR errors"
        " included.\n-->\n"
    )
    xml = (
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        + comment.encode("utf-8")
        + etree.tostring(root, encoding="UTF-8")
        + b"\n"
    )
    doc = etree.fromstring(xml).getroottree()
    sidecar = sidecar_for(doc, ctx.blocks)
    return xml, (json.dumps(sidecar, indent=2, ensure_ascii=False) + "\n").encode("utf-8"), key.key


# Elements whose content is text: indent() leaves everything inside them as it is.
TEXT_HOSTS = {"p", "block", "heading", "subheading", "note"}


def indent(e: etree._Element, level: int = 0) -> None:
    """Indent the document's structure without adding whitespace to any text."""
    if etree.QName(e).localname in TEXT_HOSTS or not len(e):
        return
    pad = "\n" + "  " * (level + 1)
    e.text = pad
    for child in e:
        indent(child, level + 1)
        child.tail = pad
    e[-1].tail = "\n" + "  " * level


def sidecar_for(doc: etree._ElementTree, blocks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """The viewer sidecar (profile section 16.3) of a built document."""
    ns = {"a": AKN, "cx": CX}

    def value(path: str) -> str:
        return doc.xpath(f"string({path})", namespaces=ns)

    def nearest(node: etree._Element) -> str | None:
        return next((a.get("eId") for a in node.iterancestors() if a.get("eId")), None)

    parts_ = [
        {
            "eId": hc.get("eId"),
            "key": hc.get(q("cx:part")),
            "role": hc.get("name"),
            "authors": (hc.get(q("cx:authors")) or "").split(),
        }
        for hc in doc.xpath("//a:judgmentBody/*/a:hcontainer", namespaces=ns)
    ]
    prints = []
    for ref in doc.xpath("//a:references/a:TLCReference[@name='printing']", namespaces=ns):
        eid = ref.get("eId")
        (rec,) = doc.xpath(f"//cx:printing[@ref='#{eid}']", namespaces=ns)
        pages = []
        for eop in doc.xpath(f"//a:eop[@refersTo='#{eid}']", namespaces=ns):
            page: dict[str, Any] = {"number": eop.get("number"), "eId": nearest(eop)}
            if eop.get(q("cx:scan")):
                page["scan"] = int(eop.get(q("cx:scan")))
            pages.append(page)
        p: dict[str, Any] = {
            "ref": eid,
            "citation": ref.get("showAs"),
            "type": rec.get("type"),
            "firstPage": rec.get("firstPage"),
        }
        if rec.get("lastPage") is not None:
            p["lastPage"] = rec.get("lastPage")
        p["text"] = rec.get("text")
        p["pages"] = pages
        prints.append(p)
    used: list[str] = []
    for tokens in doc.xpath("//@cx:blocks", namespaces=ns):
        used += [t for t in tokens.split() if t not in used]
    return {
        "profile": value("//a:proprietary/cx:profile/@version"),
        "document": value("//a:FRBRManifestation/a:FRBRthis/@value"),
        "work": value("//a:FRBRWork/a:FRBRthis/@value"),
        "expression": value("//a:FRBRExpression/a:FRBRthis/@value"),
        "parts": parts_,
        "printings": prints,
        "blocks": {b: blocks[b] for b in used},
    }


# Sources.


def source_path(entry: dict[str, Any], kind: str) -> Path:
    reporter, volume, file_name = entry["cap"].split("/")
    sub, ext = ("cases", "json") if kind == "json" else ("html", "html")
    return SOURCE / reporter / volume / sub / f"{file_name}.{ext}"


def read_source(entry: dict[str, Any], kind: str) -> bytes:
    path = source_path(entry, kind)
    data = path.read_bytes()
    want = entry["source"][kind]["sha256"]
    if sha256(data) != want:
        raise PinError(f"{path.relative_to(ROOT)}: SHA-256 {sha256(data)}, manifest says {want}")
    return data


def fetch(entry: dict[str, Any]) -> None:
    for kind in ("json", "html"):
        path = source_path(entry, kind)
        url = entry["source"][kind]["url"]
        # static.case.law answers urllib's default User-Agent with 403 Forbidden.
        with http_get(url) as r:
            data = r.read()
        if sha256(data) != entry["source"][kind]["sha256"]:
            raise PinError(f"{url}: SHA-256 {sha256(data)} differs from the manifest")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


# Volume records: CAP's VolumeMetadata.json and CasesMetadata.json, read from data.stare.pub.


def http_get(url: str, headers: dict[str, str] | None = None, method: str = "GET"):
    """Open url, retrying a few times on a server error or a dropped connection."""
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, **(headers or {})}, method=method
    )
    for attempt in range(4):
        try:
            return urllib.request.urlopen(request, timeout=60)
        except urllib.error.HTTPError as e:
            if (e.code < 500 and e.code != 429) or attempt == 3:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 3:
                raise
        time.sleep(2**attempt)
    raise AssertionError("unreachable")


class RangeFile(io.RawIOBase):
    """A remote zip read with HTTP range requests, each response checked against the pinned
    ETag and size, so the reads can't mix two versions of the file."""

    def __init__(self, url: str, etag: str, size: int) -> None:
        self.url, self.etag, self.size, self.pos = url, etag, size, 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        self.pos = {io.SEEK_SET: 0, io.SEEK_CUR: self.pos, io.SEEK_END: self.size}[whence] + offset
        return self.pos

    def readinto(self, buf: Any) -> int:
        if self.pos >= self.size or not len(buf):
            return 0
        end = min(self.pos + len(buf), self.size) - 1
        with http_get(self.url, {"Range": f"bytes={self.pos}-{end}"}) as r:
            etag, total = r.headers.get("ETag"), (r.headers.get("Content-Range") or "")
            data = r.read()
        if r.status != 206 or etag != self.etag or not total.endswith(f"/{self.size}"):
            raise PinError(
                f"{self.url}: served ETag {etag} and range {total!r} (status {r.status}); "
                f"volumes.lock.json pins ETag {self.etag}, {self.size} bytes"
            )
        if len(data) != end - self.pos + 1:
            raise PinError(f"{self.url}: short range response")
        buf[: len(data)] = data
        self.pos += len(data)
        return len(data)


@dataclass
class VolumeRecords:
    """One CAP volume's records: VolumeMetadata.json and CasesMetadata.json."""

    name: str  # slug/volume
    volume: dict[str, Any]
    cases: list[dict[str, Any]]

    def page(self, first: str) -> list[dict[str, Any]]:
        """Every case that begins on the page, in printed order (CAP's file ordinal)."""
        return sorted(
            (c for c in self.cases if c["first_page"] == first), key=lambda c: c["file_name"]
        )


class Volumes:
    """CAP volume records pinned by volumes.lock.json, cached under .cache/stare/."""

    def __init__(self, lock: dict[str, Any], cache: Path = CACHE) -> None:
        self.lock, self.cache = lock, cache
        self.loaded: dict[str, VolumeRecords | None] = {}

    def get(self, reporter: str, volume: str) -> VolumeRecords | None:
        """The records of the volume a citation's reporter abbreviation names; None when CAP
        holds no such volume."""
        slugs = self.lock["reporters"].get(reporter)
        if slugs is None:
            raise PinError(f"reporter {reporter!r} isn't in volumes.lock.json; run --lock")
        return self.records(slugs, volume)

    def records(self, slug_: str, volume: str) -> VolumeRecords | None:
        name = f"{slug_}/{volume}"
        if name not in self.loaded:
            if name not in self.lock["volumes"]:
                raise PinError(f"volume {name} isn't in volumes.lock.json; run --lock")
            pin = self.lock["volumes"][name]
            if pin is None:
                self.loaded[name] = None
            else:
                data = self.members(name, pin)
                record = json.loads(data["metadata/VolumeMetadata.json"])
                if record["volume_number"] != volume:
                    raise Refusal(
                        f"{name}: VolumeMetadata.json is volume {record['volume_number']}"
                    )
                cases = json.loads(data["metadata/CasesMetadata.json"])
                self.loaded[name] = VolumeRecords(name, record, cases)
        return self.loaded[name]

    def case_page(self, slug_: str, volume: str, case: dict[str, Any]) -> list[dict[str, Any]]:
        """The cases that begin on a case's first page, from the records of the volume CAP
        published it in; the case itself must be among them."""
        records = self.records(slug_, volume)
        if records is None:
            raise PinError(f"volumes.lock.json says CAP holds no volume {slug_}/{volume}")
        page = records.page(case["first_page"])
        if not any(c["file_name"] == case["file_name"] and c["id"] == case["id"] for c in page):
            raise Refusal(f"{records.name}: CasesMetadata.json doesn't list {case['file_name']}")
        return page

    def members(self, name: str, pin: dict[str, Any]) -> dict[str, bytes]:
        """The volume's record files, from the cache or by range requests, checked against the
        lock."""
        result, archive = {}, None
        for member in VOLUME_RECORDS:
            path = self.cache / "cap" / name / member
            want = pin["members"][member]
            if path.exists() and sha256(path.read_bytes()) == want:
                result[member] = path.read_bytes()
                continue
            if archive is None:
                remote = RangeFile(pin["url"], pin["etag"], pin["size"])
                archive = zipfile.ZipFile(io.BufferedReader(remote, 1 << 16))
            data = archive.read(member)
            if sha256(data) != want:
                raise PinError(
                    f"{pin['url']}: {member} has SHA-256 {sha256(data)}, lock pins {want}"
                )
            path.parent.mkdir(parents=True, exist_ok=True)
            partial = path.with_name(path.name + ".part")
            partial.write_bytes(data)
            partial.replace(path)
            result[member] = data
        return result


def make_lock(manifest: dict[str, Any]) -> dict[str, Any]:
    """Pin the volume records every example needs, as data.stare.pub serves them now."""
    with http_get(REPORTERS) as r:
        reporters_map = json.load(r)
    with http_get(INDEX_MANIFEST) as r:
        index = json.load(r)
    reporters: dict[str, str] = {}
    wanted: list[tuple[str, str]] = []
    for entry in manifest["examples"]:
        cap_slug, cap_volume, _ = entry["cap"].split("/")
        case = json.loads(read_source(entry, "json"))
        wanted.append((cap_slug, cap_volume))
        for c in case["citations"]:
            if c["type"] not in ("official", "parallel"):
                continue
            volume, reporter, _ = cite_parts(c["cite"])
            slugs = reporters_map["abbreviations"].get(reporter, [])
            if len(slugs) != 1:
                raise Refusal(f"reporters.json maps {reporter!r} to {slugs}, not one slug")
            if c["type"] == "official" and (slugs[0], volume) != (cap_slug, cap_volume):
                raise Refusal(f"{entry['cap']}: official citation {c['cite']} is in {slugs[0]}")
            reporters[reporter] = slugs[0]
            wanted.append((slugs[0], volume))
    volumes: dict[str, Any] = {}
    for slug_, volume in sorted(set(wanted)):
        name = f"{slug_}/{volume}"
        if volume in index["parts"].get(slug_, {}):
            raise Refusal(f"{name} is split over several folders; this builder reads one zip")
        url = CAP_ZIP.format(slug=slug_, volume=volume)
        try:
            with http_get(url, method="HEAD") as r:
                etag, size = r.headers["ETag"], int(r.headers["Content-Length"])
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
            volumes[name] = None
            continue
        archive = zipfile.ZipFile(io.BufferedReader(RangeFile(url, etag, size), 1 << 16))
        members = {m: sha256(archive.read(m)) for m in VOLUME_RECORDS}
        volumes[name] = {"url": url, "etag": etag, "size": size, "members": members}
    return {
        "description": (
            "Pins the CAP volume records examples/cap/build.py reads: for each volume, the zip on "
            "data.stare.pub (its URL, the ETag and size the server gave, which every range "
            "response must match) and the SHA-256 of each member read. null: data.stare.pub has "
            "no zip for that volume, so CAP holds none. reporters maps each reporter abbreviation "
            "the examples cite to its CAP slug, from reporters.json. Written by build.py --lock."
        ),
        "reporters": dict(sorted(reporters.items())),
        "reportersFrom": {
            "url": REPORTERS,
            "indexBuild": reporters_map["generated_from"]["index_build"]["version"],
        },
        "volumes": volumes,
    }


def stem(key: str) -> str:
    return key.replace("/", "-")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--fetch", action="store_true", help="download the source files first")
    parser.add_argument("--check", action="store_true", help="fail if a committed file differs")
    parser.add_argument(
        "--lock", action="store_true", help="pin the CAP volume records again first"
    )
    args = parser.parse_args(argv)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    courts = json.loads(COURTS.read_text(encoding="utf-8"))
    judges = json.loads((ROOT / manifest["registries"]["judges"]).read_text(encoding="utf-8"))
    if courts["version"] != manifest["registries"]["courtsVersion"]:
        print(
            f"court registry is {courts['version']}, "
            f"manifest pins {manifest['registries']['courtsVersion']}",
            file=sys.stderr,
        )
        return 1
    if args.fetch:
        for entry in manifest["examples"]:
            fetch(entry)
    if args.lock:
        lock = make_lock(manifest)
        LOCK.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    volumes = Volumes(json.loads(LOCK.read_text(encoding="utf-8")))
    failed = 0
    for entry in manifest["examples"]:
        try:
            xml, sidecar, key = build(entry, manifest, courts, judges, volumes)
        except Refusal as e:
            print(f"{entry['cap']}: refused: {e}", file=sys.stderr)
            failed += 1
            continue
        except PinError as e:
            print(f"{entry['cap']}: {e}", file=sys.stderr)
            failed += 1
            continue
        if entry.get("key") != key:
            print(f"{entry['cap']}: key {key}, manifest says {entry.get('key')}", file=sys.stderr)
            failed += 1
        for path, data in (
            (HERE / f"{stem(key)}.akn.xml", xml),
            (HERE / f"{stem(key)}.sidecar.json", sidecar),
        ):
            if args.check:
                if not path.exists() or path.read_bytes() != data:
                    print(f"{path.relative_to(ROOT)}: differs from a rebuild", file=sys.stderr)
                    failed += 1
            else:
                path.write_bytes(data)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
