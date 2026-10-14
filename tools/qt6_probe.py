#!/usr/bin/env python3
"""Create an isolated Qt6 feasibility prototype; never edit the application.

This intentionally targets the audited ConvertAll 0.8.0 checkout. It is not a
production migration or a generic Qt porting tool. In particular, it does not
fix existing conversion-data bugs or modernize the Windows installers.
Usage: python3 tools/qt6_probe.py --source ROOT --output .cache/qt-migration/qt6
The output must not already exist. No network access or Qt installation needed.
"""

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import shutil


ENUMS = {
    'Qt.WA_QuitOnClose': 'Qt.WidgetAttribute.WA_QuitOnClose',
    'Qt.Dialog': 'Qt.WindowType.Dialog',
    'Qt.Window': 'Qt.WindowType.Window',
    'Qt.WindowTitleHint': 'Qt.WindowType.WindowTitleHint',
    'Qt.WindowSystemMenuHint': 'Qt.WindowType.WindowSystemMenuHint',
    'Qt.WindowCloseButtonHint': 'Qt.WindowType.WindowCloseButtonHint',
    'Qt.WaitCursor': 'Qt.CursorShape.WaitCursor',
    'Qt.NoFocus': 'Qt.FocusPolicy.NoFocus',
    'Qt.ClickFocus': 'Qt.FocusPolicy.ClickFocus',
    'Qt.RichText': 'Qt.TextFormat.RichText',
    'Qt.AlignCenter': 'Qt.AlignmentFlag.AlignCenter',
    'Qt.MatchExactly': 'Qt.MatchFlag.MatchExactly',
    'Qt.AscendingOrder': 'Qt.SortOrder.AscendingOrder',
    'QDialog.Accepted': 'QDialog.DialogCode.Accepted',
    'QFrame.Panel': 'QFrame.Shape.Panel',
    'QFrame.Raised': 'QFrame.Shadow.Raised',
    'QFrame.Sunken': 'QFrame.Shadow.Sunken',
    'QEvent.MouseButtonRelease': 'QEvent.Type.MouseButtonRelease',
    'QEvent.KeyPress': 'QEvent.Type.KeyPress',
    'QSizePolicy.Fixed': 'QSizePolicy.Policy.Fixed',
    'QAbstractItemView.PositionAtTop':
        'QAbstractItemView.ScrollHint.PositionAtTop',
    'QTextDocument.FindBackward': 'QTextDocument.FindFlag.FindBackward',
    'QValidator.Acceptable': 'QValidator.State.Acceptable',
    'QValidator.Invalid': 'QValidator.State.Invalid',
    'QPalette.Highlight': 'QPalette.ColorRole.Highlight',
    'QPalette.Text': 'QPalette.ColorRole.Text',
}
for _key in ('Up', 'Down', 'PageUp', 'PageDown', 'Return', 'Enter', 'Tab'):
    ENUMS['Qt.Key_' + _key] = 'Qt.Key.Key_' + _key

# Exact replacements deliberately fail loudly if the audited code has changed.
SPECIAL = {
    'helpview.py': [
        ('from PyQt6.QtGui import QTextDocument',
         'from PyQt6.QtGui import QAction, QTextDocument'),
        ('from PyQt6.QtWidgets import (QAction, QLabel,',
         'from PyQt6.QtWidgets import (QLabel,'),
        ('self.textView.highlighted[str].connect(self.showLink)',
         'self.textView.highlighted.connect(self.showLink)'),
        ('def showLink(self, text):', 'def showLink(self, url):'),
        ('self.statusBar().showMessage(text)',
         'self.statusBar().showMessage(url.toString())'),
    ],
    'colorset.py': [
        ('QPushButton, QVBoxLayout, qApp)', 'QPushButton, QVBoxLayout)'),
        ('qApp.', 'QApplication.instance().'),
        ("eval('QPalette.' + groupStr)",
         'getattr(QPalette.ColorGroup, groupStr)'),
        ("eval('QPalette.' + roleStr)",
         'getattr(QPalette.ColorRole, roleStr)'),
    ],
    'fontset.py': [('QFontDatabase()', 'QFontDatabase')],
}

# The numeric engine must remain byte-for-byte identical in this experiment.
ENGINE = ('unitatom.py', 'unitdata.py', 'unitgroup.py', 'cmdline.py',
          'option.py', 'optiondefaults.py', 'recentunits.py')


def transform(text, name):
    if "from PyQt6." in text and "from PyQt5." not in text:
        return text, {}  # current production Qt6 tree: no prototype rewrite
    changes = {}
    count = text.count('from PyQt5.')
    if count:
        text = text.replace('from PyQt5.', 'from PyQt6.')
        changes['imports'] = count
    count = text.count('.exec_(')
    if count:
        text = text.replace('.exec_(', '.exec(')
        changes['exec'] = count
    for old, new in ENUMS.items():
        text, count = re.subn(r'\b' + re.escape(old) + r'\b', new, text)
        if count:
            changes[old] = count
    for old, new in SPECIAL.get(name, ()):
        count = text.count(old)
        if not count:
            raise ValueError('Audited expression missing in %s: %s' % (name, old))
        text = text.replace(old, new)
        changes[old] = count
    ast.parse(text, filename=name)
    return text, changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('.'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    if not (source / 'source' / 'convertall.py').is_file():
        parser.error('--source must be a ConvertAll repository or source archive')
    if output.exists():
        parser.error('--output already exists; select a new directory')
    if output == source or output in source.parents:
        parser.error('--output must not replace the source directory or its parents')
    if output.is_relative_to(source):
        first = output.relative_to(source).parts[0]
        if first in ('source', 'data', 'doc', 'icons', 'translations', '.git'):
            parser.error('--output must not be inside an application resource directory')
    output.mkdir(parents=True)
    for directory in ('source', 'data', 'doc', 'icons', 'translations', 'win'):
        shutil.copytree(source / directory, output / directory,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for filename in ('install.py', 'uninstall.py', 'convertall.desktop', 'README.md'):
        shutil.copy2(source / filename, output / filename)
    manifest = {
        'purpose': 'isolated Qt6 feasibility prototype, not a release',
        'changes': {}, 'unchanged_engine_sha256': {},
    }
    for path in sorted((output / 'source').glob('*.py')):
        original = path.read_text(encoding='utf-8')
        text, changes = transform(original, path.name)
        if changes:
            path.write_text(text, encoding='utf-8')
            manifest['changes']['source/' + path.name] = changes
    for filename in ENGINE:
        before = (source / 'source' / filename).read_bytes()
        after = (output / 'source' / filename).read_bytes()
        if before != after:
            raise AssertionError('Experiment changed the engine: ' + filename)
        manifest['unchanged_engine_sha256'][filename] = hashlib.sha256(before).hexdigest()
    # The original install.py, .spec, .pro and .iss remain unchanged on purpose.
    # The report explains their separate production migration requirements.
    (output / 'prototype-manifest.json').write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print('Isolated prototype:', output)
    print('Modified GUI modules:', len(manifest['changes']))
    print('Engine/data/installer untouched. See prototype-manifest.json.')


if __name__ == '__main__':
    main()
