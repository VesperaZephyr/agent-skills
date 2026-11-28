"""Check final index locator annotations against an independent ledger."""
import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path

import pymupdf
from index_review_ledger import digest, read


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf")
    parser.add_argument("ledger")
    parser.add_argument("--output", required=True, help="CSV evidence file")
    args = parser.parse_args()

    sha = digest(args.pdf)
    inventory = [row for row in read(args.ledger) if row["side"] == "final"]
    if not inventory or any(row["pdf_sha256"] != sha for row in inventory):
        parser.error("final inventory is missing or belongs to another PDF")

    expected = defaultdict(Counter)
    for row in inventory:
        page = expected[int(row["physical_page"])]
        if row["kind"] == "page":
            page[row["value"].strip()] += 1
    findings = []

    def record(page, locator, status, target="", label="", annotation=""):
        findings.append(dict(pdf_sha256=sha, index_physical_page=page,
                             locator=locator, target_physical_page=target,
                             target_label=label, annotation_xref=annotation,
                             status=status))

    with pymupdf.open(args.pdf) as doc:
        if not all(1 <= number <= len(doc) for number in expected):
            parser.error("index physical page outside the PDF")
        labels = [page.get_label() for page in doc]
        label_counts = Counter(labels)
        for number, locators in sorted(expected.items()):
            page = doc[number - 1]
            textpage = page.get_textpage()
            observed = Counter()
            for link in page.get_links():
                visible = page.get_textbox(link["from"], textpage=textpage).strip().rstrip(",").rstrip()
                if visible not in locators:
                    record(number, visible, "unclassified_annotation", annotation=link["xref"])
                    continue
                observed[visible] += 1
                target = link.get("page", -1)
                if not isinstance(target, int) or not 0 <= target < len(doc):
                    record(number, visible, "unresolved_target", annotation=link["xref"])
                    continue
                label = labels[target]
                if label != visible:
                    status = "wrong_label"
                elif label_counts[label] > 1:
                    status = "ambiguous_label"
                else:
                    status = "match"
                record(number, visible, status, target + 1, label, link["xref"])
            for status, delta in (("missing_annotation", locators - observed),
                                  ("extra_annotation", observed - locators)):
                for locator in delta.elements():
                    record(number, locator, status)

    fields = ("pdf_sha256", "index_physical_page", "locator", "target_physical_page",
              "target_label", "annotation_xref", "status")
    output = Path(args.output)
    if output.resolve() in {Path(args.pdf).resolve(), Path(args.ledger).resolve()}:
        parser.error("output must differ from inputs")
    with output.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(findings)
    counts = Counter(row["status"] for row in findings)
    print(dict(counts))
    return int(any(status != "match" for status in counts))


if __name__ == "__main__":
    raise SystemExit(main())
