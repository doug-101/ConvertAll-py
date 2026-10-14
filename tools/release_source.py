#!/usr/bin/env python3
"""Create an immutable source archive from a CLEAN committed Qt6 tree.

No commit, tag, push or GitHub release is performed. Uses only the stdlib/git.
The gzip timestamp is zero, so repeated archives of the same commit match.
"""
import argparse
import ast
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def git(root, *arguments):
    return subprocess.check_output(['git', '-C', str(root), *arguments])


def version_from_source(source):
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == '__version__'
                for target in node.targets):
            version = ast.literal_eval(node.value)
            if isinstance(version, str) and re.fullmatch(r'\d+\.\d+\.\d+', version):
                return version
    raise ValueError('No stable __version__ found in source/convertall.py')


def create_archive(root, output_dir, commit='HEAD'):
    root, output_dir = Path(root).resolve(), Path(output_dir).resolve()
    if git(root, 'status', '--porcelain', '--untracked-files=normal').strip():
        raise ValueError('Working tree is dirty: commit the tested changes first')
    sha = git(root, 'rev-parse', '--verify', commit + '^{commit}').decode().strip()
    head = git(root, 'rev-parse', 'HEAD').decode().strip()
    if sha != head:
        raise ValueError('Archive must target the checked-out, tested HEAD commit')
    source = git(root, 'show', sha + ':source/convertall.py').decode('utf-8')
    version = version_from_source(source)
    name = f'ConvertAll-{version}-qt6-source'
    # Check where output is going BEFORE creating any files.
    if output_dir == root or root.is_relative_to(output_dir):
        raise ValueError('Use a dedicated output directory, e.g. dist/release')
    tar = git(root, 'archive', '--format=tar', '--prefix=' + name + '/', sha)
    buffer = io.BytesIO()
    with gzip.GzipFile(filename='', mode='wb', fileobj=buffer,
                       compresslevel=9, mtime=0) as stream:
        stream.write(tar)
    compressed = buffer.getvalue()
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / (name + '.tar.gz')
    archive.write_bytes(compressed)
    digest = hashlib.sha256(compressed).hexdigest()
    checksum = archive.with_name(archive.name + '.sha256')
    checksum.write_text(f'{digest}  {archive.name}\n', encoding='ascii')
    metadata = {'version': version, 'binding': 'Qt6', 'source_commit': sha,
                'archive': archive.name, 'sha256': digest}
    provenance = archive.with_name(archive.name + '.provenance.json')
    provenance.write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    return archive, checksum, provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'dist/release')
    parser.add_argument('--commit', default='HEAD')
    args = parser.parse_args()
    try:
        paths = create_archive(ROOT, args.output_dir, args.commit)
    except (ValueError, subprocess.CalledProcessError) as error:
        print(f'Cannot create release archive: {error}', file=sys.stderr)
        return 1
    for path in paths:
        print(path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
