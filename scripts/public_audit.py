#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {'.git', '.venv', 'output', 'data', 'secrets', '.pytest_cache', '__pycache__'}
TOKEN_PATTERNS = [
    re.compile(r'apify_api_[A-Za-z0-9]+'),
    re.compile(r'AIza[0-9A-Za-z_-]{20,}'),
    re.compile(r'sk-[A-Za-z0-9_-]{20,}'),
]

def iter_files():
    for path in ROOT.rglob('*'):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in {'.mp4', '.mov', '.wav', '.jpg', '.png'}:
            continue
        yield path

def main() -> None:
    hits = []
    for path in iter_files():
        text = path.read_text(errors='ignore')
        for pat in TOKEN_PATTERNS:
            if pat.search(text):
                hits.append(str(path.relative_to(ROOT)))
    if hits:
        raise SystemExit('Potential secrets found:\n' + '\n'.join(hits))
    print('Public audit passed: no obvious tokens in tracked source/docs.')

if __name__ == '__main__':
    main()
