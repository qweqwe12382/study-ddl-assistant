"""Archive the current deliverable source, including new non-ignored files.

Run with the project Python. No database, env file, dependency tree, or Git
credentials are included. The source tree and git index are not modified.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {'.git', '.tmp', '.venv', '.pytest-tmp', '.pytest_cache',
            'node_modules', '__pycache__', 'competition', 'submission'}


def main() -> None:
    listing = subprocess.check_output(
        ['git', 'ls-files', '-co', '--exclude-standard', '-z'], cwd=ROOT,
    ).decode('utf-8').split('\0')
    files = []
    for name in sorted(set(listing)):
        if not name:
            continue
        relative = Path(name)
        # docs/submission is an intentional public deliverable directory.
        if relative.parts[0] in EXCLUDED or any(
            p in EXCLUDED - {'submission'} for p in relative.parts[1:]
        ):
            continue
        if relative.name == '.env' or relative.suffix in {'.db', '.sqlite', '.sqlite3', '.pem', '.key'}:
            raise RuntimeError(f'Private data path must not be tracked: {name}')
        target = ROOT / relative
        if target.is_symlink() or not target.resolve().is_relative_to(ROOT):
            raise RuntimeError(f'Unsafe archive path: {name}')
        if target.is_file():
            files.append((relative.as_posix(), target))
    required = ['docs/submission/技术报告.pdf', 'docs/submission/评测用例.pdf',
                'docs/submission/学伴管家-介绍与演示.mp4', 'scripts/start-reviewer.ps1']
    names = {name for name, _ in files}
    for name in required:
        if name not in names:
            raise RuntimeError(f'Missing deliverable: {name}')
    manifest = {
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'description': 'Current working files; not a claim that GitHub is synchronized.',
        'files': [{'path': name, 'bytes': path.stat().st_size,
                   'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for name, path in files],
    }
    output = ROOT / 'submission'
    output.mkdir(exist_ok=True)
    archive = output / 'study-ddl-assistant-submission.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for name, path in files:
            bundle.write(path, name)
        bundle.writestr('MANIFEST.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / 'SHA256SUMS.txt').write_text(f'{digest}  {archive.name}\n', encoding='utf-8')
    print(f'{len(files)} files; {archive.stat().st_size / 1024**2:.1f} MiB; {archive}')


if __name__ == '__main__':
    main()
