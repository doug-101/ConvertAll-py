#!/usr/bin/env python3
"""Exercise a native PyInstaller flat onedir Qt6 bundle.

python tools/check_bundle.py dist/convertall --report build/test-results/bundle-validation.json
Checks actual frozen runtime versions, both entry points, every unit catalogue,
application/widget translations and GUI resources. Preferences are isolated.
The optional report binds checks to bundle file hashes and the checker's Git
checkout; this is not an independent attestation of the binary's build commit.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'source'))
# QtCore only; no QtWidgets/QApplication in the checker process.
from convertall import __version__


def validate_runtime_info(runtime):
    """Check wheel/runtime pins without treating the SIP generator as a wheel."""
    expected = {'application': 'ConvertAll', 'version': __version__, 'binding': 'PyQt6',
                'pyqt_binding': '6.11.0', 'qt_runtime': '6.11.2',
                'sip_package': '13.13.0'}
    if not isinstance(runtime, dict) or any(runtime.get(key) != value for key, value in expected.items()):
        raise RuntimeError(f'Wrong frozen Qt6 runtime: {runtime}; expected {expected}')
    generator = runtime.get('sip_generator')
    if not isinstance(generator, str) or not generator:
        raise RuntimeError('Missing SIP generator version in frozen runtime information')


def check_bundle(directory):
    directory = Path(directory).resolve()
    gui = directory / ('convertall.exe' if sys.platform == 'win32' else 'convertall')
    cli = directory / ('convertall_dos.exe' if sys.platform == 'win32' else 'convertall')
    for path in (gui, cli, directory / 'data/units.dat',
                 directory / 'doc/LICENSE', directory / 'doc/LICENSE-GPL-3.0',
                 directory / 'icons/convertall_med.png',
                 directory / 'translations/convertall_fr.qm'):
        if not path.is_file():
            raise RuntimeError(f'Missing bundle resource: {path}')
    if (directory / '_internal').exists():
        raise RuntimeError('Expected the flat --contents-directory=. layout')
    for path in directory.rglob('*'):
        name = path.name.lower()
        qt5_library = name.startswith(('qt5core', 'qt5gui', 'qt5widgets', 'qt5network',
                                       'qt5svg', 'qt5printsupport', 'libqt5'))
        if name.startswith(('pyqt5', 'pyside')) or name == 'qt5' or qt5_library:
            raise RuntimeError('Another Qt binding/library leaked into the Qt6 bundle')
    with tempfile.TemporaryDirectory(prefix='convertall-bundle-test-') as temp:
        home = Path(temp)
        env = os.environ.copy()
        env.update({'HOME': temp, 'APPDATA': str(home / 'appdata'),
                    'QT_QPA_PLATFORM': 'offscreen', 'LC_MESSAGES': 'C',
                    'LANG': 'C.UTF-8', 'PYTHONIOENCODING': 'utf-8'})
        env.pop('PYTHONPATH', None)
        env.pop('QT_PLUGIN_PATH', None)
        env.pop('QT_QPA_PLATFORM_PLUGIN_PATH', None)
        if sys.platform == 'win32' and not env.get('QT_QPA_FONTDIR'):
            windows = env.get('WINDIR') or env.get('SystemRoot')
            if windows and (Path(windows) / 'Fonts').is_dir():
                env['QT_QPA_FONTDIR'] = str(Path(windows) / 'Fonts')
        def run(program, *args):
            result = subprocess.run([str(program), *args], env=env, cwd=home,
                                    capture_output=True, text=True, encoding='utf-8',
                                    errors='replace', timeout=45)
            if result.returncode:
                raise RuntimeError(f'{program.name} {args}: exit {result.returncode}\n'
                                   f'{result.stdout}\n{result.stderr}')
            return result.stdout
        version = run(cli, '--version').strip()
        if version != f'ConvertAll {__version__} (Qt6)':
            raise RuntimeError(f'Wrong bundle version: {version}')
        runtime = json.loads(run(cli, '--runtime-info'))
        validate_runtime_info(runtime)
        translations = Path(runtime['qt_translations_path']).resolve()
        if not translations.is_relative_to(directory):
            raise RuntimeError(f'Qt6 translations escaped the bundle: {translations}')
        for language in ('ca', 'de', 'es', 'fr', 'ru', 'sv'):
            path = translations / f'qtbase_{language}.qm'
            if not path.is_file() or not path.stat().st_size:
                raise RuntimeError(f'Missing bundled Qt6 widget catalogue: {path}')
        cases = [('1', 'in', 'cm', 2.54), ('0', 'C', 'F', 32.0),
                 ('30', 'dBm', 'W', 1.0), ('1', 'kWh', 'J', 3600000.0)]
        for value, source, target, expected_value in cases:
            text = run(cli, '-q', value, source, target)
            actual = float(text.split('=', 1)[1].strip().split()[0])
            if abs(actual - expected_value) > 1e-8 * abs(expected_value):
                raise RuntimeError(f'Wrong frozen conversion: {text}')
        validation = run(cli, '--test-all')
        if validation.count('All units pass tests') != 7:
            raise RuntimeError(f'Not every bundled catalogue was validated:\n{validation}')
        for locale in ('fr_FR.UTF-8', 'ca_ES.UTF-8', 'sv_SE.UTF-8'):
            env['LC_MESSAGES'] = locale
            validation = run(cli, '--test')
            if 'Warning' in validation or 'All units pass tests' not in validation:
                raise RuntimeError(f'Frozen translations not loadable: {locale}\n{validation}')
        env['LC_MESSAGES'] = 'C'
        if 'GUI smoke test passed' not in run(cli, '--gui-smoke-test'):
            raise RuntimeError('Console entry point did not run the Qt widget smoke test')
        run(gui, '--gui-smoke-test')
    hashes = {}
    for path in sorted(directory.rglob('*')):
        if path.is_file():
            with path.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            hashes[path.relative_to(directory).as_posix()] = digest
    try:
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                                         text=True, stderr=subprocess.DEVNULL).strip()
        dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT,
                                             text=True, stderr=subprocess.DEVNULL).strip())
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = None, None
    print(f'Qt6 {__version__} bundle passed: CLI, 7 catalogues, translations, GUI/resources')
    return {'status': 'PASS', 'binding': 'Qt6', 'version': __version__, 'runtime': runtime,
            'timestamp_utc': datetime.now(timezone.utc).isoformat(),
            'checker_source_commit': commit, 'checker_working_tree_dirty': dirty,
            'bundle_sha256': hashes, 'qt_platform': 'offscreen'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    try:
        report = check_bundle(args.directory)
        code = 0
    except (RuntimeError, OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired) as error:
        print(f'Bundle validation failed: {error}', file=sys.stderr)
        report = {'status': 'FAIL', 'error': str(error), 'binding': 'Qt6'}
        code = 1
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return code


if __name__ == '__main__':
    sys.exit(main())
