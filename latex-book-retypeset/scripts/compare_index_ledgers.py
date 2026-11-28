"""Compare two UTF-8 index ledgers by exact, normalized source identity."""
import argparse
import csv
from pathlib import Path

KEY = ("index", "path", "locator")


def read_ledger(path):
    records = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if not reader.fieldnames or not set(KEY) <= set(reader.fieldnames):
            raise ValueError(f"{path}: required columns: {', '.join(KEY)}")
        for row in reader:
            key = tuple((row[column] or "").strip() for column in KEY)
            if not all(key) or key in records:
                raise ValueError(f"{path}:{reader.line_num}: empty or duplicate key {key!r}")
            records[key] = row
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    args = parser.parse_args()
    try:
        source, target = map(read_ledger, (args.source, args.target))
    except (OSError, ValueError) as error:
        parser.error(str(error))

    import sys

    fields = (*KEY, "comparison", "source_evidence", "target_evidence", "semantic_status")
    writer = csv.DictWriter(sys.stdout, fields, delimiter="\t", lineterminator="\n")
    sys.stdout.reconfigure(encoding="utf-8")
    writer.writeheader()
    for key in dict.fromkeys((*source, *target)):
        original, current = source.get(key), target.get(key)
        comparison = "target_only" if original is None else (
            "source_only" if current is None else "paired"
        )
        writer.writerow(dict(zip(KEY, key), comparison=comparison,
                             source_evidence=(original or {}).get("evidence", ""),
                             target_evidence=(current or {}).get("evidence", ""),
                             semantic_status=(current or {}).get("semantic_status", "")))


if __name__ == "__main__":
    main()
