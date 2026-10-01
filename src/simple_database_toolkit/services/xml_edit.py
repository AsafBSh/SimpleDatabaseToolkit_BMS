"""Apply leaf-value XML edits without reserializing the original document."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from xml.parsers import expat
from xml.sax.saxutils import escape


@dataclass
class _Span:
    tag: str
    start: int
    content: int
    self_closing: bool
    close: int = 0
    end: int = 0
    children: list[_Span] = field(default_factory=list)
    comments: list[tuple[int, int]] = field(default_factory=list)


def _tag_end(data: bytes, start: int) -> int:
    quote = 0
    for index in range(start, len(data)):
        value = data[index]
        if quote:
            if value == quote:
                quote = 0
        elif value in (34, 39):
            quote = value
        elif value == 62:
            return index + 1
    raise ValueError("XML tag is not terminated.")


def _spans(data: bytes) -> _Span:
    parser = expat.ParserCreate()
    stack: list[_Span] = []
    document: list[_Span] = []

    def start(tag: str, _attributes) -> None:
        offset = parser.CurrentByteIndex
        end = _tag_end(data, offset)
        node = _Span(tag, offset, end, data[offset:end].endswith(b"/>"))
        if stack:
            stack[-1].children.append(node)
        else:
            document.append(node)
        stack.append(node)

    def end(_tag: str) -> None:
        node = stack.pop()
        node.close = node.content if node.self_closing else parser.CurrentByteIndex
        node.end = node.content if node.self_closing else _tag_end(data, node.close)

    def comment(_text: str) -> None:
        if stack:
            offset = parser.CurrentByteIndex
            stack[-1].comments.append((offset, data.index(b"-->", offset) + 3))

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CommentHandler = comment
    parser.Parse(data, True)
    return document[0]


def _semantics(node: ET.Element):
    return (
        node.tag, sorted(node.attrib.items()), (node.text or "").strip(),
        tuple(_semantics(child) for child in node if isinstance(child.tag, str)),
    )


def patch_xml(original: bytes, updated: ET.Element) -> bytes:
    """Preserve all original bytes except edited values and appended leaf fields.

    Unsupported structural/attribute changes fail before any write. Expat's
    byte positions distinguish actual tags from tags inside comments.
    """
    old_root = ET.fromstring(original)
    spans = _spans(original)
    edits: list[tuple[int, int, bytes]] = []
    newline = b"\r\n" if b"\r\n" in original else b"\n"

    def walk(old: ET.Element, new: ET.Element, span: _Span) -> None:
        if old.tag != new.tag or old.attrib != new.attrib or span.tag != old.tag:
            raise ValueError("XML record order, tags, and attributes must be preserved.")
        old_children = list(old)
        new_children = [child for child in new if isinstance(child.tag, str)]
        if len(new_children) < len(old_children):
            raise ValueError("XML field removal is not supported.")
        for old_child, new_child, child_span in zip(old_children, new_children, span.children, strict=False):
            walk(old_child, new_child, child_span)

        if not old_children and (old.text or "") != (new.text or ""):
            value = escape(new.text or "").encode("utf-8")
            if span.self_closing:
                opening = original[span.start:span.content - 2] + b">"
                edits.append((span.start, span.end, opening + value + b"</" + span.tag.encode() + b">"))
            else:
                gaps: list[tuple[int, int]] = []
                position = span.content
                for start, end in span.comments:
                    gaps.append((position, start))
                    position = end
                gaps.append((position, span.close))
                usable = [gap for gap in gaps if original[gap[0]:gap[1]].strip()]
                targets = usable or [gaps[-1]]
                for index, (start, end) in enumerate(targets):
                    text = original[start:end]
                    if b"<" in text:
                        raise ValueError("Editing mixed XML content or CDATA is not supported.")
                    match = re.fullmatch(rb"(\s*)(.*?)(\s*)", text, re.DOTALL)
                    assert match is not None
                    replacement = match[1] + (value if index == 0 else b"") + match[3]
                    edits.append((start, end, replacement))

        additions = new_children[len(old_children):]
        if additions:
            if span.self_closing:
                raise ValueError("Appending fields to an empty XML record is not supported.")
            line_start = original.rfind(b"\n", span.content, span.close) + 1
            parent_indent = original[line_start:span.close]
            multiline = line_start >= span.content and not parent_indent.strip()
            indent = parent_indent + b"    "
            if span.children and multiline:
                child_start = span.children[0].start
                child_line = original.rfind(b"\n", span.content, child_start) + 1
                candidate = original[child_line:child_start]
                if not candidate.strip() and len(candidate) > len(parent_indent):
                    indent = candidate
            extra = b""
            for child in additions:
                if list(child) or child.attrib:
                    raise ValueError("Only plain leaf XML fields may be appended.")
                tag = str(child.tag).encode("utf-8")
                value = escape(child.text or "").encode("utf-8")
                extra += (indent if multiline else b"") + b"<" + tag + b">" + value + b"</" + tag + b">" + (newline if multiline else b"")
            insert = line_start if multiline else span.close
            edits.append((insert, insert, extra))

    walk(old_root, updated, spans)
    output = original
    previous = len(original) + 1
    for start, end, replacement in sorted(edits, reverse=True):
        if end > previous:
            raise ValueError("XML edits overlap.")
        output = output[:start] + replacement + output[end:]
        previous = start
    if _semantics(ET.fromstring(output)) != _semantics(updated):
        raise ValueError("Patched XML does not match the intended values.")
    return output
