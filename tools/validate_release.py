#!/usr/bin/env python3
"""Qt6 release gate: pinned environment, tests, coverage and input provenance.

Reports go to build/test-results (ignored by Git). Never publishes anything.
--require-clean enforces a Git checkout suitable for release/CI validation.
Without it, development/extracted-tree tests are allowed but not certification.
The Qt5 baseline is frozen at b10b8e7; use its archived checkout for Qt5 QA.
"""
import argparse
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def expected_packages():
    return {'PyQt6': '6.11.0', 'PyQt6-sip': '13.13.0', 'PyQt6-Qt6': '6.11.2',
            'pytest': '9.1.1', 'pytest-qt': '4.5.0',
            'pytest-cov': '7.1.0', 'coverage': '7.16.2'}


def input_hashes():
    paths = []
    for name in ('source', 'data', 'icons', 'translations', 'doc', 'docs',
                 'tests', 'tools', 'win', '.github'):
        paths += [p for p in (ROOT / name).rglob('*') if p.is_file()
                  and '__pycache__' not in p.parts and p.suffix != '.pyc']
    paths += [ROOT / name for name in ('install.py', 'uninstall.py', 'README.md',
                                      'requirements-qt5.txt', 'requirements-qt6.txt',
                                      'requirements-test.txt', 'requirements-build.txt', 'requirements-test-debian.txt',
                                      'pytest.ini', '.coveragerc', '.gitignore',
                                      '.gitattributes', 'convertall.desktop',
                                      'test_all_qt5.sh', 'test_all_qt6.sh', 'release_qt6.sh')]
    return {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(paths)}


def git_state():
    try:
        def git(*args):
            return subprocess.check_output(['git', *args], cwd=ROOT, text=True,
                                           stderr=subprocess.DEVNULL).strip()
        return {'commit': git('rev-parse', 'HEAD'),
                'branch': git('branch', '--show-current'),
                'working_tree_dirty': bool(git('status', '--porcelain'))}
    except (OSError, subprocess.CalledProcessError):
        return {'commit': None, 'branch': None, 'working_tree_dirty': None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-clean', action='store_true')
    args = parser.parse_args()
    results = ROOT / 'build/test-results'
    results.mkdir(parents=True, exist_ok=True)
    start = git_state()
    environment = os.environ.copy()
    environment.setdefault('QT_QPA_PLATFORM', 'offscreen')
    environment['QT_API'] = 'pyqt6'
    if (sys.platform == 'win32'
            and environment['QT_QPA_PLATFORM'].split(':', 1)[0] == 'offscreen'
            and not environment.get('QT_QPA_FONTDIR')):
        windows = environment.get('WINDIR') or environment.get('SystemRoot')
        if windows and (Path(windows) / 'Fonts').is_dir():
            environment['QT_QPA_FONTDIR'] = str(Path(windows) / 'Fonts')
    report = {'timestamp_utc': datetime.now(timezone.utc).isoformat(),
              'binding': 'Qt6', 'python': sys.version, 'executable': sys.executable,
              'platform': platform.platform(), 'machine': platform.machine(),
              'qt_platform': environment.get('QT_QPA_PLATFORM'),
              'qt_fontdir': environment.get('QT_QPA_FONTDIR'),
              **start, 'require_clean': args.require_clean, 'release_eligible': False,
              'pytest_exit_code': None, 'expected_packages': expected_packages()}
    def fail(message):
        print(message, file=sys.stderr)
        report['prerequisite_error'] = message
        (results / 'validation.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        return 2
    if not (3, 11) <= sys.version_info[:2] <= (3, 14):
        return fail('Qt6 release validation requires Python 3.11–3.14')
    try:
        installed = {name: metadata.version(name) for name in expected_packages()}
    except metadata.PackageNotFoundError as error:
        return fail(f'{error}\nInstall requirements-test.txt in a fresh Qt6 venv.')
    report['packages'] = installed
    if installed != expected_packages():
        return fail(f'Incorrect release environment: {installed}\nExpected: {expected_packages()}')
    for name in ('PyQt5', 'PySide2', 'PySide6'):
        try:
            metadata.version(name)
        except metadata.PackageNotFoundError:
            continue
        return fail(f'Mixed Qt bindings: {name} is installed. Use a clean Qt6 venv.')
    try:
        from PyQt6.QtCore import PYQT_VERSION_STR, qVersion
        from PyQt6 import sip
        report.update(pyqt_binding=PYQT_VERSION_STR, qt_runtime=qVersion(),
                      sip_package=installed['PyQt6-sip'], sip_generator=sip.SIP_VERSION_STR)
    except ImportError as error:
        return fail(f'Qt6 cannot be imported: {error}')
    if report['pyqt_binding'] != installed['PyQt6'] or report['qt_runtime'] != installed['PyQt6-Qt6']:
        return fail('Loaded Qt6 runtime/binding do not match the installed pinned wheels.')
    if args.require_clean and (not start['commit'] or start['working_tree_dirty']):
        return fail('A clean committed Git checkout is required for release validation.')
    expected_sha = environment.get('GITHUB_SHA')
    if expected_sha and start['commit'] != expected_sha:
        return fail(f'CI checkout SHA {start["commit"]} differs from GITHUB_SHA {expected_sha}.')
    if subprocess.run([sys.executable, '-m', 'pip', 'check'], cwd=ROOT).returncode:
        return fail('pip check failed.')
    before = input_hashes()
    command = [sys.executable, '-m', 'pytest', '-q', '--cov=source', '--cov-branch',
               '--cov-report=term-missing:skip-covered',
               '--cov-report=xml:build/test-results/coverage.xml',
               '--cov-report=json:build/test-results/coverage.json',
               '--junitxml=build/test-results/junit.xml']
    result = subprocess.run(command, cwd=ROOT, env=environment)
    finish = git_state()
    unchanged = before == input_hashes()
    same_commit = start['commit'] == finish['commit']
    if not unchanged or not same_commit:
        print('Inputs or commit changed during validation: rerun on the final tree.', file=sys.stderr)
    eligible = (result.returncode == 0 and unchanged and same_commit
                and bool(start['commit']) and not start['working_tree_dirty']
                and not finish['working_tree_dirty'])
    report.update(input_sha256=before, inputs_unchanged=unchanged, commit_unchanged=same_commit,
                  final_git_state=finish, pytest_exit_code=result.returncode,
                  command=command, release_eligible=eligible)
    (results / 'validation.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    if result.returncode:
        return result.returncode
    if not unchanged or not same_commit or (args.require_clean and not eligible):
        return 1
    if not eligible:
        print('Development tests only: this dirty/extracted tree is not release-certified.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
