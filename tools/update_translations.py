#!/usr/bin/env python3
"""Update Qt6 application translations without losing the `_()` contexts.

PyQt6's pylupdate6 does not extract ConvertAll's global `_()` helper. This
stdlib AST extractor mirrors setupTranslator(): context = module filename.
Existing translation text/comments are preserved; removed sources become
vanished. Qt widget translations are provided by the pinned Qt6 runtime.

python tools/update_translations.py --check
python tools/update_translations.py --update --compile --lrelease /usr/lib/qt6/bin/lrelease
No downloads, publication or source modifications are performed.
"""
import argparse
import ast
import copy
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ('ca', 'de', 'es', 'fr', 'ru', 'sv')


def extract_messages(source):
    """Map (context, source, disambiguation) to relative filename/line pairs."""
    source = Path(source)
    messages = {}
    for path in sorted(source.glob('*.py')):
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != '_':
                continue
            if not node.args or not isinstance(node.args[0], ast.Constant) or not isinstance(node.args[0].value, str):
                raise ValueError(f'{path.name}:{node.lineno}: translation source must be a literal')
            if len(node.args) > 2:
                raise ValueError(f'{path.name}:{node.lineno}: unsupported translation arguments')
            comment = ''
            comment_node = node.args[1] if len(node.args) > 1 else None
            for keyword in node.keywords:
                if keyword.arg != 'comment' or comment_node is not None:
                    raise ValueError(f'{path.name}:{node.lineno}: unsupported translation keyword')
                comment_node = keyword.value
            if comment_node is not None:
                if not isinstance(comment_node, ast.Constant) or not isinstance(comment_node.value, str):
                    raise ValueError(f'{path.name}:{node.lineno}: disambiguation must be a literal')
                comment = comment_node.value
            key = (path.stem, node.args[0].value, comment)
            messages.setdefault(key, []).append(('../source/' + path.name, node.lineno))
    return messages


def catalogue_messages(path):
    result = {}
    for context in ET.parse(path).getroot().findall('context'):
        for message in context.findall('message'):
            key = (context.findtext('name'), message.findtext('source'), message.findtext('comment') or '')
            result[key] = message
    return result


def update_catalogue(path, extracted):
    path = Path(path)
    tree = ET.parse(path)
    existing = catalogue_messages(path)
    old_root = tree.getroot()
    root = ET.Element('TS', dict(old_root.attrib))
    root.set('version', '2.1')
    grouped = {}
    for key in sorted(set(existing) | set(extracted)):
        context, source, comment = key
        if key in existing:
            message = copy.deepcopy(existing[key])
        else:
            message = ET.Element('message')
            ET.SubElement(message, 'source').text = source
            if comment:
                ET.SubElement(message, 'comment').text = comment
            ET.SubElement(message, 'translation', {'type': 'unfinished'})
        for location in list(message.findall('location')):
            message.remove(location)
        translation = message.find('translation')
        if translation is None:
            translation = ET.SubElement(message, 'translation', {'type': 'unfinished'})
        if key in extracted:
            if translation.get('type') in ('obsolete', 'vanished'):
                translation.attrib.pop('type', None)
                if not ''.join(translation.itertext()).strip():
                    translation.set('type', 'unfinished')
            for index, (filename, line) in enumerate(extracted[key]):
                message.insert(index, ET.Element('location', {'filename': filename, 'line': str(line)}))
        else:
            translation.set('type', 'vanished')
        grouped.setdefault(context, []).append(message)
    for name, messages in sorted(grouped.items()):
        context = ET.SubElement(root, 'context')
        ET.SubElement(context, 'name').text = name
        context.extend(messages)
    ET.indent(root, space='  ')
    content = b'<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE TS>\n' + ET.tostring(root, encoding='utf-8') + b'\n'
    path.write_bytes(content)


def find_lrelease(requested=None):
    if requested:
        return requested
    for name in ('lrelease-qt6', 'lrelease6', 'lrelease'):
        found = shutil.which(name)
        if found:
            return found
    path = Path('/usr/lib/qt6/bin/lrelease')
    if path.is_file():
        return str(path)
    raise ValueError('Qt6 lrelease missing. Install Qt6 Linguist tools or pass --lrelease PATH.')


def compile_catalogue(path, executable):
    path = Path(path)
    with tempfile.TemporaryDirectory(prefix='convertall-qm-') as folder:
        qm = Path(folder) / path.with_suffix('.qm').name
        subprocess.run([executable, '-nounfinished', str(path), '-qm', str(qm)], check=True)
        if not qm.is_file() or not qm.stat().st_size:
            raise ValueError(f'No QM generated for {path.name}')
        path.with_suffix('.qm').write_bytes(qm.read_bytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='report sources absent from TS files; write nothing')
    parser.add_argument('--update', action='store_true')
    parser.add_argument('--compile', action='store_true')
    parser.add_argument('--lrelease')
    args = parser.parse_args()
    if not any((args.check, args.update, args.compile)) or (args.check and (args.update or args.compile)):
        parser.error('use --check, --update, --compile, or --update --compile')
    try:
        extracted = extract_messages(ROOT / 'source')
        executable = None
        if args.compile:
            executable = find_lrelease(args.lrelease)
            version = subprocess.run([executable, '-version'], capture_output=True, text=True, check=True)
            if not re.search(r'\b6\.\d+', version.stdout + version.stderr):
                raise ValueError('Refusing a non-Qt6 lrelease executable')
        missing = False
        for language in LANGUAGES:
            path = ROOT / 'translations' / f'convertall_{language}.ts'
            existing = catalogue_messages(path)
            absent = sorted(set(extracted) - set(existing))
            print(f'{language}: {len(extracted)} source messages; {len(absent)} missing from TS')
            if args.check:
                missing = missing or bool(absent)
                for context, source, comment in absent:
                    print(f'  {context}: {source!r} ({comment!r})')
            if args.update:
                update_catalogue(path, extracted)
            if args.compile:
                compile_catalogue(path, executable)
        return 1 if missing else 0
    except (OSError, ValueError, SyntaxError, ET.ParseError, subprocess.CalledProcessError) as error:
        print(f'Translation update failed: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
