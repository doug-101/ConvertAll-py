#!/usr/bin/env python3
"""Compatibility entry point for the supported Qt6 PyInstaller build.

The historical cx_Freeze recipe belongs to the archived Qt5 commit b10b8e7.
Use `python -m PyInstaller --noconfirm --clean source/convertall.spec` instead.
This wrapper keeps `python source/setup.py build` usable, from any directory.
"""
from pathlib import Path
import subprocess
import sys


def main():
    source = Path(__file__).resolve().parent
    if sys.argv[1:] in ([], ['-h'], ['--help']):
        print('Usage: python source/setup.py build')
        print('Qt6 packaging uses PyInstaller and requirements-build.txt, not cx_Freeze.')
        return 0
    if sys.argv[1:] != ['build']:
        print('Unsupported legacy packaging option; use the PyInstaller spec.', file=sys.stderr)
        return 2
    from convertall import __version__
    print(f'Building ConvertAll {__version__} (Qt6) with PyInstaller')
    return subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
                           str(source / 'convertall.spec')], cwd=source.parent).returncode


if __name__ == '__main__':
    sys.exit(main())
