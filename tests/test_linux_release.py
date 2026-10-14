"""Linux release recipes and CI/provenance guards; native packages are user-run."""
import copy
import io
import json
import os
from pathlib import Path
import shutil
from types import SimpleNamespace
import struct
import subprocess
import sys
import tarfile
import zipfile

import pytest

from helpers import ROOT
import linux_release as packages
from linux_release import ReleaseError
import release_qt6

pytestmark = pytest.mark.packaging
SHA = 'a' * 40


@pytest.fixture
def bundle(tmp_path):
    folder = tmp_path / 'bundle'
    folder.mkdir()
    for name, content in {'convertall': b'fake executable', 'data/units.dat': b'unit data',
                          'doc/LICENSE': b'GPL', 'PyQt6_sip-13.13.0.dist-info/METADATA': b'Version: 13.13.0'}.items():
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return folder


def report_for(bundle):
    return {'status': 'PASS', 'checker_source_commit': SHA, 'checker_working_tree_dirty': False,
            'runtime': {'application': 'ConvertAll', 'version': '0.9.0', 'binding': 'PyQt6',
                        'pyqt_binding': '6.11.0', 'qt_runtime': '6.11.2',
                        'sip_package': '13.13.0', 'sip_generator': '6.17.0'},
            'bundle_sha256': packages.file_hashes(bundle)}


def test_report_binds_every_byte_to_clean_sha(bundle):
    report = report_for(bundle)
    packages.verify_bundle_report(bundle, report, SHA, '0.9.0')
    (bundle / 'convertall').write_bytes(b'changed')
    with pytest.raises(ReleaseError, match='bytes differ'):
        packages.verify_bundle_report(bundle, report, SHA, '0.9.0')


@pytest.mark.parametrize('field,value', [('status', 'FAIL'), ('checker_source_commit', 'b' * 40),
                                         ('checker_working_tree_dirty', True)])
def test_bundle_provenance_cannot_be_bypassed(bundle, field, value):
    report = report_for(bundle)
    report[field] = value
    with pytest.raises(ReleaseError, match='clean PASS'):
        packages.verify_bundle_report(bundle, report, SHA, '0.9.0')


def test_bundle_extra_or_missing_files_are_rejected(bundle):
    report = report_for(bundle)
    (bundle / 'extra').write_text('unexpected', encoding='utf-8')
    with pytest.raises(ReleaseError, match='bytes differ'):
        packages.verify_bundle_report(bundle, report, SHA, '0.9.0')
    (bundle / 'extra').unlink()
    (bundle / 'data/units.dat').unlink()
    with pytest.raises(ReleaseError, match='Missing/invalid'):
        packages.verify_bundle_report(bundle, report, SHA, '0.9.0')


def test_bundle_report_tolerates_only_the_extras_packaging_adds(bundle, tmp_path):
    """A resumed run re-verifies the bundle that already holds the notices."""
    report = report_for(bundle)
    (bundle / 'doc/third-party/PyQt6').mkdir(parents=True)
    (bundle / 'doc/third-party/PyQt6/LICENSE').write_text('GPL', encoding='utf-8')
    (bundle / 'RELEASE-INFO.json').write_text('{}', encoding='utf-8')
    with pytest.raises(ReleaseError, match='bytes differ'):
        packages.verify_bundle_report(bundle, report, SHA, '0.9.0')
    allowed = ('doc/third-party/', 'RELEASE-INFO.json')
    packages.verify_bundle_report(bundle, report, SHA, '0.9.0', extra_prefixes=allowed)
    (bundle / 'stowaway.so').write_bytes(b'unrecorded')
    with pytest.raises(ReleaseError, match='bytes differ'):
        packages.verify_bundle_report(bundle, report, SHA, '0.9.0', extra_prefixes=allowed)


@pytest.mark.parametrize('name', ['', '.', '../secret', '/etc/passwd', 'a/../b', './file',
                                 'a\\b', 'nul\x00file'])
def test_artifact_paths_cannot_escape(tmp_path, name):
    with pytest.raises(ReleaseError, match='Unsafe'):
        packages.safe_file(tmp_path, name)


def test_source_archive_checks_real_sha_and_checksum(tmp_path):
    name = 'ConvertAll-0.9.0-qt6-source.tar.gz'
    archive = tmp_path / name
    archive.write_bytes(b'archive fixture')
    digest = packages.sha256(archive)
    archive.with_name(name + '.sha256').write_text(f'{digest}  {name}\n', encoding='ascii')
    info = {'source_commit': SHA, 'version': '0.9.0', 'binding': 'Qt6', 'sha256': digest}
    provenance = archive.with_name(name + '.provenance.json')
    provenance.write_text(json.dumps(info), encoding='utf-8')
    assert packages.verify_source_archive(tmp_path, '0.9.0', SHA)[0] == archive
    info['source_commit'] = 'b' * 40
    provenance.write_text(json.dumps(info), encoding='utf-8')
    with pytest.raises(ReleaseError, match='mismatch'):
        packages.verify_source_archive(tmp_path, '0.9.0', SHA)


def test_glibc_baseline_comes_from_elf_requirements_not_platform(bundle):
    (bundle / 'convertall').write_bytes(b'\x7fELFfixture')
    (bundle / 'libfixture.so').write_bytes(b'\x7fELFfixture')
    values = {'convertall': 'Name: GLIBC_2.9 Name: GLIBC_2.28',
              'libfixture.so': 'Name: GLIBC_2.34 Name: GLIBC_PRIVATE'}
    assert packages.glibc_requirement(bundle, lambda path: values[path.name]) == '2.34'
    with pytest.raises(ReleaseError, match='No GLIBC'):
        packages.glibc_requirement(bundle, lambda path: 'static binary')


def test_deb_uses_system_dependencies_without_copying_a_frozen_runtime(tmp_path):
    stage = packages.stage_deb(tmp_path / 'deb', ROOT, '0.9.3',
                               'Test Maintainer <test@example.invalid>')
    control = (stage / 'DEBIAN/control').read_text(encoding='utf-8')
    assert 'Package: convertall\nVersion: 0.9.3-1\nArchitecture: all\n' in control
    assert 'Depends: ' + ', '.join(packages.DEBIAN_DEPENDENCIES) in control
    assert 'python3-pyqt6 (>= 6.4.2)' in control
    assert 'libc6' not in control and 'Installed-Size: ' in control
    script = (stage / 'usr/bin/convertall').read_text(encoding='utf-8')
    assert 'exec /usr/bin/python3 -E -s "$HERE/../share/convertall/_debian_entry.py" "$@"' in script
    app = stage / 'usr/share/convertall'
    assert (app / 'convertall.py').read_bytes() == (ROOT / 'source/convertall.py').read_bytes()
    assert (app / 'data/units.dat').read_bytes() == (ROOT / 'data/units.dat').read_bytes()
    assert len(list((app / 'data').glob('*.dat'))) == 7
    assert len(list((app / 'translations').glob('convertall_*.qm'))) == 6
    assert not (stage / 'usr/lib/convertall').exists()
    assert not (app / 'PyQt6').exists() and not (app / 'setup.py').exists()
    assert not list(stage.rglob('*.so')) and not list(stage.rglob('*.dist-info'))
    assert not list(stage.rglob('*.ts'))
    packages.verify_thin_deb_payload(stage)
    assert (stage / 'usr/share/doc/convertall/LICENSE-GPL-3.0').is_file()
    assert (stage / 'usr/share/icons/hicolor/scalable/apps/convertall.svg').is_file()


@pytest.mark.parametrize('maintainer', ['missing-email', 'Name <mail>\nDepends: bad', 'Name <mail>'])
def test_deb_control_rejects_header_injection(maintainer):
    with pytest.raises(ReleaseError, match='Invalid Debian'):
        packages.deb_control('0.9.3', maintainer, 1)


def test_appdir_keeps_full_bundle_icon_and_argument_forwarding(bundle, tmp_path):
    stage = packages.stage_appdir(bundle, tmp_path / 'ConvertAll.AppDir', ROOT)
    assert 'exec "$HERE/usr/lib/convertall/convertall" "$@"' in (stage / 'AppRun').read_text()
    assert (stage / 'usr/lib/convertall/PyQt6_sip-13.13.0.dist-info/METADATA').is_file()
    assert (stage / '.DirIcon').read_bytes() == (ROOT / 'icons/convertall_lg.png').read_bytes()
    desktop = (stage / 'convertall.desktop').read_text(encoding='utf-8')
    assert 'Exec=convertall\nIcon=convertall\n' in desktop
    assert 'Terminal=false' in desktop and 'Categories=Education;Math;' in desktop


def test_portable_tar_is_repeatable_and_retains_executable(bundle, tmp_path):
    first, second = tmp_path / 'one.tar.gz', tmp_path / 'two.tar.gz'
    packages.make_tar(bundle, first, 1234567890)
    packages.make_tar(bundle, second, 1234567890)
    assert first.read_bytes() == second.read_bytes()
    with tarfile.open(first, 'r:gz') as archive:
        info = archive.getmember('bundle/convertall')
        assert info.mode == 0o755 and info.mtime == 1234567890
        assert info.uid == info.gid == 0
    out = tmp_path / 'extracted'
    out.mkdir()
    packages.extract_own_tar(first, out)
    assert (out / 'bundle/convertall').read_bytes() == (bundle / 'convertall').read_bytes()


@pytest.mark.parametrize('name,link', [('../escape', None), ('/absolute', None),
                                      ('bundle/link', '../../escape')])
def test_tar_extraction_rejects_unsafe_members(tmp_path, name, link):
    path = tmp_path / 'bad.tar.gz'
    with tarfile.open(path, 'w:gz') as archive:
        info = tarfile.TarInfo(name)
        if link is not None:
            info.type, info.linkname = tarfile.SYMTYPE, link
            archive.addfile(info)
        else:
            info.size = 1
            archive.addfile(info, io.BytesIO(b'x'))
    with pytest.raises(ReleaseError, match='Unsafe'):
        packages.extract_own_tar(path, tmp_path / 'out')


def test_windows_zip_contains_runtime_not_a_lone_exe(bundle, tmp_path):
    (bundle / 'convertall.exe').write_bytes(b'MZfixture')
    output = tmp_path / 'windows.zip'
    packages.make_windows_zip(bundle, output, 'ConvertAll-Windows', 1234567890)
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        assert archive.read('ConvertAll-Windows/convertall.exe') == b'MZfixture'
        assert archive.read('ConvertAll-Windows/data/units.dat') == b'unit data'
        assert archive.getinfo('ConvertAll-Windows/convertall.exe').external_attr >> 16 == 0o100755


def good_run():
    return {'head_sha': SHA, 'head_branch': release_qt6.BRANCH, 'path': release_qt6.WORKFLOW,
            'event': 'push', 'status': 'completed', 'conclusion': 'success'}


@pytest.mark.parametrize('field,value', [('head_sha', 'b' * 40), ('head_branch', 'master'),
                                         ('event', 'pull_request'), ('conclusion', 'failure'),
                                         ('status', 'in_progress'), ('path', 'another.yml')])
def test_release_requires_green_ci_of_exact_sha(field, value):
    run = good_run()
    release_qt6.validate_ci_run(run, SHA)
    run[field] = value
    with pytest.raises(ReleaseError, match='exact current SHA'):
        release_qt6.validate_ci_run(run, SHA)


def test_ci_requires_all_eight_tests_and_both_native_bundles():
    names = [f'Tests {os_name} / Python {version} / Qt6'
             for os_name in ('ubuntu-24.04', 'windows-2022') for version in ('3.11', '3.12', '3.13', '3.14')]
    names += ['Bundle ubuntu-24.04 / Qt6', 'Bundle windows-2022 / Qt6',
              'Debian native Qt / bookworm', 'Debian native Qt / trixie']
    jobs = [{'name': name, 'status': 'completed', 'conclusion': 'success'} for name in names]
    release_qt6.validate_ci_jobs(jobs)
    jobs[-1]['conclusion'] = 'skipped'
    with pytest.raises(ReleaseError, match='Missing/failed'):
        release_qt6.validate_ci_jobs(jobs)


CI_JOB_NAMES = ([f'Tests {os_name} / Python {version} / Qt6'
                 for os_name in ('ubuntu-24.04', 'windows-2022')
                 for version in ('3.11', '3.12', '3.13', '3.14')]
                + [f'Bundle {os_name} / Qt6' for os_name in ('ubuntu-24.04', 'windows-2022')]
                + [f'Debian native Qt / {suite}' for suite in ('bookworm', 'trixie')])


def ci_jobs_with(default_conclusion='success'):
    return [{'name': name, 'status': 'completed', 'conclusion': default_conclusion}
            for name in CI_JOB_NAMES]


@pytest.fixture
def fake_clock(monkeypatch):
    """A clock the polling code advances by sleeping, so tests stay instant."""
    clock = {'elapsed': 0.0}
    monkeypatch.setattr(release_qt6.time, 'monotonic', lambda: clock['elapsed'])
    monkeypatch.setattr(release_qt6.time, 'sleep',
                        lambda seconds: clock.__setitem__('elapsed', clock['elapsed'] + seconds))
    return clock


def ci_run(run_id, status='completed', conclusion='success'):
    return {'id': run_id, 'head_sha': SHA, 'head_branch': release_qt6.BRANCH,
            'path': release_qt6.WORKFLOW, 'event': 'push', 'status': status,
            'conclusion': conclusion}


def fake_github(runs, jobs_by_run):
    def github(endpoint, *, missing_ok=False):
        if '/actions/workflows/qt6-release.yml/runs?' in endpoint:
            return {'workflow_runs': list(runs)}
        if endpoint.endswith('/jobs?per_page=100'):
            return {'jobs': jobs_by_run[int(endpoint.split('/runs/')[1].split('/')[0])]}
        return runs[-1]
    return github


def test_ci_runs_only_for_the_configured_release_marker():
    """The workflow gate and the script constant must describe the same rule."""
    workflow = (ROOT / '.github/workflows/qt6-release.yml').read_text(encoding='utf-8')
    marker = release_qt6.CI_MARKER
    assert marker == '[PROD]'
    gate = f"contains(github.event.head_commit.message || '', '{marker}')"
    # `on:` mentions the event once; each of the three jobs carries the gate.
    assert workflow.count("github.event_name == 'workflow_dispatch'") == 3
    assert workflow.count(gate) == 4  # three jobs plus the concurrency group
    order = ['  tests:', '  native-deb:', '  bundle:']
    for index, header in enumerate(order):
        start = workflow.index('\n' + header)
        end = workflow.index('\n' + order[index + 1]) if index + 1 < len(order) else len(workflow)
        assert gate in workflow[start:end], header
        assert "github.event.pull_request.title || '', '" + marker + "'" in workflow[start:end]
    # A quiet push gets its own concurrency group: it can never cancel a marked run.
    assert "'release' || 'quiet'" in workflow
    for document in ('README.md', 'doc/RELEASE_LINUX_FR.md'):
        assert marker in (ROOT / document).read_text(encoding='utf-8'), document


class _StopAfterPreflight(Exception):
    """Sentinel: the flow under test must not go any further than the preflight."""


class _PinnedBuildTools:
    """PyInstaller is only installed in the release venv, never in the QA one."""

    versions = {'PyInstaller': '6.22.3', 'pyinstaller-hooks-contrib': '2026.8'}

    @staticmethod
    def version(name):
        return _PinnedBuildTools.versions[name]


def _preflight_stubs(monkeypatch, stopped):
    """Everything build_release reads before it stops being cheap: no network, no
    host tooling and no work directory, so the test only exercises control flow."""
    monkeypatch.setattr(release_qt6, 'require_clean_sha', lambda commit=None: SHA)
    monkeypatch.setattr(release_qt6, 'tag_target', lambda tag: None)
    monkeypatch.setattr(release_qt6, 'command', lambda *arguments, **kwargs: None)
    monkeypatch.setattr(release_qt6.shutil, 'which', lambda name: '/usr/bin/' + name)
    monkeypatch.setattr(release_qt6, 'metadata', _PinnedBuildTools)
    monkeypatch.setattr(release_qt6, 'previous_run', stopped)


@pytest.mark.skipif(sys.platform != 'linux', reason='build_release is Linux-only')
def test_a_local_rehearsal_survives_its_own_preflight(monkeypatch, capsys):
    """Regression: the rehearsal banner once ran before `run` was assigned, so every
    release died with UnboundLocalError before it could even ask for a maintainer."""
    _preflight_stubs(monkeypatch, _stop_during_preflight)
    args = SimpleNamespace(local_only=True, draft=False, run_id=None, wait_ci=False,
                           maintainer='Rehearsal Person <rehearsal@example.org>', resume='latest')
    with pytest.raises(_StopAfterPreflight):
        release_qt6.build_release(args)
    assert 'LOCAL REHEARSAL' in capsys.readouterr().out


@pytest.mark.skipif(sys.platform != 'linux', reason='build_release is Linux-only')
def test_a_real_release_still_names_its_ci_run(monkeypatch, capsys):
    monkeypatch.setattr(release_qt6, 'select_ci', lambda commit, run_id, wait: {'id': 7})
    _preflight_stubs(monkeypatch, _stop_during_preflight)
    args = SimpleNamespace(local_only=False, draft=False, run_id=None, wait_ci=True,
                           maintainer='Release Person <release@example.org>', resume='latest')
    with pytest.raises(_StopAfterPreflight):
        release_qt6.build_release(args)
    assert 'LOCAL REHEARSAL' not in capsys.readouterr().out


def _stop_during_preflight(*arguments, **kwargs):
    raise _StopAfterPreflight()


def test_a_maintainer_can_be_exported_once_for_every_run(monkeypatch):
    """One export must cover the release, a --resume and a rehearsal."""
    monkeypatch.setenv('CONVERTALL_MAINTAINER', '  Env Person <env@example.org>  ')
    assert release_qt6.maintainer_identity(None) == 'Env Person <env@example.org>'
    # The flag stays the most explicit source.
    assert release_qt6.maintainer_identity('Flag <flag@example.org>') == 'Flag <flag@example.org>'
    # An all-whitespace variable must not shadow the git identity.
    def configured(arguments, **kwargs):
        value = 'Git Person' if 'user.name' in arguments else 'git@example.org'
        return subprocess.CompletedProcess(arguments, 0, value + '\n', '')

    monkeypatch.setattr(release_qt6.subprocess, 'run', configured)
    assert (release_qt6.maintainer_identity(None, {'CONVERTALL_MAINTAINER': '   '})
            == 'Git Person <git@example.org>')


def test_a_missing_maintainer_says_exactly_what_to_do(monkeypatch):
    """The missing-maintainer failure of the previous release must be self-explaining."""
    monkeypatch.delenv('CONVERTALL_MAINTAINER', raising=False)

    def no_identity(*arguments, **kwargs):
        return subprocess.CompletedProcess(arguments, 1, '', '')

    monkeypatch.setattr(release_qt6.subprocess, 'run', no_identity)
    with pytest.raises(ReleaseError) as failure:
        release_qt6.maintainer_identity(None)
    message = str(failure.value)
    for pointer in ('--maintainer "Name <email>"', 'CONVERTALL_MAINTAINER',
                    'git config --global user.email',
                    'bash release_qt6.sh --wait-ci --draft --maintainer'):
        assert pointer in message, pointer


def test_a_configured_git_identity_still_becomes_the_debian_maintainer(monkeypatch):
    monkeypatch.delenv('CONVERTALL_MAINTAINER', raising=False)

    def configured(arguments, **kwargs):
        value = 'Silent Person' if 'user.name' in arguments else 'silent@example.org'
        return subprocess.CompletedProcess(arguments, 0, value + '\n', '')

    monkeypatch.setattr(release_qt6.subprocess, 'run', configured)
    assert release_qt6.maintainer_identity(None) == 'Silent Person <silent@example.org>'


def test_a_local_rehearsal_never_asks_for_a_ci_run_or_a_release(monkeypatch):
    """Rehearsing the local steps must not require CI, and must never publish."""
    def forbidden(*arguments, **kwargs):
        raise AssertionError('a rehearsal must not select a CI run')

    monkeypatch.setattr(release_qt6, 'select_ci', forbidden)
    args = SimpleNamespace(local_only=True, draft=False, run_id=None, wait_ci=False)
    assert release_qt6.requested_ci_run(args, SHA) is None


@pytest.mark.parametrize('option', ['draft', 'run_id', 'wait_ci'])
def test_a_local_rehearsal_refuses_release_only_options(option):
    args = SimpleNamespace(local_only=True, draft=False, run_id=None, wait_ci=False)
    setattr(args, option, True if option == 'draft' else (7 if option == 'run_id' else True))
    with pytest.raises(ReleaseError, match='rehearsal'):
        release_qt6.requested_ci_run(args, SHA)


def test_a_real_release_still_goes_through_select_ci(monkeypatch):
    calls = []

    def fake_select(commit, run_id, wait):
        calls.append((commit, run_id, wait))
        return {'id': 5}

    monkeypatch.setattr(release_qt6, 'select_ci', fake_select)
    args = SimpleNamespace(local_only=False, draft=True, run_id=None, wait_ci=True)
    assert release_qt6.requested_ci_run(args, SHA) == {'id': 5}
    assert calls == [(SHA, None, True)]


def test_select_ci_skips_a_quiet_run_even_when_it_is_reported_successful(monkeypatch):
    marked, quiet = ci_run(42), ci_run(41)
    jobs = {42: ci_jobs_with(), 41: ci_jobs_with('skipped')}
    monkeypatch.setattr(release_qt6, 'github', fake_github([quiet, marked], jobs))
    assert release_qt6.select_ci(SHA, None, wait=False)['id'] == 42


def test_select_ci_refuses_a_history_without_a_green_marked_run(monkeypatch):
    monkeypatch.setattr(release_qt6, 'github',
                        fake_github([ci_run(7)], {7: ci_jobs_with('skipped')}))
    with pytest.raises(ReleaseError, match='twelve green jobs'):
        release_qt6.select_ci(SHA, None, wait=False)


def test_select_ci_waits_for_github_to_register_the_push(monkeypatch, fake_clock):
    """The API answers before the run exists; that must not abort the release."""
    calls = {'count': 0}

    def github(endpoint, *, missing_ok=False):
        if '/jobs?per_page=100' in endpoint:
            return {'jobs': ci_jobs_with()}
        calls['count'] += 1
        return {'workflow_runs': [] if calls['count'] == 1 else [ci_run(11)]}

    monkeypatch.setattr(release_qt6, 'github', github)
    assert release_qt6.select_ci(SHA, None, wait=True)['id'] == 11
    assert calls['count'] == 2  # it polled instead of giving up on the first empty answer


def test_a_missing_run_is_diagnosed_only_after_the_grace_period(monkeypatch, fake_clock):
    monkeypatch.setattr(release_qt6, 'github', fake_github([], {}))
    with pytest.raises(ReleaseError, match='No CI run for this SHA after'):
        release_qt6.select_ci(SHA, None, wait=False)
    assert fake_clock['elapsed'] >= release_qt6.CI_REGISTRATION_GRACE
    assert release_qt6.CI_REGISTRATION_WAIT > release_qt6.CI_REGISTRATION_GRACE > 0


def test_select_ci_waits_for_a_pending_run_instead_of_using_an_old_one(monkeypatch):
    runs = [ci_run(9, status='in_progress', conclusion=None)]
    watched = []

    def fake_command(arguments, **kwargs):
        watched.append(arguments)
        runs[0] = ci_run(9)  # the run finished while it was being watched
        return ''

    monkeypatch.setattr(release_qt6, 'command', fake_command)
    monkeypatch.setattr(release_qt6, 'github', fake_github(runs, {9: ci_jobs_with()}))
    selected = release_qt6.select_ci(SHA, None, wait=True)
    assert selected['id'] == 9
    assert watched and watched[0][:3] == ['gh', 'run', 'watch']


def test_missing_jobs_message_names_the_marker_when_nothing_ran():
    with pytest.raises(ReleaseError, match='contains \\[PROD\\]'):
        release_qt6.validate_ci_jobs([{'name': 'Tests ubuntu-24.04 / Python 3.11 / Qt6',
                                       'status': 'completed', 'conclusion': 'skipped'}])


def test_a_resumed_run_reuses_the_artifacts_of_the_exact_sha(tmp_path):
    builds, releases = tmp_path / 'build', tmp_path / 'dist'
    stamp = '20260101T000000Z-1'
    (builds / stamp).mkdir(parents=True)
    (builds / stamp / 'release.log').write_text('log', encoding='utf-8')
    (releases / f'{"b" * 40}-{stamp}').mkdir(parents=True)
    # Artifacts of another tree are never repackaged under this SHA.
    with pytest.raises(ReleaseError, match='drop --resume to rebuild'):
        release_qt6.previous_run(stamp, SHA, builds, releases)
    (releases / f'{SHA}-{stamp}').mkdir()
    work, assets = release_qt6.previous_run(stamp, SHA, builds, releases)
    assert work == builds / stamp and assets == releases / f'{SHA}-{stamp}'


def test_resume_latest_picks_the_most_recent_run_and_needs_one(tmp_path):
    builds, releases = tmp_path / 'build', tmp_path / 'dist'
    for stamp in ('20260101T000000Z-1', '20260102T000000Z-2'):
        (builds / stamp).mkdir(parents=True)
        (builds / stamp / 'release.log').write_text('log', encoding='utf-8')
        (releases / f'{SHA}-{stamp}').mkdir(parents=True)
    work, assets = release_qt6.previous_run('latest', SHA, builds, releases)
    assert work.name == '20260102T000000Z-2'
    assert assets.name == f'{SHA}-20260102T000000Z-2'
    with pytest.raises(ReleaseError, match='without --resume'):
        release_qt6.previous_run('latest', SHA, tmp_path / 'empty', tmp_path / 'empty')
    with pytest.raises(ReleaseError, match='Not an earlier release run'):
        release_qt6.previous_run('nope', SHA, builds, releases)


def test_fetch_tool_reuse_reverifies_the_pin_instead_of_downloading(tmp_path):
    name = 'runtime-x86_64'
    path = tmp_path / name
    header = bytearray(20)
    header[:6] = b'\x7fELF\x02\x01'
    struct.pack_into('<H', header, 18, 62)  # x86_64
    path.write_bytes(bytes(header))
    pin = {'repository': 'AppImage/type2-runtime', 'asset_id': 596078161, 'name': name,
           'sha256': packages.sha256(path)}
    assert release_qt6.fetch_tool(pin, tmp_path, reuse=True) == path  # no download happened
    path.write_bytes(b'\x7fELF\x02\x01' + b'x' * 14)
    with pytest.raises(ReleaseError, match='does not match the pin'):
        release_qt6.fetch_tool(pin, tmp_path, reuse=True)
    with pytest.raises(ReleaseError, match='already exists'):
        release_qt6.fetch_tool(pin, tmp_path)


def test_test_summary_reads_a_previous_or_a_fresh_results_directory(tmp_path):
    (tmp_path / 'validation.json').write_text(json.dumps({'commit': SHA, 'release_eligible': True}),
                                              encoding='utf-8')
    (tmp_path / 'junit.xml').write_text(
        '<testsuite tests="4" failures="1" errors="0" skipped="1"/>', encoding='utf-8')
    (tmp_path / 'coverage.json').write_text(json.dumps({'totals': {'percent_covered': 90.7}}),
                                            encoding='utf-8')
    report, counts = release_qt6.test_summary(tmp_path / 'validation.json', tmp_path / 'junit.xml',
                                              tmp_path / 'coverage.json')
    assert report['commit'] == SHA
    assert counts == {'tests': 4, 'failures': 1, 'errors': 0, 'skipped': 1, 'coverage_percent': 90.7}


def test_tool_locks_are_explicit_and_unverified_assets_are_not_executed(tmp_path, monkeypatch):
    lock = json.loads((ROOT / 'tools/appimage-lock.json').read_text(encoding='utf-8'))
    assert lock['architecture'] == 'x86_64'
    for name in ('appimagetool', 'runtime'):
        release_qt6.validate_tool_pin(lock[name])
    pin = copy.deepcopy(lock['runtime'])
    pin['sha256'] = '0' * 64
    class Result:
        returncode = 0
        stderr = b''
    def download(arguments, **kwargs):
        # Only fake a download; the test must never execute a real tool.
        assert arguments[:2] == ['gh', 'api']
        kwargs['stdout'].write(b'unverified downloaded bytes')
        return Result()
    monkeypatch.setattr(release_qt6.subprocess, 'run', download)
    with pytest.raises(ReleaseError, match='checksum mismatch'):
        release_qt6.fetch_tool(pin, tmp_path)


def test_appimage_uses_the_locked_builders_supported_compressor():
    lock = json.loads((ROOT / 'tools/appimage-lock.json').read_text(encoding='utf-8'))
    assert lock['compression'] == 'zstd'
    arguments = release_qt6.appimage_command(
        'AppRun', 'runtime-x86_64', 'ConvertAll.AppDir', 'ConvertAll.AppImage', lock['compression'])
    assert arguments == ['AppRun', '--runtime-file', 'runtime-x86_64', '--comp', 'zstd',
                         '--no-appstream', 'ConvertAll.AppDir', 'ConvertAll.AppImage']
    assert 'xz' not in arguments


@pytest.mark.parametrize('compression', ['xz', 'gzip', '', None])
def test_appimage_rejects_unsupported_compression_before_execution(compression):
    with pytest.raises(ReleaseError, match='only zstd'):
        release_qt6.appimage_command('AppRun', 'runtime', 'AppDir', 'out.AppImage', compression)


def test_local_scratch_directories_are_unique_writable_and_executable():
    notes = []
    directories = release_qt6.local_scratch_directories(notes)
    assert directories
    assert len(set(directories)) == len(directories)
    assert all(directory.is_dir() and os.access(directory, os.W_OK) for directory in directories)
    assert all(release_qt6.directory_can_execute(directory) for directory in directories)
    assert all('noexec' not in note for note in notes)  # rejected candidates are not returned


def test_local_scratch_directories_reject_noexec_mounts(monkeypatch, tmp_path):
    """Writable but not executable is not a usable scratch directory."""
    notes = []
    calls = []

    def fake_mkdtemp(**arguments):
        calls.append(arguments)
        (tmp_path / 'scratch').mkdir(exist_ok=True)
        return str(tmp_path / 'scratch')

    monkeypatch.setattr(release_qt6.tempfile, 'mkdtemp', fake_mkdtemp)
    monkeypatch.setattr(release_qt6, 'directory_can_execute', lambda directory: False)
    assert release_qt6.local_scratch_directories(notes) == []
    assert calls  # every candidate directory was actually tried
    assert notes and 'noexec' in notes[0]


def test_directory_can_execute_probes_and_cleans_up(tmp_path):
    assert release_qt6.directory_can_execute(tmp_path) is True
    assert not (tmp_path / 'exec-probe').exists()  # the probe never leaks


def elf64_with_a_payload(payload_offset, last_section=((0x100, 0x40)), section_table=(0x100, 64, 1)):
    """Minimal ELF with a section table, as an AppImage runtime is read by the tooling."""
    table_offset, entry_size, count = section_table
    image = bytearray(max(payload_offset, table_offset + entry_size * count) + 4)
    image[:6] = b'\x7fELF\x02\x01'
    struct.pack_into('<Q', image, 40, table_offset)
    struct.pack_into('<H', image, 58, entry_size)
    struct.pack_into('<H', image, 60, count)
    struct.pack_into('<Q', image, table_offset + 24, last_section[0])
    struct.pack_into('<Q', image, table_offset + 32, last_section[1])
    image[payload_offset:payload_offset + 4] = b'hsqs'
    return bytes(image)


def test_appimage_payload_offset_follows_the_runtime_rule(tmp_path):
    """The runtime uses the later of the section table end and the last section end."""
    table_end = tmp_path / 'table.AppImage'
    table_end.write_bytes(elf64_with_a_payload(0x140))
    assert release_qt6.appimage_payload_offset(table_end) == 0x140
    last_section_end = tmp_path / 'section.AppImage'
    last_section_end.write_bytes(elf64_with_a_payload(0x300, last_section=(0x100, 0x200)))
    assert release_qt6.appimage_payload_offset(last_section_end) == 0x300
    broken = tmp_path / 'broken.AppImage'
    broken.write_bytes(elf64_with_a_payload(0x140).replace(b'hsqs', b'zero'))
    with pytest.raises(ReleaseError, match='reads returned'):
        release_qt6.appimage_payload_offset(broken)


def test_local_scratch_copy_is_verified(monkeypatch, tmp_path):
    scratch = tmp_path / 'scratch'
    monkeypatch.setattr(release_qt6, 'local_scratch_directories', lambda notes=None: [scratch])
    source = tmp_path / 'source.bin'
    source.write_bytes(b'pinned bytes')
    copy = release_qt6.local_scratch_copy(source, packages.sha256(source))
    assert copy.read_bytes() == source.read_bytes()
    if os.name == 'posix':  # Windows has no execute bit to preserve
        assert copy.stat().st_mode & 0o111
    with pytest.raises(ReleaseError, match='No verified local copy'):
        release_qt6.local_scratch_copy(source, 'f' * 64)
    monkeypatch.setattr(release_qt6, 'local_scratch_directories', lambda notes=None: [])
    with pytest.raises(ReleaseError, match='no usable local directory'):
        release_qt6.local_scratch_copy(source)


def test_fs_safe_keeps_odd_paths_printable_and_serializable(tmp_path):
    """A work tree name that is not valid UTF-8 must not break logs or the manifest."""
    odd = tmp_path / 'T\udce9l\udce9chargements'
    safe = release_qt6.fs_safe(odd)
    assert safe.isascii()
    assert '\\udce9' not in safe  # escaped as bytes, never as lone surrogates
    assert json.dumps({'paths': {safe: False}})  # what release-provenance.json needs


def test_appimage_binfmt_handlers_only_reports_appimage_entries(tmp_path):
    (tmp_path / 'register').write_text('-1', encoding='utf-8')
    (tmp_path / 'status').write_text('enabled', encoding='utf-8')
    (tmp_path / 'python3.13').write_text('enabled\ninterpreter /usr/bin/python3.13\n', encoding='utf-8')
    (tmp_path / 'AppImageLauncher').write_text(
        'enabled\ninterpreter /usr/bin/AppImageLauncher\nflags: POCF\n', encoding='utf-8')
    handlers = release_qt6.appimage_binfmt_handlers(tmp_path)
    assert list(handlers) == ['AppImageLauncher']
    assert 'interpreter' in handlers['AppImageLauncher']
    assert release_qt6.appimage_binfmt_handlers(tmp_path / 'missing') == {}


def test_the_claimed_runtime_is_detected_by_its_magic_at_offset_eight(tmp_path):
    """AppImage/type2-runtime writes b'AI\x02' at offset 8 of the runtime itself.

    That is what makes the pinned runtime a claimed file like the image it builds:
    using it as an escape hatch waits for the handler instead of reading the payload.
    """
    for magic in (b'AI\x01', b'AI\x02'):
        claimed = tmp_path / f'runtime-{magic[2]}'
        claimed.write_bytes(b'\x7fELF\x02\x01' + b'\x00\x00' + magic + b'\x00' * 8)
        assert release_qt6.carries_appimage_magic(claimed), magic
    plain = tmp_path / 'plain'
    plain.write_bytes(b'\x7fELF\x02\x01' + b'\x00' * 16)
    assert not release_qt6.carries_appimage_magic(plain)
    assert not release_qt6.carries_appimage_magic(tmp_path / 'missing')
    short = tmp_path / 'short'
    short.write_bytes(b'\x7fELF')
    assert not release_qt6.carries_appimage_magic(short)


def test_appimage_environment_report_records_locale_and_ascii_flags(tmp_path):
    report = release_qt6.appimage_environment_report([tmp_path, Path('/tmp/T\udce9l')])
    assert set(report) == {'locale', 'binfmt_misc_appimage_handlers', 'paths'}
    assert set(report['locale']) == {'LANG', 'LC_ALL', 'LC_CTYPE', 'LC_MESSAGES', 'LANGUAGE',
                                     'TMPDIR', 'PYTHONUTF8', 'PYTHONIOENCODING'}
    assert report['paths'][release_qt6.fs_safe(tmp_path)] is True
    assert report['paths'][release_qt6.fs_safe(Path('/tmp/T\udce9l'))] is False
    assert json.dumps(report)  # the manifest embeds this report


def test_ascii_build_directory_skips_non_ascii_candidates(monkeypatch, tmp_path):
    non_ascii = tmp_path / 'T\udce9l\udce9chargements'
    ascii_dir = tmp_path / 'release-scratch'
    monkeypatch.setattr(release_qt6, 'local_scratch_directories', lambda notes=None: [non_ascii])
    assert release_qt6.ascii_build_directory() is None
    monkeypatch.setattr(release_qt6, 'local_scratch_directories',
                        lambda notes=None: [non_ascii, ascii_dir])
    assert release_qt6.ascii_build_directory() == ascii_dir


def test_ascii_tree_copies_a_non_ascii_tree(tmp_path):
    """appimagetool resolves its helpers relative to its own path, so the copy is complete."""
    source = tmp_path / 'T\udce9l' / 'squashfs-root'
    (source / 'usr/bin').mkdir(parents=True)
    (source / 'AppRun').write_text('#!/bin/sh\n', encoding='utf-8')
    (source / 'usr/bin/mksquashfs').write_text('binary\n', encoding='utf-8')
    (source / 'AppRun').chmod(0o755)
    destination = tmp_path / 'ascii-tool'
    copied = release_qt6.ascii_tree(source, destination)
    assert copied == destination
    assert (destination / 'AppRun').read_text(encoding='utf-8') == '#!/bin/sh\n'
    assert (destination / 'usr/bin/mksquashfs').is_file()
    if os.name == 'posix':
        assert (destination / 'AppRun').stat().st_mode & 0o111
    assert release_qt6.ascii_tree(Path('/tmp/plain'), destination) == Path('/tmp/plain')


def test_appimage_extraction_retries_from_a_local_disk(monkeypatch, tmp_path):
    """A shared or synchronised work tree must not dead-end the AppImage step."""
    image = tmp_path / 'appimagetool-x86_64.AppImage'
    image.write_bytes(b'\x7fELF\x02\x01' + b'x' * 64)
    local = tmp_path / 'local-temp'
    local.mkdir()
    monkeypatch.setattr(release_qt6, 'local_scratch_directories', lambda notes=None: [local])
    seen = []

    def fake_command(arguments, *, cwd=None, quiet=False, **kwargs):
        seen.append((Path(arguments[0]), Path(cwd)))
        if len(seen) == 1:
            raise ReleaseError('Command failed (1): the mount cannot read its own image')
        (Path(cwd) / 'squashfs-root').mkdir(parents=True, exist_ok=True)
        (Path(cwd) / 'squashfs-root/AppRun').write_text('#!/bin/sh\n', encoding='utf-8')
        return ''

    monkeypatch.setattr(release_qt6, 'command', fake_command)
    root = release_qt6.extract_appimage(image, tmp_path / 'extracted', required='AppRun',
                                        expected_sha256=packages.sha256(image))
    assert len(seen) == 2
    assert Path(seen[1][1]) != Path(seen[0][1])  # retried somewhere else
    assert root == Path(seen[1][1]) / 'squashfs-root'
    assert (root / 'AppRun').is_file()
    assert Path(seen[1][0]).read_bytes() == image.read_bytes()  # same verified bytes


def test_appimage_extraction_can_use_the_pinned_runtime(monkeypatch, tmp_path):
    """TARGET_APPIMAGE makes the pinned runtime read the image by path, not /proc/self/exe."""
    image = tmp_path / 'tool.AppImage'
    image.write_bytes(b'\x7fELF\x02\x01' + b'x' * 64)
    runtime = tmp_path / 'runtime-x86_64'
    runtime.write_bytes(b'\x7fELF\x02\x01' + b'r' * 64)
    local = tmp_path / 'local-temp'
    local.mkdir()
    monkeypatch.setattr(release_qt6, 'local_scratch_directories', lambda notes=None: [local])
    environments = []

    def fake_command(arguments, *, cwd=None, quiet=False, env=None, **kwargs):
        environments.append((Path(arguments[0]), env))
        if Path(arguments[0]) != runtime:
            raise ReleaseError('Command failed (1): cannot open squashfs image')
        assert env['TARGET_APPIMAGE'] == str(image)
        (Path(cwd) / 'squashfs-root').mkdir(parents=True, exist_ok=True)
        (Path(cwd) / 'squashfs-root/AppRun').write_text('#!/bin/sh\n', encoding='utf-8')
        return ''

    monkeypatch.setattr(release_qt6, 'command', fake_command)
    root = release_qt6.extract_appimage(image, tmp_path / 'extracted', required='AppRun',
                                        runtime=runtime)
    # in place, then a local copy, then the pinned runtime with TARGET_APPIMAGE
    assert [program for program, _ in environments] == [image, local / image.name, runtime]
    assert environments[-1][1]['TARGET_APPIMAGE'] == str(image)
    assert (root / 'AppRun').is_file()


def test_payload_extraction_strips_the_elf_prefix(monkeypatch, tmp_path):
    """The last resort reads the squashfs itself, from the verified local copy."""
    image = tmp_path / 'tool.AppImage'
    image.write_bytes(b'P' * 0x140 + b'hsqs' + b'payload')
    local = tmp_path / 'local-temp'
    local.mkdir()
    monkeypatch.setattr(release_qt6, 'local_scratch_directories', lambda notes=None: [local])
    runs = []

    def fake_command(arguments, *, cwd=None, quiet=False, **kwargs):
        runs.append(arguments)
        root = Path(arguments[2])
        root.mkdir(parents=True, exist_ok=True)
        (root / 'AppRun').write_text('#!/bin/sh\n', encoding='utf-8')
        return ''

    monkeypatch.setattr(release_qt6, 'command', fake_command)
    root = release_qt6.extract_squashfs_payload(image, tmp_path / 'out', required='AppRun',
                                                offset=0x140,
                                                expected_sha256=packages.sha256(image))
    assert runs[0][0] == 'unsquashfs'
    assert Path(runs[0][3]).read_bytes() == b'hsqs' + b'payload'  # payload only, no ELF prefix
    assert root == tmp_path / 'out/squashfs-root'
    assert (root / 'AppRun').is_file()


def test_a_broken_local_copy_does_not_end_the_fallback(monkeypatch, tmp_path):
    """A scratch directory that cannot hold a verified copy must not stop the layers."""
    image = tmp_path / 'tool.AppImage'
    image.write_bytes(b'\x7fELF\x02\x01' + b'x' * 64)
    local = tmp_path / 'local-temp'
    local.mkdir()
    monkeypatch.setattr(release_qt6, 'local_scratch_directories', lambda notes=None: [local])

    def broken_copy(path, expected_sha256=None):
        raise ReleaseError('scratch directory cannot hold a verified copy')

    def broken_command(*arguments, **kwargs):
        raise ReleaseError('Command failed (1): cannot open squashfs image')

    def broken_offset(path):
        raise ReleaseError('No squashfs payload')

    monkeypatch.setattr(release_qt6, 'local_scratch_copy', broken_copy)
    monkeypatch.setattr(release_qt6, 'command', broken_command)
    monkeypatch.setattr(release_qt6, 'appimage_payload_offset', broken_offset)
    with pytest.raises(ReleaseError) as failure:
        release_qt6.extract_appimage(image, tmp_path / 'out', required='AppRun')
    message = str(failure.value)
    assert 'scratch directory cannot hold a verified copy' in message
    if shutil.which('unsquashfs'):  # squashfs-tools is required on release hosts only
        assert 'No squashfs payload' in message


def test_a_command_timeout_is_a_release_error_not_an_abort(monkeypatch):
    """A hanging AppImage check must fall through to the next layer, not kill the run."""
    def timing_out(*arguments, **kwargs):
        raise subprocess.TimeoutExpired(cmd='hanging', timeout=kwargs.get('timeout'))
    monkeypatch.setattr(release_qt6.subprocess, 'run', timing_out)
    # The timeout is passed explicitly: asserting the default (1800s) would pin a
    # number no caller uses, which is how this test first failed on CI.
    with pytest.raises(ReleaseError, match='timed out after 180s: /some/hanging/AppRun'):
        release_qt6.command(['/some/hanging/AppRun', '--runtime-info'], timeout=180)


def test_a_timed_out_command_keeps_what_it_printed(monkeypatch, tmp_path):
    """The 180s wait on the pinned runtime left nothing to diagnose with."""
    log = tmp_path / 'release.log'
    monkeypatch.setattr(release_qt6, 'LOG', log)

    def timing_out(arguments, **kwargs):
        raise subprocess.TimeoutExpired(cmd=arguments, timeout=kwargs['timeout'],
                                        output='extracting\n', stderr='still running\n')
    monkeypatch.setattr(release_qt6.subprocess, 'run', timing_out)
    with pytest.raises(ReleaseError, match='timed out after 180s'):
        release_qt6.command(['/some/hanging/runtime-x86_64', '--appimage-extract-and-run'],
                            timeout=180, quiet=True)
    kept = log.read_text(encoding='utf-8')
    assert 'TIMED OUT after 180s' in kept
    assert 'extracting' in kept and 'still running' in kept


def test_an_intercepted_appimage_skips_the_layers_that_run_it():
    """binfmt_misc handlers claimed the pinned tool and hung on the built image."""
    handlers = {'AppImageLauncher': 'enabled; interpreter /usr/bin/AppImageLauncher'}
    assert release_qt6.runtime_launch_plan(handlers) == ['pinned runtime']
    assert release_qt6.runtime_launch_plan({}) == ['direct', 'local copy', 'pinned runtime']
    # With a runtime the handler claims as well, no layer may execute anything:
    # the 0.9.3 run on a host with AppImageLauncher waited 180s on that runtime
    # while the payload that never gets executed was the only usable proof left.
    assert release_qt6.runtime_launch_plan(handlers, True) == []
    assert release_qt6.runtime_launch_plan({}, True) == ['direct', 'local copy', 'pinned runtime']


def test_intercepted_extraction_never_executes_the_claimed_runtime(monkeypatch, tmp_path, capsys):
    image = tmp_path / 'tool.AppImage'
    image.write_bytes(b'\x7fELF\x02\x01' + b'x' * 64)
    runtime = tmp_path / 'runtime-x86_64'
    runtime.write_bytes(b'\x7fELF\x02\x01' + b'r' * 64)
    local = tmp_path / 'local-temp'
    local.mkdir()
    monkeypatch.setattr(release_qt6, 'local_scratch_directories',
                        lambda notes=None: [local])

    def fake_command(arguments, *, cwd=None, quiet=False, **kwargs):
        assert Path(arguments[0]) != image, 'the intercepted image must not be executed'
        (Path(cwd) / 'squashfs-root').mkdir(parents=True, exist_ok=True)
        (Path(cwd) / 'squashfs-root/AppRun').write_text('#!/bin/sh\n', encoding='utf-8')
        return ''

    monkeypatch.setattr(release_qt6, 'command', fake_command)
    root = release_qt6.extract_appimage(image, tmp_path / 'out', required='AppRun',
                                        runtime=runtime, intercepted=True)
    assert (root / 'AppRun').is_file()
    # A warning that starts with an empty reason explains nothing (seen in the
    # 0.9.3 local log as "WARNING: ; retrying through the pinned runtime...").
    warnings = [line for line in capsys.readouterr().out.splitlines() if line.startswith('WARNING')]
    assert warnings and all('WARNING: ;' not in line for line in warnings)


def test_appimage_extraction_failure_stays_explicit(monkeypatch, tmp_path):
    image = tmp_path / 'tool.AppImage'
    image.write_bytes(b'\x7fELF\x02\x01' + b'x' * 16)
    local = tmp_path / 'local-temp'
    local.mkdir()
    monkeypatch.setattr(release_qt6, 'local_scratch_directories', lambda notes=None: [local])

    def failing_command(*arguments, **kwargs):
        raise ReleaseError('Command failed (1): no squashfs')
    monkeypatch.setattr(release_qt6, 'command', failing_command)
    def failing_offset(path):
        raise ReleaseError('No squashfs payload at offset 64')
    monkeypatch.setattr(release_qt6, 'appimage_payload_offset', failing_offset)
    with pytest.raises(ReleaseError) as failure:
        release_qt6.extract_appimage(image, tmp_path / 'out', required='AppRun',
                                     expected_sha256=packages.sha256(image))
    message = str(failure.value)
    assert 'move the clone to a local disk' in message
    if shutil.which('unsquashfs'):
        assert 'No squashfs payload at offset 64' in message
    else:  # squashfs-tools is a documented requirement, not a dependency here
        assert 'unsquashfs is not installed' in message
    assert packages.sha256(image) in message  # the bytes on disk are reported, not hidden


def test_release_elf_architecture_is_checked_before_execution(tmp_path):
    path = tmp_path / 'elf'
    header = bytearray(20)
    header[:6] = b'\x7fELF\x02\x01'
    struct.pack_into('<H', header, 18, 62)
    path.write_bytes(header)
    release_qt6.require_amd64_elf(path)
    struct.pack_into('<H', header, 18, 183)  # AArch64, not a valid x86_64 artifact
    path.write_bytes(header)
    with pytest.raises(ReleaseError, match='x86_64 ELF'):
        release_qt6.require_amd64_elf(path)


def test_new_script_is_hashed_archived_and_does_not_publish_latest():
    import validate_release
    assert 'release_qt6.sh' in validate_release.input_hashes()
    text = (ROOT / 'tools/release_qt6.py').read_text(encoding='utf-8')
    assert "'--verify-tag', '--draft'" in text
    assert '--latest' not in text and '--clobber' not in text
    assert 'sudo' not in (ROOT / 'release_qt6.sh').read_text()
