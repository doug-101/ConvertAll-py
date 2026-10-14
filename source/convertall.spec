# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 6.22.3, Qt6 only. Run from any cwd using an absolute spec path.
# Flat onedir layout is retained for resource loading and Inno Setup.
from pathlib import Path
import sys
from PyInstaller.utils.hooks import copy_metadata

source = Path(SPECPATH).resolve()
root = source.parent
resources = [(str(root / name), name) for name in ('data', 'doc', 'icons')]
# Existing application QM files are readable by Qt6. Widget translations come
# from PyQt6's qtbase catalogue via the PyInstaller Qt hook, never Qt5 qt_*.qm.
resources += [(str(path), 'translations')
              for pattern in ('convertall_*.qm', 'convertall_*.ts')
              for path in (root / 'translations').glob(pattern)]
resources += [(str(path), 'source') for pattern in ('*.py', '*.pro', '*.spec')
              for path in source.glob(pattern)]
resources += [(str(path), '.') for path in (root / 'win').iterdir()
              if path.is_file()]
# --runtime-info reads the real distribution version, not SIP_VERSION_STR
# (the generator version). Normalize the destination for the Inno recipes.
resources += [(path, 'PyQt6_sip-13.13.0.dist-info')
              for path, destination in copy_metadata('PyQt6-sip')]

analysis = Analysis(
    [str(source / 'convertall.py')],
    pathex=[str(source)],
    binaries=[],
    datas=resources,
    hiddenimports=['PyQt6.QtWidgets', 'PyQt6.sip'],
    hookspath=[],
    runtime_hooks=[],
    excludes=['PyQt5', 'PySide6', 'PySide2'],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
windows = sys.platform == 'win32'
common = dict(exclude_binaries=True, debug=False, strip=False, upx=False,
              contents_directory='.')
if windows:
    common['icon'] = str(root / 'win' / 'convertall.ico')
gui = EXE(pyz, analysis.scripts, [], name='convertall',
          console=not windows, **common)
executables = [gui]
if windows:
    cli = EXE(pyz, analysis.scripts, [], name='convertall_dos', console=True,
              **common)
    executables.append(cli)
collection = COLLECT(*executables, analysis.binaries, analysis.datas,
                     strip=False, upx=False, name='convertall')
