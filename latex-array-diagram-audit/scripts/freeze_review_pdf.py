"""Copy a completed PDF to a new review bundle; record and recheck byte identity.

The caller must wait for the build to exit. Stability during copying does not
prove that a paused writer will not resume later.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import pymupdf


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def freeze(source, out, expected=None):
    source = Path(source).resolve(strict=True)
    out = Path(out).resolve()
    if out == source or source.is_relative_to(out):
        raise ValueError('Review bundle must not contain the input PDF')
    stat = source.stat()
    signature = (stat.st_size, stat.st_mtime_ns)
    initial = sha(source)
    if expected and initial != expected:
        raise ValueError('Expected source hash mismatch')
    out.mkdir(parents=True, exist_ok=False)
    try:
        target = out / 'review.pdf'
        shutil.copyfile(source, target)
        copied = sha(target)
        now = source.stat()
        if copied != initial or sha(source) != initial or signature != (now.st_size, now.st_mtime_ns):
            raise ValueError('Source changed during freezing; bundle is invalid')
        with pymupdf.open(target) as doc:
            if doc.needs_pass or not doc.is_pdf or doc.page_count < 1:
                raise ValueError('Expected readable nonempty PDF')
            count = doc.page_count
        record = dict(schema_version=1, source_pdf=str(source), frozen_pdf=str(target),
                      sha256=copied, pages=count, bytes=target.stat().st_size,
                      renderer=pymupdf.VersionBind, visual_review='not_performed',
                      limitation='Caller must stop/wait for the build before freezing.')
        (out / 'snapshot.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
        return record
    except Exception as exc:
        (out / 'INVALID.json').write_text(json.dumps(dict(error=str(exc))), encoding='utf-8')
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--out', required=True, type=Path, help='New review directory')
    parser.add_argument('--expected-sha256')
    args = parser.parse_args()
    print(json.dumps(freeze(args.source, args.out, args.expected_sha256), indent=2))


if __name__ == '__main__':
    main()
