"""Byte fidelity checks for XML value edits and appended runway fields."""

import xml.etree.ElementTree as ET

import pytest

from simple_database_toolkit.services.xml_edit import patch_xml


@pytest.mark.parametrize("bom", [b"", b"\xef\xbb\xbf"])
def test_preserves_declaration_comments_entities_and_crlf(bom: bytes) -> None:
    original = bom + (
        b'<?xml version="1.0" encoding="UTF-8"?>\r\n'
        b'<!-- <Data>999</Data> -->\r\n<Records>\r\n'
        b'  <Record Num="1" note="a&gt;b">\r\n'
        b'    <Data>  12.500  </Data>\r\n'
        b'    <Name>Caf\xc3\xa9 &amp; Hangar</Name>\r\n'
        b'  </Record>\r\n</Records>\r\n'
    )
    updated = ET.fromstring(original)
    updated.find("Record/Data").text = "15.000"
    assert patch_xml(original, updated) == original.replace(b"12.500", b"15.000")


def test_no_change_returns_identical_bytes() -> None:
    original = b'<Records><!-- keep --><Data>1&#48;</Data><Empty /></Records>\r\n'
    assert patch_xml(original, ET.fromstring(original)) == original


def test_empty_field_expands_only_its_tag() -> None:
    original = b'<Records><Data /><Name>Untouched</Name></Records>'
    updated = ET.fromstring(original)
    updated.find("Data").text = "20"
    assert patch_xml(original, updated) == original.replace(b"<Data />", b"<Data >20</Data>")


def test_comment_inside_changed_value_is_retained() -> None:
    original = b'<Records><Data>1<!-- preserve -->0</Data></Records>'
    updated = ET.fromstring(original)
    updated.find("Data").text = "20"
    assert patch_xml(original, updated) == b'<Records><Data>20<!-- preserve --></Data></Records>'


@pytest.mark.parametrize("original, expected", [
    (b'<Records><Record><Type>8</Type></Record></Records>',
     b'<Records><Record><Type>8</Type><Data>20</Data></Record></Records>'),
    (b'<Records>\r\n  <Record>\r\n    <Type>8</Type>\r\n  </Record>\r\n</Records>\r\n',
     b'<Records>\r\n  <Record>\r\n    <Type>8</Type>\r\n    <Data>20</Data>\r\n  </Record>\r\n</Records>\r\n'),
])
def test_appended_field_uses_existing_layout(original: bytes, expected: bytes) -> None:
    updated = ET.fromstring(original)
    ET.SubElement(updated.find("Record"), "Data").text = "20"
    assert patch_xml(original, updated) == expected


@pytest.mark.parametrize("change", ["attribute", "remove", "reorder", "cdata"])
def test_unsupported_edits_fail_before_write(change: str) -> None:
    original = b'<Records><Data><![CDATA[10]]></Data><Name>Keep</Name></Records>'
    updated = ET.fromstring(original)
    if change == "attribute":
        updated.set("Changed", "1")
    elif change == "remove":
        updated.remove(updated.find("Name"))
    elif change == "reorder":
        updated[:] = list(reversed(updated[:]))
    else:
        updated.find("Data").text = "20"
    with pytest.raises(ValueError):
        patch_xml(original, updated)
