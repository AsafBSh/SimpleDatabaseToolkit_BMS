"""Audit installed XML read-only and run service tests on temporary copies."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(root: Path) -> tuple[dict[str, object], dict[Path, str]]:
    paths = sorted(root.rglob("*.xml"))
    roots: Counter[str] = Counter()
    formats: Counter[str] = Counter()
    errors: list[dict[str, str]] = []
    airbases: list[str] = []
    hashes: dict[Path, str] = {}
    total_bytes = 0
    for path in paths:
        data = path.read_bytes()
        total_bytes += len(data)
        hashes[path] = hashlib.sha256(data).hexdigest()
        formats["utf8_bom" if data.startswith(b"\xef\xbb\xbf") else "no_bom"] += 1
        formats["crlf" if b"\r\n" in data else "lf_or_no_newlines"] += 1
        if b"<!--" in data:
            formats["with_comments"] += 1
        try:
            parsed = ET.fromstring(data)
        except ET.ParseError as exc:
            errors.append({"file": str(path.relative_to(root)), "error": str(exc)})
            continue
        roots[parsed.tag] += 1
        expected = {"FED": "FEDRecords", "PHD": "PHDRecords", "PDX": "PDRecords", "OCD": "OCDRecords"}
        prefix = path.stem.split("_")[0].upper()
        if prefix in expected and parsed.tag != expected[prefix]:
            errors.append({"file": str(path.relative_to(root)), "error": f"Expected {expected[prefix]}, found {parsed.tag}"})
        identities = [item.get("Num") for item in parsed if item.get("Num") is not None]
        if len(identities) != len(set(identities)):
            errors.append({"file": str(path.relative_to(root)), "error": "Duplicate record Num attributes"})
        if parsed.tag == "PHDRecords" and any(item.findtext("Type") == "8" for item in parsed.findall("PHD")):
            airbases.append(str(path.parent.relative_to(root)))
    return {
        "objects_root": str(root), "files": len(paths), "bytes": total_bytes,
        "root_elements": dict(roots), "formats": dict(formats),
        "parse_or_identity_errors": errors, "airbases": airbases,
    }, hashes


class ResultsPlugin:
    def __init__(self) -> None:
        self.tests: list[dict[str, object]] = []

    def pytest_runtest_logreport(self, report) -> None:
        if report.when == "call" or report.failed:
            self.tests.append({
                "test": report.nodeid, "outcome": report.outcome,
                "details": str(report.longrepr) if report.failed else "",
                "properties": dict(report.user_properties),
            })


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--objects", action="append", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--inventory-only", action="store_true")
    args = parser.parse_args()
    roots = [root.resolve() for root in args.objects]
    output = args.report.resolve()
    if any(output.is_relative_to(root) for root in roots):
        parser.error("Report must be outside the installed theater folders.")
    for root in roots:
        if not (root / "Falcon4_CT.xml").is_file():
            parser.error(f"Objects folder has no Falcon4_CT.xml: {root}")
    audits = []
    hashes: dict[Path, str] = {}
    for root in roots:
        audit, root_hashes = inventory(root)
        audits.append(audit)
        hashes.update(root_hashes)
        print(f"Read-only inventory: {root}: {audit['files']} XML files, {len(audit['airbases'])} airbases")
    plugin = ResultsPlugin()
    exit_code = 0
    try:
        if not args.inventory_only:
            import pytest

            test_file = Path(__file__).resolve().parents[1] / "tests" / "integration" / "test_installed_theater_xml.py"
            pytest_args = [str(test_file), "-q", "--tb=short"]
            for root in roots:
                pytest_args.extend(["--bms-objects", str(root)])
            exit_code = int(pytest.main(pytest_args, plugins=[plugin]))
    finally:
        altered = [str(path) for path, original in hashes.items()
                   if not path.is_file() or fingerprint(path) != original]
        added = [str(path) for root in roots for path in root.rglob("*.xml")
                 if path not in hashes]
        result = {
            "date_utc": datetime.now(timezone.utc).isoformat(),
            "audit": audits, "tests": plugin.tests, "pytest_exit_code": exit_code,
            "source_hashes_verified": len(hashes), "altered_sources": altered,
            "added_sources": added,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(f"Verified {len(hashes)} installed XML hashes; altered {len(altered)}, added {len(added)}. Report: {output}")
    if altered or added or any(audit["parse_or_identity_errors"] for audit in audits):
        return 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
