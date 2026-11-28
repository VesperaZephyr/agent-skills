"""Build and reconcile source/final index checklists from visual transcriptions."""

import argparse
import csv
import hashlib
import os
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path


IDENTITY = (
    "id", "side", "pdf_sha256", "index_page", "physical_page", "column",
    "path", "kind", "value", "weight",
)
REVIEW = (
    "owner", "decision", "counterpart", "evidence", "final_evidence",
    "visual_evidence", "link_check", "verified_pdf_sha256",
)
FIELDS = IDENTITY + REVIEW
DECISIONS = {
    "source": {"match", "repair", "exception"},
    "final": {"match", "addition", "exception"},
}
PAGE = re.compile(r"[1-9][0-9]*|[ivxlcdm]+")


def digest(path):
    with open(path, "rb") as stream:
        sha = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(block)
        return sha.hexdigest()


def read(path):
    with open(path, encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError(f"{path}: unexpected CSV header")
        rows = list(reader)
    ids = set()
    for row in rows:
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f"{path}: malformed CSV row")
        if row["id"] in ids or not row["id"] or row["side"] not in DECISIONS:
            raise ValueError(f"{path}: invalid or duplicate ID {row['id']}")
        ids.add(row["id"])
    return rows


def write(path, rows, *, replace=False):
    path = Path(path)
    if path.exists() and not replace:
        raise ValueError(f"{path} already exists")
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8-sig", newline="", dir=path.parent, delete=False
    ) as stream:
        temporary = Path(stream.name)
        try:
            writer = csv.DictWriter(stream, FIELDS)
            writer.writeheader()
            writer.writerows(rows)
            stream.close()
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def entries(side, pdf_hash, pages):
    pages_seen, keys = set(), set()
    for label, physical, text_path in pages:
        if (not physical.isdecimal() or int(physical) < 1
                or physical in pages_seen or not label.strip()):
            raise ValueError(f"invalid or duplicate physical page: {physical}")
        pages_seen.add(physical)
        for line_no, line in enumerate(
            Path(text_path).read_text(encoding="utf-8-sig").splitlines(), 1
        ):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            fields = [field.strip() for field in line.split("|")]
            if len(fields) != 3 or not all(fields):
                raise ValueError(f"{text_path}:{line_no}: expected column|path|entries")
            column, path, raw = fields
            if raw.startswith(("see:", "see-also:")):
                kind, value = raw.split(":", 1)
                items = [(kind, value.strip(), "")]
                if not items[0][1]:
                    raise ValueError(f"{text_path}:{line_no}: empty redirect")
            elif raw == "branch:":
                items = [("branch", "", "")]
            else:
                items = []
                for token in raw.split():
                    bold = token.startswith("*")
                    value = token[1:] if bold else token
                    if not PAGE.fullmatch(value):
                        raise ValueError(f"{text_path}:{line_no}: invalid page {value!r}")
                    items.append(("page", value, "bold" if bold else "regular"))
            for ordinal, (kind, value, weight) in enumerate(items, 1):
                key = (path, kind, value)
                if key in keys:
                    raise ValueError(f"{text_path}:{line_no}: duplicate logical row {key}")
                keys.add(key)
                identity = (
                    f"{side[0].upper()}-{int(physical):04d}-{line_no:03d}-{ordinal:02d}",
                    side, pdf_hash, label, physical, column, path, kind, value, weight,
                )
                yield dict(zip(FIELDS, identity + ("",) * len(REVIEW)))


def assign(args):
    rows = read(args.ledger)
    if bool(args.ids) == bool(args.pages) or (args.ids and args.column):
        raise ValueError("select either page(s) with optional column, or --ids")
    selected = [row for row in rows if row["side"] == args.side and (
        row["id"] in args.ids if args.ids else row["index_page"] in args.pages
        and (not args.column or row["column"] == args.column)
    )]
    if args.ids and {row["id"] for row in selected} != set(args.ids):
        raise ValueError("one or more IDs are absent from the requested side")
    if not selected or any(row["owner"] for row in selected):
        raise ValueError("empty selection or rows already assigned")
    for row in selected:
        row["owner"] = args.owner
    write(args.output, selected)
    write(args.ledger, rows, replace=True)


def merge(args):
    rows = read(args.ledger)
    by_id = {row["id"]: row for row in rows}
    seen = set()
    for shard in args.shards:
        for update in read(shard):
            key = update["id"]
            original = by_id.get(key)
            if (key in seen or original is None or not original["owner"]
                    or any(update[field] != original[field] for field in IDENTITY + ("owner",))):
                raise ValueError(f"{shard}: duplicate, unassigned or altered row {key}")
            seen.add(key)
            if not update["decision"] and not update["verified_pdf_sha256"]:
                continue
            if update["decision"] not in DECISIONS[update["side"]] or not update["evidence"].strip():
                raise ValueError(f"{shard}: invalid decision or missing evidence for {key}")
            if original["decision"] and update != original and not args.replace_review:
                raise ValueError(f"{shard}: already reviewed {key}; use --replace-review to adjudicate")
            original.update(update)
    write(args.ledger, rows, replace=True)


def inspect(args):
    rows = read(args.ledger)
    for side in DECISIONS:
        subset = [row for row in rows if row["side"] == side]
        print(side, "total", len(subset), "kinds", dict(Counter(r["kind"] for r in subset)),
              "decisions", dict(Counter(r["decision"] or "pending" for r in subset)))
    if args.pending:
        for row in rows:
            if not row["decision"]:
                print(row["id"], row["path"], row["kind"], row["value"], row["owner"], sep="\t")
    if not args.gate:
        return 0
    source = [row for row in rows if row["side"] == "source"]
    if not source or any(r["decision"] not in DECISIONS["source"] or not r["evidence"].strip()
                         for r in source):
        raise ValueError("source review is incomplete")
    if args.gate == "source":
        return 0
    if not args.pdf:
        raise ValueError("--gate final requires --pdf")
    final_hash = digest(args.pdf)
    reverse = {r["id"]: r for r in rows if r["side"] == "final"}
    if not reverse:
        raise ValueError("final PDF requires its own independently inventoried index rows")
    by_id = {r["id"]: r for r in rows}
    for row in rows:
        refs = set(row["counterpart"].split())
        row_id, side, decision = row["id"], row["side"], row["decision"]
        valid_link = {"match", "not-applicable"} if row["kind"] == "page" else {"not-applicable"}
        if (decision not in DECISIONS[side] or not row["evidence"].strip()
                or not row["final_evidence"].strip() or not row["visual_evidence"].strip()
                or row["link_check"] not in valid_link
                or row["verified_pdf_sha256"] != final_hash
                or (side == "final" and row["pdf_sha256"] != final_hash)
                or (decision in {"match", "repair"} and not refs)
                or any(ref not in by_id or by_id[ref]["side"] == side
                       or row_id not in by_id[ref]["counterpart"].split() for ref in refs)):
            raise ValueError(f"{row_id}: incomplete, stale or inconsistent final evidence")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    setup = sub.add_parser("inventory", help="register a source or independently transcribed final index")
    setup.add_argument("ledger")
    setup.add_argument("side", choices=DECISIONS)
    setup.add_argument("pdf")
    setup.add_argument("--page", action="append", nargs=3, required=True,
                       metavar=("LABEL", "PHYSICAL", "TRANSCRIPTION"))
    setup.add_argument("--replace-final", action="store_true",
                       help="replace final rows and clear previous final verification on source rows")
    claim = sub.add_parser("assign", help="export an exclusive reviewer shard")
    claim.add_argument("ledger")
    claim.add_argument("output")
    claim.add_argument("owner")
    claim.add_argument("side", choices=DECISIONS)
    claim.add_argument("pages", nargs="*")
    claim.add_argument("--column")
    claim.add_argument("--ids", nargs="+", default=[])
    combine = sub.add_parser("merge", help="validate and import reviewer shards")
    combine.add_argument("ledger")
    combine.add_argument("shards", nargs="+")
    combine.add_argument("--replace-review", action="store_true")
    status = sub.add_parser("status", help="show actual undecided rows or enforce a checkpoint")
    status.add_argument("ledger")
    status.add_argument("--pending", action="store_true")
    status.add_argument("--gate", choices=("source", "final"))
    status.add_argument("--pdf")
    args = parser.parse_args()
    try:
        if args.command == "inventory":
            exists = Path(args.ledger).exists()
            rows = read(args.ledger) if exists else []
            if args.replace_final and args.side != "final":
                raise ValueError("--replace-final only applies to final inventory")
            if any(row["side"] == args.side for row in rows) and not args.replace_final:
                raise ValueError("this side is already registered")
            if args.replace_final:
                rows = [row for row in rows if row["side"] == "source"]
                for row in rows:
                    for field in ("counterpart", "final_evidence", "visual_evidence",
                                  "link_check", "verified_pdf_sha256"):
                        row[field] = ""
            new = list(entries(args.side, digest(args.pdf), args.page))
            if not new:
                raise ValueError("empty inventory")
            write(args.ledger, rows + new, replace=exists)
            print(f"registered {len(new)} {args.side} rows")
        elif args.command == "assign":
            assign(args)
        elif args.command == "merge":
            merge(args)
        else:
            return inspect(args)
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
