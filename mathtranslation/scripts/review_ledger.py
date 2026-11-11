#!/usr/bin/env python3
"""Create and maintain a source-to-translation review ledger.

The ledger separates source-page coverage, semantic correspondence, repair
disposition, and final-PDF evidence. It records immutable PDF snapshots and
reports stale evidence without deciding whether a mathematical translation is
correct.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
PAGE_FIELDS = [
    "source_physical_page",
    "source_printed_page",
    "in_scope",
    "source_inventory_status",
    "translation_inventory_status",
    "challenge_status",
    "unit_count",
    "finding_ids",
    "notes",
]
UNIT_FIELDS = [
    "unit_id",
    "source_physical_page",
    "source_region",
    "source_printed_page",
    "kind",
    "source_identifier",
    "translation_tex_file",
    "translation_anchor",
    "translation_pdf_physical_page",
    "translation_printed_page",
    "semantic_status",
    "semantic_source_sha256",
    "semantic_tex_sha256",
    "repair_status",
    "pdf_status",
    "pdf_snapshot",
    "evidence_path",
    "finding_id",
    "notes",
]
PAGE_INVENTORY_STATUSES = {"not_started", "inventoried", "not_applicable", "unresolved"}
CHALLENGE_STATUSES = {"not_started", "reviewed", "not_applicable", "unresolved"}
SEMANTIC_STATUSES = {
    "not_started",
    "matched",
    "defect",
    "intentional_with_reason",
    "source_issue_retained",
    "unresolved",
}
REPAIR_STATUSES = {"not_applicable", "open", "repaired", "retained_with_reason", "unresolved"}
PDF_STATUSES = {"not_checked", "verified", "unresolved"}
SEMANTIC_REVIEWED = {
    "matched",
    "defect",
    "intentional_with_reason",
    "source_issue_retained",
    "unresolved",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pdf_page_count(path: Path, supplied: int | None) -> int:
    if supplied is not None:
        if supplied < 1:
            raise ValueError("page counts must be positive")
        return supplied
    try:
        import pymupdf as fitz
    except ImportError as exc:
        try:
            import fitz
        except ImportError:
            raise ValueError(
                "PyMuPDF is needed to count PDF pages; install pymupdf or pass the corresponding --*-page-count"
            ) from exc
    with fitz.open(path) as document:
        return document.page_count


def require_file(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"file not found: {path}")
    return path


def ledger_paths(directory: str) -> tuple[Path, Path, Path]:
    root = Path(directory).expanduser().resolve()
    return root, root / "manifest.json", root / "pages.csv"


def read_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"ledger manifest not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported ledger schema version: {data.get('schema_version')}")
    return data


def write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_csv_rows(path: Path, expected_fields: list[str]) -> list[dict[str, str]]:
    if not path.is_file():
        raise ValueError(f"ledger table not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != expected_fields:
            raise ValueError(f"unexpected columns in {path.name}; restore the generated header")
        return [dict(row) for row in reader]


def write_csv_atomic(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="raise", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def snapshot_record(name: str, path: Path, page_count: int, input_revision: str = "") -> dict[str, Any]:
    return {
        "name": name,
        "path": str(path),
        "sha256": sha256_file(path),
        "page_count": page_count,
        "input_revision": input_revision,
        "recorded_at_utc": utc_now(),
    }


def cmd_init(args: argparse.Namespace) -> int:
    source = require_file(args.source)
    translation = require_file(args.translation)
    source_count = pdf_page_count(source, args.source_page_count)
    translation_count = pdf_page_count(translation, args.translation_page_count)
    start = args.scope_start if args.scope_start is not None else 1
    end = args.scope_end if args.scope_end is not None else source_count
    if start < 1 or end < start or end > source_count:
        raise ValueError(f"scope must be within source PDF pages 1..{source_count}")

    root, manifest_path, pages_path = ledger_paths(args.ledger_dir)
    units_path = root / "units.csv"
    root.mkdir(parents=True, exist_ok=True)
    if any(path.exists() for path in (manifest_path, pages_path, units_path)):
        raise ValueError(f"ledger files already exist in {root}; refusing to overwrite them")

    initial = snapshot_record("T0", translation, translation_count, args.input_revision or "")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": utc_now(),
        "edition": args.edition or "",
        "build_entrypoint": args.build_entrypoint or "",
        "source": {
            "path": str(source),
            "sha256": sha256_file(source),
            "page_count": source_count,
        },
        "scope": {"source_physical_start": start, "source_physical_end": end},
        "current_translation_snapshot": "T0",
        "translation_snapshots": {"T0": initial},
        "status_values": {
            "semantic": sorted(SEMANTIC_STATUSES),
            "repair": sorted(REPAIR_STATUSES),
            "pdf": sorted(PDF_STATUSES),
        },
    }
    pages: list[dict[str, str]] = []
    for number in range(1, source_count + 1):
        printed = ""
        if args.source_printed_start is not None and start <= number <= end:
            printed = str(args.source_printed_start + number - start)
        pages.append(
            {
                "source_physical_page": str(number),
                "source_printed_page": printed,
                "in_scope": "yes" if start <= number <= end else "no",
                "source_inventory_status": "not_started",
                "translation_inventory_status": "not_started",
                "challenge_status": "not_started",
                "unit_count": "0",
                "finding_ids": "",
                "notes": "",
            }
        )
    write_json_atomic(manifest_path, manifest)
    write_csv_atomic(pages_path, PAGE_FIELDS, pages)
    write_csv_atomic(units_path, UNIT_FIELDS, [])
    print(f"Created review ledger: {root}")
    print(f"Source pages: {source_count}; scope: {start}-{end}; initial translation snapshot: T0")
    return 0


def cmd_snapshot(args: argparse.Namespace) -> int:
    root, manifest_path, _ = ledger_paths(args.ledger_dir)
    manifest = read_manifest(manifest_path)
    translation = require_file(args.translation)
    snapshots = manifest["translation_snapshots"]
    if args.name in snapshots:
        raise ValueError(f"snapshot already exists: {args.name}")
    count = pdf_page_count(translation, args.translation_page_count)
    snapshots[args.name] = snapshot_record(args.name, translation, count, args.input_revision or "")
    manifest["current_translation_snapshot"] = args.name
    write_json_atomic(manifest_path, manifest)
    print(f"Recorded {args.name}: {translation}")
    print(f"SHA-256: {snapshots[args.name]['sha256']}; pages: {count}")
    print("PDF checks tied to earlier snapshots will be reported as stale; semantic rows remain separately tracked.")
    return 0


def cmd_add_unit(args: argparse.Namespace) -> int:
    root, manifest_path, pages_path = ledger_paths(args.ledger_dir)
    manifest = read_manifest(manifest_path)
    units_path = root / "units.csv"
    units = read_csv_rows(units_path, UNIT_FIELDS)
    if any(row["unit_id"] == args.unit_id for row in units):
        raise ValueError(f"unit_id already exists: {args.unit_id}")
    start = manifest["scope"]["source_physical_start"]
    end = manifest["scope"]["source_physical_end"]
    if not start <= args.source_page <= end:
        raise ValueError(f"source page {args.source_page} is outside ledger scope {start}-{end}")
    pages = read_csv_rows(pages_path, PAGE_FIELDS)
    page = next(row for row in pages if int(row["source_physical_page"]) == args.source_page)
    printed = page["source_printed_page"]
    tex_file = str(Path(args.translation_tex_file).expanduser().resolve()) if args.translation_tex_file else ""
    row = {field: "" for field in UNIT_FIELDS}
    row.update(
        {
            "unit_id": args.unit_id,
            "source_physical_page": str(args.source_page),
            "source_region": args.source_region or "",
            "source_printed_page": printed,
            "kind": args.kind,
            "source_identifier": args.source_identifier or "",
            "translation_tex_file": tex_file,
            "semantic_status": "not_started",
            "repair_status": "not_applicable",
            "pdf_status": "not_checked",
        }
    )
    units.append(row)
    page["unit_count"] = str(int(page["unit_count"] or "0") + 1)
    write_csv_atomic(units_path, UNIT_FIELDS, units)
    write_csv_atomic(pages_path, PAGE_FIELDS, pages)
    print(f"Added {args.unit_id} on source physical page {args.source_page}.")
    return 0


def cmd_mark_page(args: argparse.Namespace) -> int:
    _, manifest_path, pages_path = ledger_paths(args.ledger_dir)
    manifest = read_manifest(manifest_path)
    pages = read_csv_rows(pages_path, PAGE_FIELDS)
    start = manifest["scope"]["source_physical_start"]
    end = manifest["scope"]["source_physical_end"]
    if not start <= args.page <= end:
        raise ValueError(f"source page {args.page} is outside ledger scope {start}-{end}")
    row = next((item for item in pages if int(item["source_physical_page"]) == args.page), None)
    if row is None:
        raise ValueError(f"source physical page is missing from pages.csv: {args.page}")
    if args.printed_page is not None:
        row["source_printed_page"] = str(args.printed_page)
    if args.source_inventory_status:
        row["source_inventory_status"] = args.source_inventory_status
    if args.translation_inventory_status:
        row["translation_inventory_status"] = args.translation_inventory_status
    if args.challenge_status:
        row["challenge_status"] = args.challenge_status
    if args.finding_ids is not None:
        row["finding_ids"] = args.finding_ids
    if args.notes is not None:
        row["notes"] = args.notes
    if args.append_note:
        row["notes"] = "; ".join(part for part in (row["notes"], args.append_note) if part)
    write_csv_atomic(pages_path, PAGE_FIELDS, pages)
    print(f"Updated source physical page {args.page}.")
    return 0


def cmd_mark_unit(args: argparse.Namespace) -> int:
    root, manifest_path, _ = ledger_paths(args.ledger_dir)
    manifest = read_manifest(manifest_path)
    units_path = root / "units.csv"
    units = read_csv_rows(units_path, UNIT_FIELDS)
    row = next((item for item in units if item["unit_id"] == args.unit_id), None)
    if row is None:
        raise ValueError(f"unit not found: {args.unit_id}")
    if args.semantic_status:
        row["semantic_status"] = args.semantic_status
        row["semantic_source_sha256"] = manifest["source"]["sha256"]
        if row["translation_tex_file"]:
            path = Path(row["translation_tex_file"])
            if path.is_file():
                row["semantic_tex_sha256"] = sha256_file(path)
    if args.repair_status:
        row["repair_status"] = args.repair_status
    elif args.semantic_status == "defect" and row["repair_status"] == "not_applicable":
        row["repair_status"] = "open"
    if args.pdf_status:
        row["pdf_status"] = args.pdf_status
        row["pdf_snapshot"] = (
            manifest["current_translation_snapshot"]
            if args.pdf_status in {"verified", "unresolved"}
            else ""
        )
    if args.translation_tex_file:
        path = Path(args.translation_tex_file).expanduser().resolve()
        row["translation_tex_file"] = str(path)
        if args.semantic_status and path.is_file():
            row["semantic_tex_sha256"] = sha256_file(path)
    for argument, field in (
        (args.translation_anchor, "translation_anchor"),
        (args.output_physical_page, "translation_pdf_physical_page"),
        (args.output_printed_page, "translation_printed_page"),
        (args.evidence_path, "evidence_path"),
        (args.finding_id, "finding_id"),
    ):
        if argument is not None:
            row[field] = str(argument)
    if args.notes is not None:
        row["notes"] = args.notes
    if args.append_note:
        row["notes"] = "; ".join(part for part in (row["notes"], args.append_note) if part)
    write_csv_atomic(units_path, UNIT_FIELDS, units)
    print(f"Updated {args.unit_id}.")
    return 0


def validate_rows(manifest: dict[str, Any], pages: list[dict[str, str]], units: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    page_numbers = [int(row["source_physical_page"]) for row in pages]
    if len(page_numbers) != len(set(page_numbers)):
        errors.append("pages.csv has duplicate source physical pages")
    expected = set(range(1, manifest["source"]["page_count"] + 1))
    if set(page_numbers) != expected:
        errors.append("pages.csv does not contain exactly one row for every source physical page")
    unit_ids = [row["unit_id"] for row in units]
    if len(unit_ids) != len(set(unit_ids)):
        errors.append("units.csv has duplicate unit_id values")
    start = manifest["scope"]["source_physical_start"]
    end = manifest["scope"]["source_physical_end"]
    for row in pages:
        page = int(row["source_physical_page"])
        expected_scope = "yes" if start <= page <= end else "no"
        if row["in_scope"] != expected_scope:
            errors.append(f"source page {page}: in_scope disagrees with the manifest range")
        if row["source_inventory_status"] not in PAGE_INVENTORY_STATUSES:
            errors.append(f"source page {page}: unknown source_inventory_status")
        if row["translation_inventory_status"] not in PAGE_INVENTORY_STATUSES:
            errors.append(f"source page {page}: unknown translation_inventory_status")
        if row["challenge_status"] not in CHALLENGE_STATUSES:
            errors.append(f"source page {page}: unknown challenge_status")
    for row in units:
        try:
            page = int(row["source_physical_page"])
        except (TypeError, ValueError):
            errors.append(f"{row['unit_id']}: invalid source physical page")
            continue
        if not start <= page <= end:
            errors.append(f"{row['unit_id']}: source physical page is outside scope")
        if row["semantic_status"] not in SEMANTIC_STATUSES:
            errors.append(f"{row['unit_id']}: unknown semantic_status {row['semantic_status']!r}")
        if row["repair_status"] not in REPAIR_STATUSES:
            errors.append(f"{row['unit_id']}: unknown repair_status {row['repair_status']!r}")
        if row["pdf_status"] not in PDF_STATUSES:
            errors.append(f"{row['unit_id']}: unknown pdf_status {row['pdf_status']!r}")
    return errors


def current_file_warning(name: str, data: dict[str, Any]) -> str | None:
    path = Path(data["path"])
    if not path.is_file():
        return f"{name}: recorded file is missing: {path}"
    actual = sha256_file(path)
    if actual != data["sha256"]:
        return f"{name}: file changed since snapshot; record a new immutable snapshot (current hash {actual})"
    return None


def compress_page_numbers(numbers: list[int]) -> str:
    if not numbers:
        return "none"
    ordered = sorted(set(numbers))
    ranges: list[str] = []
    first = previous = ordered[0]
    for number in ordered[1:]:
        if number == previous + 1:
            previous = number
            continue
        ranges.append(str(first) if first == previous else f"{first}-{previous}")
        first = previous = number
    ranges.append(str(first) if first == previous else f"{first}-{previous}")
    return ", ".join(ranges)


def cmd_report(args: argparse.Namespace) -> int:
    root, manifest_path, pages_path = ledger_paths(args.ledger_dir)
    manifest = read_manifest(manifest_path)
    pages = read_csv_rows(pages_path, PAGE_FIELDS)
    units = read_csv_rows(root / "units.csv", UNIT_FIELDS)
    errors = validate_rows(manifest, pages, units)
    scope_start = manifest["scope"]["source_physical_start"]
    scope_end = manifest["scope"]["source_physical_end"]
    in_scope_pages = [row for row in pages if row["in_scope"] == "yes"]
    open_pages = [
        row for row in in_scope_pages
        if row["source_inventory_status"] not in {"inventoried", "not_applicable"}
        or row["translation_inventory_status"] not in {"inventoried", "not_applicable"}
        or row["challenge_status"] not in {"reviewed", "not_applicable"}
    ]
    current_name = manifest["current_translation_snapshot"]
    current_snapshot = manifest["translation_snapshots"][current_name]
    stale_pdf = [
        row for row in units
        if row["pdf_status"] == "verified" and row["pdf_snapshot"] != current_name
    ]
    open_repairs = [row for row in units if row["repair_status"] == "open"]
    unresolved = [row for row in units if row["semantic_status"] == "unresolved" or row["repair_status"] == "unresolved"]
    semantic_open = [row for row in units if row["semantic_status"] in {"not_started", "unresolved"}]
    pdf_open = [row for row in units if row["pdf_status"] != "verified" or row["pdf_snapshot"] != current_name]
    semantic_counts = Counter(row["semantic_status"] for row in units)
    pdf_counts = Counter(row["pdf_status"] for row in units)
    repair_counts = Counter(row["repair_status"] for row in units)
    warnings: list[str] = []
    warning = current_file_warning("source PDF", manifest["source"])
    if warning:
        warnings.append(warning)
    warning = current_file_warning(f"translation snapshot {current_name}", current_snapshot)
    if warning:
        warnings.append(warning)
    for row in units:
        tex_file = row["translation_tex_file"]
        if row["semantic_status"] in SEMANTIC_REVIEWED and not row["semantic_source_sha256"]:
            warnings.append(f"{row['unit_id']}: semantic status is not bound to a source PDF hash")
        if row["semantic_status"] in SEMANTIC_REVIEWED and row["semantic_source_sha256"] != manifest["source"]["sha256"]:
            warnings.append(f"{row['unit_id']}: semantic review uses a different source PDF hash")
        if row["semantic_status"] in SEMANTIC_REVIEWED and not tex_file:
            warnings.append(f"{row['unit_id']}: semantic status is not bound to a translation source file")
        if row["semantic_status"] in SEMANTIC_REVIEWED and tex_file and not row["semantic_tex_sha256"]:
            warnings.append(f"{row['unit_id']}: translation source file hash was not recorded")
        if row["pdf_status"] == "verified" and not row["translation_pdf_physical_page"]:
            warnings.append(f"{row['unit_id']}: PDF check is marked verified without an output physical page")
        if row["pdf_status"] == "verified" and not row["evidence_path"]:
            warnings.append(f"{row['unit_id']}: PDF check is marked verified without a saved evidence path")
        if tex_file and row["semantic_tex_sha256"]:
            path = Path(tex_file)
            if path.is_file() and sha256_file(path) != row["semantic_tex_sha256"]:
                warnings.append(f"{row['unit_id']}: translation source file changed after semantic review")
            elif not path.is_file():
                warnings.append(f"{row['unit_id']}: recorded translation source file is missing: {path}")
    lines = [
        f"# Review ledger: {root.name}",
        "",
        f"- Edition: {manifest.get('edition') or '(not recorded)'}",
        f"- Source: {manifest['source']['page_count']} pages; SHA-256 `{manifest['source']['sha256']}`",
        f"- Source scope: physical pages {scope_start}–{scope_end}",
        f"- Current translation snapshot: {current_name}, {current_snapshot['page_count']} pages; SHA-256 `{current_snapshot['sha256']}`",
        f"- Build entry point: {manifest.get('build_entrypoint') or '(not recorded)'}; input revision: {current_snapshot.get('input_revision') or '(not recorded)'}",
        f"- Page coverage inventory incomplete: {len(open_pages)}/{len(in_scope_pages)} in-scope pages",
        f"- Content units: {len(units)}; semantic states `{dict(semantic_counts)}`",
        f"- Repair states `{dict(repair_counts)}`; PDF states `{dict(pdf_counts)}`",
        f"- Semantic review open: {len(semantic_open)}; PDF check open on current snapshot: {len(pdf_open)}",
        f"- Stale PDF evidence: {len(stale_pdf)}; open repairs: {len(open_repairs)}; unresolved units: {len(unresolved)}",
    ]
    if open_pages:
        lines.append(f"- Pages still needing inventory/challenge work: {compress_page_numbers([int(row['source_physical_page']) for row in open_pages])}")
    if errors:
        lines += ["", "## Ledger structure errors", ""] + [f"- {item}" for item in errors]
    if warnings:
        lines += ["", "## Version warnings", ""] + [f"- {item}" for item in warnings]
    if stale_pdf:
        lines += ["", "## PDF checks tied to an older snapshot", ""] + [f"- {row['unit_id']}: {row['pdf_snapshot']}" for row in stale_pdf]
    if open_repairs:
        lines += ["", "## Open repairs", ""] + [f"- {row['unit_id']}: {row['finding_id']}" for row in open_repairs]
    if unresolved:
        lines += ["", "## Unresolved units", ""] + [f"- {row['unit_id']}: {row['finding_id']}" for row in unresolved]
    if not (errors or warnings or stale_pdf or open_repairs or unresolved or open_pages or semantic_open or pdf_open):
        lines += ["", "No open states remain in this ledger snapshot; this status summary is not a verdict on content correctness."]
    report = "\n".join(lines) + "\n"
    if args.output:
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report, encoding="utf-8")
    print(report, end="")
    return 2 if errors else 0


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create and audit a source-to-translation review ledger.")
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="create a manifest and page/unit tables")
    init.add_argument("--source", required=True, help="authoritative source PDF")
    init.add_argument("--translation", required=True, help="frozen initial translation PDF")
    init.add_argument("--ledger-dir", required=True)
    init.add_argument("--edition", help="edition or printing used as the source authority")
    init.add_argument("--build-entrypoint", help="actual build command or entry point")
    init.add_argument("--input-revision", help="optional TeX/generator commit or revision for snapshot T0")
    init.add_argument("--scope-start", type=int, help="first source physical page in scope; default 1")
    init.add_argument("--scope-end", type=int, help="last source physical page in scope; default final page")
    init.add_argument("--source-printed-start", type=int, help="printed folio on scope-start, if known")
    init.add_argument("--source-page-count", type=int, help="supply count if PyMuPDF is unavailable")
    init.add_argument("--translation-page-count", type=int, help="supply count if PyMuPDF is unavailable")
    init.set_defaults(func=cmd_init)

    snapshot = commands.add_parser("snapshot", help="record a new immutable translation PDF version")
    snapshot.add_argument("--ledger-dir", required=True)
    snapshot.add_argument("--name", required=True, help="snapshot label such as T1")
    snapshot.add_argument("--translation", required=True)
    snapshot.add_argument("--input-revision", help="optional TeX/generator commit or revision")
    snapshot.add_argument("--translation-page-count", type=int, help="supply count if PyMuPDF is unavailable")
    snapshot.set_defaults(func=cmd_snapshot)

    add = commands.add_parser("add-unit", help="register one source content unit")
    add.add_argument("--ledger-dir", required=True)
    add.add_argument("--unit-id", required=True)
    add.add_argument("--source-page", required=True, type=int, help="source physical page")
    add.add_argument("--kind", required=True, help="paragraph, equation, theorem, exercise, footnote, figure, index, etc.")
    add.add_argument("--source-region")
    add.add_argument("--source-identifier")
    add.add_argument("--translation-tex-file", help="optional source file containing the mapped translation")
    add.set_defaults(func=cmd_add_unit)

    page = commands.add_parser("mark-page", help="update inventory and challenge status for one source page")
    page.add_argument("--ledger-dir", required=True)
    page.add_argument("--page", required=True, type=int, help="source physical page")
    page.add_argument("--printed-page", type=int)
    page.add_argument("--source-inventory-status", choices=sorted(PAGE_INVENTORY_STATUSES))
    page.add_argument("--translation-inventory-status", choices=sorted(PAGE_INVENTORY_STATUSES))
    page.add_argument("--challenge-status", choices=sorted(CHALLENGE_STATUSES))
    page.add_argument("--finding-ids")
    page.add_argument("--notes")
    page.add_argument("--append-note")
    page.set_defaults(func=cmd_mark_page)

    mark = commands.add_parser("mark-unit", help="update a unit's review and PDF evidence status")
    mark.add_argument("--ledger-dir", required=True)
    mark.add_argument("--unit-id", required=True)
    mark.add_argument("--semantic-status", choices=sorted(SEMANTIC_STATUSES - {"not_started"}))
    mark.add_argument("--repair-status", choices=sorted(REPAIR_STATUSES))
    mark.add_argument("--pdf-status", choices=sorted(PDF_STATUSES - {"not_checked"}))
    mark.add_argument("--translation-tex-file", help="translation file to bind semantic review to")
    mark.add_argument("--translation-anchor")
    mark.add_argument("--output-physical-page")
    mark.add_argument("--output-printed-page")
    mark.add_argument("--evidence-path")
    mark.add_argument("--finding-id")
    mark.add_argument("--notes")
    mark.add_argument("--append-note")
    mark.set_defaults(func=cmd_mark_unit)

    report = commands.add_parser("report", help="summarize coverage, findings, and stale evidence")
    report.add_argument("--ledger-dir", required=True)
    report.add_argument("--output", help="also write the report to a Markdown file")
    report.set_defaults(func=cmd_report)
    return parser


def main() -> int:
    parser = make_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except (OSError, ValueError, csv.Error, json.JSONDecodeError) as exc:
        print(f"review_ledger: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
