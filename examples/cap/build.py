"""Build the CAP examples: Akoma Ntoso documents and sidecars from Caselaw Access Project cases.

Usage:
    uv run python examples/cap/build.py          # rebuild every example from examples/cap/source/
    uv run python examples/cap/build.py --fetch  # download the source files, then rebuild
    uv run python examples/cap/build.py --check  # rebuild in memory; fail if a file differs

The examples and their sources are listed in examples/cap/manifest.json. Each source file is checked
against the SHA-256 recorded there before it is read. The build is deterministic: the same sources,
manifest, judge fixture and court registry give byte-identical output.

This is a producer of spec/akoma-ntoso-profile.md written for these examples, not a general CAP
converter. It refuses, rather than guesses, whenever a case needs something the profile or the court
record key spec leaves open, and says why.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.request
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


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# Keys (spec/court-record-key.md).


def profile_for(court: dict[str, Any], decided: str) -> str | None:
    found = None
    for p in court["profiles"]:
        if p["from"] is None or p["from"] <= decided:
            found = p["profile"]
    return found


def clean_docket(printed: str) -> str:
    """CRK section 5.1."""
    s = printed.strip()
    s = re.sub(r"^(No\.|Nos\.|Docket No\.|Case No\.)\s*", "", s)
    s = re.sub("[‐‑‒–—−]", "-", s)
    if s.endswith(".") and not s.endswith("Orig."):
        s = s[:-1]
    return s


def printed_profile(cleaned: str) -> str | None:
    """CRK section 5.5; None when the profile rejects the docket."""
    s = re.sub(r"\s+", "", cleaned.lower()).replace(":", "_").replace("/", "_")
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
    notes: list[str] = field(default_factory=list)


def decision_key(case: dict[str, Any], court_code: str, courts: dict[str, Any]) -> DecisionKey:
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
    cleaned = clean_docket(printed)
    segment = printed_profile(cleaned) if cleaned else None
    fallback = segment is None
    if fallback:
        official = [c["cite"] for c in case["citations"] if c["type"] == "official"]
        if not official:
            raise Refusal("no-docket" if not cleaned else "docket-profile")
        volume, reporter, page = cite_parts(official[0])
        segment = f"rpt.{volume}-{slug(reporter)}-{page}"
        if not case["file_name"].endswith("-01"):
            # CRK 5.6: several decisions on one page that share a date take decision ordinals in
            # printed order. Whether that applies when only one of them falls back is open, so
            # this builder doesn't decide it.
            raise Refusal("reporter fallback for a decision that isn't first on its page")
    key = f"us/{court_code}/{segment}/{decided}"
    if not KEY.fullmatch(key):
        raise Refusal(f"computed key {key!r} is not valid")
    return DecisionKey(key, court_code, segment, decided, fallback)


def author_slugs(byline: str, court: str, judges: dict[str, Any]) -> list[str]:
    """Judge slugs for a byline, by the registry's printed surnames; [] for none."""
    if per_curiam(byline):
        return []
    surname = re.sub(r"[^a-z]", "", byline.split(",")[0].lower())
    found = [
        s
        for s, j in sorted(judges.items())
        if court in j["courts"] and surname in [b.lower() for b in j["bylines"]]
    ]
    if len(found) != 1:
        raise Refusal(f"unregistered-author: byline {byline!r} matches {found or 'no judge'}")
    return found


def per_curiam(byline: str) -> bool:
    return re.sub(r"[^a-z]", "", byline.lower()) == "percuriam"


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
    """A CAP citation link: a ref to a decision (profile section 10), or plain text."""
    cite = a.get("data-cite") or ""
    category = ctx.categories.get(re.sub(r"\s", "", cite), "")
    paths = [p for p in (a.get("data-case-paths") or "").split(",") if p]
    href = None
    if category.startswith("reporters:"):
        if len(paths) == 1 and re.fullmatch(r"/[a-z0-9][a-z0-9-]*/\d+/\d+-\d{2}", paths[0]):
            href = "cap:" + paths[0][1:]
        else:
            try:
                href = cite_alias(cite)
            except Refusal:
                href = None
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


@dataclass
class Part:
    eid: str
    notes: int = 0


def hoist_page_breaks(p: etree._Element) -> list[etree._Element]:
    """Detach the page breaks at the very start of p; refuse a page break later in p."""
    moved = []
    while len(p) and not (p.text or "").strip() and etree.QName(p[0]).localname == "eop":
        eop = p[0]
        p.text = (p.text or "") + (eop.tail or "")
        eop.tail = None
        p.remove(eop)
        moved.append(eop)
    if p.xpath(".//a:eop", namespaces={"a": AKN}):
        raise Refusal("a page break inside a paragraph printed before the byline")
    if not p.text:
        p.text = None
    return moved


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
            inner = el(p, "courtType", refersTo=f"#court_{ctx.key.court}")
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
        byline = author.text_content().strip()
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
        set_blocks(heading, info["author"], ctx)
        by = f"#{info['authors'][0]}" if info["authors"] else f"#court_{ctx.key.court}"
        opinion = el(heading, "opinion", by=by, type=OPINION_TYPES.get(info["role"]))
        convert_inline(info["author"], opinion, ctx, label_scans(info["author"]), part)
        normalize(opinion)
        content = el(hc, "content")
        n = 0
        before_byline = True
        hoisted: list[etree._Element] = []
        for src in info["article"]:
            if src is info["author"]:
                before_byline = False
                continue
            if src.tag == "aside":
                continue
            if src.tag not in ("p", "blockquote"):
                raise Refusal(f"unexpected <{src.tag}> in an opinion")
            n += 1
            cls = src.get("class")
            if src.tag == "p":
                p = el(content, "p", {"eId": f"{eid}__p_{n}", "class": cls})
            else:
                p = el(content, "block", {"name": "blockquote", "eId": f"{eid}__p_{n}"})
            set_blocks(p, src, ctx)
            convert_inline(src, p, ctx, label_scans(src), part)
            normalize(p)
            if before_byline:
                hoisted += hoist_page_breaks(p)
        # A paragraph CAP prints before the byline ("OPINION", "ORDER") follows the heading here,
        # because hcontainer puts its heading first. A page break at the start of such a paragraph
        # moves to the start of the heading, so that the byline stays on the page it was printed on.
        for i, eop in enumerate(hoisted):
            heading.insert(i, eop)
        if n == 0:
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


def printings(case: dict[str, Any], cap_volume: str, entry: dict[str, Any]) -> list[Printing]:
    result = []
    nominative = [c["cite"] for c in case["citations"] if c["type"] == "nominative"]
    for c in case["citations"]:
        if c["type"] not in ("official", "parallel"):
            continue
        volume, reporter, page = cite_parts(c["cite"])
        eid = f"printing_{volume}-{slug(reporter)}-{page}"
        transcribed = c["type"] == "official"
        if transcribed:
            if page != case["first_page"]:
                raise Refusal(f"official citation {c['cite']} doesn't start at CAP's first_page")
            # @ordinal only when several decisions begin on the page (profile section 5.3).
            n = int(case["file_name"].split("-")[1])
            ordinal = str(n) if n > 1 or entry.get("pageShared") else None
            result.append(
                Printing(
                    eid,
                    c["cite"],
                    "official",
                    reporter,
                    volume,
                    page,
                    case["last_page"],
                    "transcribed",
                    ordinal,
                    (cap_volume, case["first_page_order"], case["last_page_order"]),
                    nominative,
                )
            )
        else:
            status = entry.get("printings", {}).get(c["cite"])
            if status is None:
                raise Refusal(f"the manifest doesn't say whether {c['cite']} is held by a source")
            result.append(
                Printing(
                    eid,
                    c["cite"],
                    "parallel",
                    reporter,
                    volume,
                    page,
                    None,
                    status["text"],
                    None,
                    None,
                    [],
                )
            )
    if not result or result[0].type != "official":
        raise Refusal("the case has no official citation")
    return result


def build(
    entry: dict[str, Any],
    manifest: dict[str, Any],
    courts: dict[str, Any],
    judges_doc: dict[str, Any],
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
    key = decision_key(case, court_code, courts["courts"])
    judges = judges_doc["judges"]
    prints = printings(case, f"{reporter}/{volume}", entry)
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
    el(work, "FRBRthis", value=key.key)
    el(work, "FRBRuri", value=key.key)
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
    el(expr, "FRBRthis", value=key.key)
    el(expr, "FRBRuri", value=key.key)
    el(expr, "FRBRdate", date=key.decided, name="decided")
    el(expr, "FRBRauthor", href=f"#court_{key.court}")
    el(expr, "FRBRauthoritative", value="false")
    el(expr, "FRBRlanguage", language="eng")
    man = el(ident, "FRBRManifestation")
    el(man, "FRBRthis", value=f"{key.key}.akn.xml")
    el(man, "FRBRuri", value=f"{key.key}.akn.xml")
    el(man, "FRBRdate", date=manifest["generated"], name="generated")
    el(man, "FRBRauthor", href=f"#{producer['eId']}")
    el(man, "FRBRformat", value="application/akn+xml")

    refs = el(meta, "references", source=f"#{producer['eId']}")
    el(
        refs,
        "TLCOrganization",
        eId=f"court_{key.court}",
        href=f"{manifest['registries']['courts']}#{key.court}",
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
            href=f"{manifest['registries']['judges']}#{s}",
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
        uri=manifest["registries"]["courts"],
        version=courts["version"],
    )
    if any(info["authors"] for info in built):
        el(
            keys,
            "cx:registry",
            name="judges",
            uri=manifest["registries"]["judges"],
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
TEXT_HOSTS = {"p", "block", "heading", "note"}


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
        raise Refusal(f"{path.relative_to(ROOT)}: SHA-256 {sha256(data)}, manifest says {want}")
    return data


def fetch(entry: dict[str, Any]) -> None:
    for kind in ("json", "html"):
        path = source_path(entry, kind)
        url = entry["source"][kind]["url"]
        # static.case.law answers urllib's default User-Agent with 403 Forbidden.
        request = urllib.request.Request(url, headers={"User-Agent": "exemplar-cap-examples"})
        with urllib.request.urlopen(request, timeout=60) as r:
            data = r.read()
        if sha256(data) != entry["source"][kind]["sha256"]:
            raise Refusal(f"{url}: SHA-256 {sha256(data)} differs from the manifest")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def stem(key: str) -> str:
    return key.replace("/", "-")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--fetch", action="store_true", help="download the source files first")
    parser.add_argument("--check", action="store_true", help="fail if a committed file differs")
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
    failed = 0
    for entry in manifest["examples"]:
        try:
            if args.fetch:
                fetch(entry)
            xml, sidecar, key = build(entry, manifest, courts, judges)
        except Refusal as e:
            print(f"{entry['cap']}: refused: {e}", file=sys.stderr)
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
