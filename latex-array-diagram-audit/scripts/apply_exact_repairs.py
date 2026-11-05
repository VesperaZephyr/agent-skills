"""Apply a reviewed UTF-8 replacement plan to ONE file; dry-run by default."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile


def digest(data):
    return hashlib.sha256(data).hexdigest()


def run():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('target', type=Path)
    p.add_argument('plan', type=Path)
    p.add_argument('--apply', action='store_true')
    p.add_argument('--backup-dir', type=Path)
    a = p.parse_args()
    target = a.target.resolve(strict=True)
    original = target.read_bytes()
    plan = json.loads(a.plan.read_text(encoding='utf-8-sig'))
    if plan['source_sha256'] != digest(original):
        raise ValueError('Source hash mismatch; review the current file and regenerate the plan')
    bom = original.startswith(b'\xef\xbb\xbf')
    text = original.decode('utf-8-sig')
    # Normalize only for matching; reject mixed line endings rather than silently rewrite.
    crlf = '\r\n' in text
    if '\r' in text.replace('\r\n', '') or (crlf and '\n' in text.replace('\r\n', '')):
        raise ValueError('Mixed or unsupported line endings')
    normalized = text.replace('\r\n', '\n')
    spans = []
    for item in plan['replacements']:
        old, new = item['old'], item['new']
        count = item.get('expected_count', 1)
        if not old or not isinstance(count, int) or isinstance(count, bool) or count < 1:
            raise ValueError('Nonempty old and positive expected_count required')
        if '\r' in old or '\r' in new:
            raise ValueError('Plan strings must use LF line endings')
        if normalized.count(old) != count:
            raise ValueError('Replacement count mismatch: ' + repr(old[:80]))
        start = 0
        for _ in range(count):
            pos = normalized.index(old, start)
            spans.append((pos, pos + len(old), new))
            start = pos + len(old)
    if not spans:
        raise ValueError('Empty replacement plan')
    spans.sort()
    if any(left[1] > right[0] for left, right in zip(spans, spans[1:])):
        raise ValueError('Overlapping replacements')
    result = normalized
    for start, end, new in reversed(spans):
        result = result[:start] + new + result[end:]
    if crlf:
        result = result.replace('\n', '\r\n')
    output = (b'\xef\xbb\xbf' if bom else b'') + result.encode('utf-8')
    record = dict(target=str(target), before_sha256=digest(original),
                  after_sha256=digest(output), replacements=len(spans), applied=False)
    if a.apply:
        if a.backup_dir is None:
            raise ValueError('--apply requires --backup-dir')
        a.backup_dir.mkdir(parents=True, exist_ok=True)
        backup = a.backup_dir / (target.name + '.' + digest(original) + '.bak')
        if backup.exists() and backup.read_bytes() != original:
            raise ValueError('Existing backup differs')
        if not backup.exists():
            with backup.open('xb') as f:
                f.write(original)
        fd, temp = tempfile.mkstemp(prefix=target.name + '.', dir=target.parent)
        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(output)
            if target.read_bytes() != original:
                raise ValueError('Target changed during preflight; stop concurrent editors')
            os.replace(temp, target)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
        record.update(applied=True, backup=str(backup.resolve()))
    print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    run()
