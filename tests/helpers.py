"""Subprocess helpers; timeouts make a hung event loop a test failure."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'source' / 'convertall.py'


def run_cli(*arguments, input='', env=None, script=SCRIPT, cwd=None, timeout=20):
    environment = os.environ.copy()
    environment.update({'QT_QPA_PLATFORM': 'offscreen', 'PYTHONIOENCODING': 'utf-8',
                        'LC_MESSAGES': 'C', 'LANG': 'C.UTF-8'})
    if env:
        environment.update(env)
    return subprocess.run([sys.executable, str(script), *map(str, arguments)],
                          input=input, text=True, encoding='utf-8',
                          capture_output=True, cwd=cwd or ROOT,
                          env=environment, timeout=timeout)


def copy_project(destination):
    destination.mkdir(parents=True)
    for name in ('source', 'data', 'doc', 'docs', 'icons', 'translations', 'win',
                 'tools', 'tests', '.github'):
        shutil.copytree(ROOT / name, destination / name,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for name in ('.gitignore', '.gitattributes', '.coveragerc', 'pytest.ini', 'README.md', 'install.py',
                 'uninstall.py', 'convertall.desktop', 'requirements-qt5.txt', 'requirements-test-debian.txt',
                 'requirements-qt6.txt', 'requirements-test.txt', 'requirements-build.txt',
                 'test_all_qt5.sh', 'test_all_qt6.sh', 'release_qt6.sh'):
        shutil.copy2(ROOT / name, destination / name)
    return destination
