#!/usr/bin/env python3
"""Build/check a small architecture-all .deb using Debian's SYSTEM Python/Qt.

User/CI-run only. No apt, pip, sudo, tag or release is performed.

Milestones are always printed; on GitHub Actions the few important ones are
also published as annotations, so a failure stays diagnosable even when job
logs and artifacts cannot be downloaded.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import traceback

import linux_release as packages
from linux_release import ReleaseError
from release_source import version_from_source

ROOT = Path(__file__).resolve().parents[1]
STEP = {'name': 'startup'}
TRACE = []


def log(message):
    """Fine-grained milestone: always in the log, kept in the report."""
    TRACE.append(f'{STEP["name"]}: {message}')
    print(f'[native-deb] {message}', flush=True)


def note(message):
    """Important milestone, also published as a GitHub annotation."""
    log(message)
    if os.environ.get('GITHUB_ACTIONS'):
        print(f'::notice title=ConvertAll native .deb::{message}', flush=True)


def report_failure(output_dir, error, detail):
    """Fail loudly and readably, including on CI where logs may be unavailable."""
    text = f'step={STEP["name"]}\nerror={error}\n{detail}'
    text += '\nlast milestones:\n' + '\n'.join(TRACE[-3:])
    for directory in (Path(output_dir), ROOT / 'build/native-debian'):
        try:
            directory.mkdir(parents=True, exist_ok=True)
            (directory / 'native-deb-failure.txt').write_text(text, encoding='utf-8')
            break  # one report is enough; never litter twice
        except OSError:
            pass
    print(f'Native Debian package FAILED at [{STEP["name"]}]: {error}', file=sys.stderr)
    if os.environ.get('GITHUB_ACTIONS'):
        lines = text.splitlines()
        flat = ' | '.join(lines[:2])
        if len(lines) > 2:
            flat += ' | ' + ' | '.join(lines[2:])[-620:]
        print(f'::error title=Native Debian package failed ({STEP["name"]})::{flat[:900]}',
              flush=True)


def environment(home=None):
    env = os.environ.copy()
    for key in ('PYTHONPATH', 'PYTHONHOME', 'LD_LIBRARY_PATH', 'QT_PLUGIN_PATH',
                'QT_QPA_PLATFORM_PLUGIN_PATH', 'APPDIR', 'APPIMAGE'):
        env.pop(key, None)
    env.update(QT_QPA_PLATFORM='offscreen', LANG='C.UTF-8', LC_MESSAGES='C',
               PYTHONIOENCODING='utf-8')
    if home is not None:
        env.update(HOME=str(home), APPDATA=str(home / 'appdata'), XDG_CONFIG_HOME=str(home / 'config'))
    return env


def run(arguments, *, cwd=ROOT, env=None):
    try:
        result = subprocess.run(list(map(str, arguments)), cwd=cwd, env=env,
                                capture_output=True, text=True, encoding='utf-8', timeout=180)
    except OSError as error:
        raise ReleaseError(f'{arguments[0]} could not be executed: {error}') from error
    if result.returncode:
        output = '\n'.join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
        raise ReleaseError(f'{arguments[0]} failed ({result.returncode}):\n{output[-900:]}')
    return result.stdout


def git(*arguments):
    """Run git for this checkout only.

    Container CI mounts the workspace with a different owner, so plain `git`
    refuses to work ("detected dubious ownership"). Trusting exactly this
    repository through -c keeps the fix local instead of editing global config.
    """
    return run(['git', '-c', f'safe.directory={ROOT}', *arguments])


def runtime_json(output):
    """Read the JSON runtime report even if warnings were printed before it."""
    for line in reversed(output.splitlines()):
        stripped = line.strip()
        if stripped.startswith('{') and stripped.endswith('}'):
            return json.loads(stripped)
    raise ReleaseError(f'No runtime JSON report in launcher output:\n{output[-700:]}')


def probe_system(version):
    runtime = runtime_json(run(['/usr/bin/python3', '-E', '-s', ROOT / 'source/convertall.py',
                                '--runtime-info'], env=environment()))
    packages.validate_debian_runtime(runtime, version)
    note('system runtime ok: python={} pyqt={} qt={} sip={}/{} translations={}'.format(
        runtime.get('python_version'), runtime.get('pyqt_binding'), runtime.get('qt_runtime'),
        runtime.get('sip_package'), runtime.get('sip_generator'),
        runtime.get('qt_translations_path')))
    return runtime


def stage(name):
    """Record which packaging stage owns any failure."""
    class Stage:
        def __enter__(self):
            STEP['name'] = name
        def __exit__(self, *exception):
            return False
    return Stage()


def check_extracted(directory, work, version):
    packages.verify_thin_deb_payload(directory)
    log('thin payload accepted: six application catalogues, seven unit files, no runtime')
    home = work / 'test-home'
    home.mkdir()
    env = environment(home)
    launcher = directory / 'usr/bin/convertall'
    def launch(*arguments):
        return run([launcher, *arguments], cwd=home, env=env)
    runtime = runtime_json(launch('--runtime-info'))
    packages.validate_debian_runtime(runtime, version)
    note('extracted launcher ok: {} using {} (Qt translations: {})'.format(
        runtime.get('python_executable'), runtime.get('pyqt_location'),
        runtime.get('qt_translations_path')))
    qt_path = Path(runtime['qt_translations_path']).resolve()
    if qt_path.is_relative_to(directory.resolve()):
        raise ReleaseError('Thin .deb used bundled Qt translations instead of the system package')
    expected = [('1', 'in', 'cm', 2.54), ('0', 'C', 'F', 32.0),
                ('30', 'dBm', 'W', 1.0), ('1', 'kWh', 'J', 3600000.0)]
    for value, source, target, result in expected:
        text = launch('-q', value, source, target)
        actual = float(text.split('=', 1)[1].strip().split()[0])
        if abs(actual - result) > 1e-8 * abs(result):
            raise ReleaseError(f'Wrong native Debian conversion: {text}')
    log('four conversions exact (in/cm, C/F, dBm/W, kWh/J)')
    if launch('--test-all').count('All units pass tests') != 7:
        raise ReleaseError('Not every native Debian catalogue passed')
    log('seven unit catalogues pass their self-tests')
    app_translations = Path(directory) / 'usr/share/convertall/translations'
    language_report = {}
    for locale in ('fr_FR.UTF-8', 'ca_ES.UTF-8', 'sv_SE.UTF-8'):
        env['LC_MESSAGES'] = locale
        text = launch('--test')
        if 'All units pass tests' not in text:
            raise ReleaseError(f'Native Debian unit test failed for {locale}')
        names = packages.translation_warning_names(text)
        expected = packages.expected_missing_translations(
            locale, runtime['qt_translations_path'], app_translations)
        # Only a genuinely absent distribution widget catalogue may warn; the
        # application's own catalogue must never be the missing one.
        if names != expected or any(name.startswith('convertall_') for name in names):
            raise ReleaseError(f'Native Debian translations mismatched for {locale}: '
                               f'warnings={names}, expected={expected}')
        language_report[locale] = {
            'widget_catalogue_present': not any(name.startswith('qt_') for name in expected),
            'warnings': names}
        log(f'{locale}: warnings={names or "none"} expected={expected or "none"}')
    note('translations exact: ' + '; '.join(
        f'{locale} warns {report["warnings"] or "nothing"}'
        for locale, report in language_report.items()))
    env['LC_MESSAGES'] = 'C'
    if 'GUI smoke test passed' not in launch('--gui-smoke-test'):
        raise ReleaseError('Native Debian GUI/resources failed')
    note('GUI smoke test opened the window with icons and help file')
    return {'status': 'PASS', 'runtime': runtime, 'qt_platform': 'offscreen',
            'tests': ['runtime-origin', 'four-conversions', 'seven-catalogues',
                      'system-qtbase/app-translations', 'gui-resources'],
            'languages': language_report,
            'milestones': list(TRACE),
            'manual_installation_tested': False}


def build(output, work, maintainer):
    commit = git('rev-parse', 'HEAD').strip()
    dirty = git('status', '--porcelain').strip()
    if dirty:
        raise ReleaseError('Thin Debian release requires a clean committed tree:\n' + dirty[:600])
    if os.environ.get('GITHUB_SHA', commit) != commit:
        raise ReleaseError('Native Debian checkout differs from GITHUB_SHA: '
                           f'{os.environ.get("GITHUB_SHA")} != {commit}')
    note(f'git gates passed at {commit[:12]} (clean tree, GITHUB_SHA match)')
    version = version_from_source((ROOT / 'source/convertall.py').read_text(encoding='utf-8'))
    packages.deb_control(version, maintainer, 1)
    with stage('probe distribution Qt with /usr/bin/python3'):
        probe_system(version)  # Do not validate with the wheel venv.
    output, work = Path(output).resolve(), Path(work).resolve()
    if any(path == ROOT or ROOT.is_relative_to(path) for path in (output, work)):
        raise ReleaseError('Use dedicated output/work directories, never the repository root/parent')
    work.mkdir(parents=True, exist_ok=False)
    output.mkdir(parents=True, exist_ok=True)
    with stage('stage application files'):
        staged = packages.stage_deb(work / 'stage', ROOT, version, maintainer)
        payload = {name: digest for name, digest in packages.file_hashes(staged).items()
                   if not name.startswith('DEBIAN/')}
        run(['desktop-file-validate', staged / 'usr/share/applications/convertall.desktop'])
        log(f'staged {len(payload)} files for {version}, desktop entry validated')
    deb = output / f'convertall_{version}-1_all.deb'
    if deb.exists():
        raise ReleaseError('Debian output already exists; no overwrite is performed')
    with stage('build .deb with dpkg-deb'):
        env = environment()
        env['SOURCE_DATE_EPOCH'] = git('show', '-s', '--format=%ct', commit).strip()
        run(['dpkg-deb', '--root-owner-group', '-Zxz', '-z9', '--build', staged, deb], env=env)
        extracted = work / 'extracted'
        run(['dpkg-deb', '--extract', deb, extracted])
        packages.verify_payload(extracted, payload)
        note(f'built {deb.name} ({deb.stat().st_size} bytes); every payload hash verified')
    with stage('execute extracted package'):
        checks = check_extracted(extracted, work, version)
    if commit != git('rev-parse', 'HEAD').strip() or git('status', '--porcelain').strip():
        raise ReleaseError('Git inputs changed during native Debian packaging')
    report = {**checks, 'version': version, 'source_commit': commit,
              'package': deb.name, 'architecture': 'all', 'runtime_profile': 'debian-system-qt',
              'bundled_runtime': False, 'depends': list(packages.DEBIAN_DEPENDENCIES),
              'package_sha256': packages.sha256(deb), 'package_bytes': deb.stat().st_size,
              'payload_sha256': payload, 'build_os_release': platform.freedesktop_os_release()}
    report_path = output / 'native-deb-validation.json'
    packages.write_file(report_path, json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    note(f'native .deb validation report written: {report_path}')
    print(f'PASS thin Debian package: {deb}\nBytes: {deb.stat().st_size}\nReport: {report_path}')
    return deb, report_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe-system', action='store_true', help='check native Qt dependencies only')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'dist/debian')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + f'-{os.getpid()}'
    parser.add_argument('--work-dir', type=Path, default=ROOT / 'build/debian' / stamp)
    parser.add_argument('--maintainer', help='public package identity: Name <email>')
    args = parser.parse_args()
    try:
        if args.probe_system:
            STEP['name'] = 'probe distribution Qt with /usr/bin/python3'
            version = version_from_source((ROOT / 'source/convertall.py').read_text(encoding='utf-8'))
            print(json.dumps(probe_system(version), ensure_ascii=False))
        else:
            if not args.maintainer:
                raise ReleaseError('Provide --maintainer "Name <email>"')
            build(args.output_dir, args.work_dir, args.maintainer)
        return 0
    except Exception as error:  # every failure must stay reportable, even unexpected ones
        report_failure(args.output_dir, error, traceback.format_exc(limit=12)[-1800:]
                       + '\nRequired system dependencies: python3-pyqt6 python3-pyqt6.sip qt6-translations-l10n')
        return 1


if __name__ == '__main__':
    sys.exit(main())
