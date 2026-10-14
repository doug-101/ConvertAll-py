"""Thin .deb invariants; actual apt runtimes are exercised separately in CI."""
import copy
from pathlib import Path

import pytest

from helpers import ROOT
import linux_release as packages
from linux_release import ReleaseError

pytestmark = pytest.mark.packaging


@pytest.fixture
def native_runtime():
    return {'application': 'ConvertAll', 'version': '0.9.3', 'binding': 'PyQt6',
            'python_executable': '/usr/bin/python3', 'python_version': '3.11.2',
            'pyqt_binding': '6.4.2', 'qt_runtime': '6.4.2', 'sip_package': '13.4.1',
            'sip_generator': '6.7.7', 'frozen': False,
            'pyqt_location': '/usr/lib/python3/dist-packages/PyQt6/QtCore.cpython-311-x86_64-linux-gnu.so',
            'qt_translations_path': '/usr/share/qt6/translations'}


def test_system_qt_profile_is_distinct_from_frozen_wheel_pins(native_runtime):
    packages.validate_debian_runtime(native_runtime, '0.9.3')
    newer = copy.deepcopy(native_runtime)
    newer.update(python_version='3.13.5', pyqt_binding='6.8.4', qt_runtime='6.8.2', sip_package='13.10.2')
    packages.validate_debian_runtime(newer, '0.9.3')


@pytest.mark.parametrize('field,value', [('python_version', '3.10.9'), ('pyqt_binding', '6.3.0'),
                                         ('qt_runtime', '6.3.0'), ('sip_package', '13.3.0'),
                                         ('frozen', True), ('version', '0.9.0'),
                                         ('sip_generator', '')])
def test_native_profile_rejects_unsupported_or_wrong_app_runtime(native_runtime, field, value):
    native_runtime[field] = value
    with pytest.raises(ReleaseError, match='Unsupported Debian'):
        packages.validate_debian_runtime(native_runtime, '0.9.3')


@pytest.mark.parametrize('field,value', [
    ('python_executable', '/home/test/.venv/bin/python'),
    ('pyqt_location', '/home/test/.venv/lib/python3.11/site-packages/PyQt6/QtCore.so'),
    ('pyqt_location', '/usr/local/lib/python3.11/dist-packages/PyQt6/QtCore.so'),
])
def test_native_profile_cannot_be_validated_by_a_wheel_venv(native_runtime, field, value):
    native_runtime[field] = value
    with pytest.raises(ReleaseError, match='Debian package'):
        packages.validate_debian_runtime(native_runtime, '0.9.3')


@pytest.mark.parametrize('name,content', [('runtime.so', b'library'), ('python', b'\x7fELFbinary'),
                                        ('setup.py', b'build script'), ('module.pyc', b'bytecode'),
                                        ('PyQt6', None)])
def test_thin_package_rejects_any_bundled_runtime_or_build_file(tmp_path, name, content):
    stage = packages.stage_deb(tmp_path / 'deb', ROOT, '0.9.3', 'Test <test@example.invalid>')
    path = stage / 'usr/share/convertall' / name
    if content is None:
        path.mkdir()
    else:
        path.write_bytes(content)
    with pytest.raises(ReleaseError, match='Bundled runtime|ELF binary'):
        packages.verify_thin_deb_payload(stage)


def test_generated_debian_entry_compiles_and_preserves_relative_resource_layout():
    entry = packages.deb_entry()
    compile(entry, '_debian_entry.py', 'exec')
    assert 'convertall.dataFilePath = str(base / "data")' in entry
    assert 'convertall.helpFilePath = str(base.parent / "doc" / "convertall")' in entry
    assert 'sys.exit(convertall.main())' in entry
    assert 'pip install' not in entry and 'apt install' not in packages.deb_launcher()


def test_debian_packaging_does_not_collect_wheel_notices_or_frozen_payload(tmp_path):
    stage = packages.stage_deb(tmp_path / 'deb', ROOT, '0.9.3', 'Test <test@example.invalid>')
    assert not list(stage.rglob('third-party'))
    assert not list(stage.rglob('PyQt6'))
    assert not list(stage.rglob('*.dist-info'))
    assert not list(stage.rglob('*.exe'))
    assert len(list((stage / 'usr/share/doc/convertall').glob('README*.html'))) >= 5
    assert len(list((stage / 'usr/share/convertall/translations').glob('*.qm'))) == 6
    assert len(list((stage / 'usr/share/convertall/data').glob('*.dat'))) == 7
    assert not list(stage.rglob('*.ts'))  # TS/build inputs remain available in the source archive.


def test_distribution_widget_translations_are_only_tolerated_when_truly_missing(tmp_path):
    qt, app = tmp_path / 'qt', tmp_path / 'app'
    qt.mkdir()
    app.mkdir()
    (app / 'convertall_fr.qm').write_bytes(b'qm')
    (app / 'convertall_sv.qm').write_bytes(b'qm')
    # Absent widget catalogue is reported, never hidden.
    assert packages.expected_missing_translations('sv_SE.UTF-8', qt, app) == ['qt_sv_SE']
    (qt / 'qtbase_fr.qm').write_bytes(b'qm')
    assert packages.expected_missing_translations('fr_FR.UTF-8', qt, app) == []
    # A missing application catalogue is surfaced so callers can reject it.
    assert packages.expected_missing_translations('de_DE.UTF-8', qt, app) == [
        'convertall_de_DE', 'qt_de_DE']
    (app / 'convertall_de.qm').write_bytes(b'qm')
    assert packages.expected_missing_translations('de_DE.UTF-8', qt, app) == ['qt_de_DE']


def test_warning_parser_reports_each_unloadable_catalogue_once():
    output = ('Warning: translation file "qt_sv_SE" could not be loaded\n'
              'Warning: translation file "qt_sv_SE" could not be loaded\n'
              'All units pass tests\n')
    assert packages.translation_warning_names(output) == ['qt_sv_SE']
    assert packages.translation_warning_names('All units pass tests\n') == []


def test_thin_package_must_ship_every_application_translation(tmp_path):
    stage = packages.stage_deb(tmp_path / 'deb', ROOT, '0.9.3', 'Test <test@example.invalid>')
    (stage / 'usr/share/convertall/translations/convertall_sv.qm').unlink()
    with pytest.raises(ReleaseError, match='six application translations'):
        packages.verify_thin_deb_payload(stage)


def test_native_deb_checker_rejects_a_missing_application_catalogue():
    text = (ROOT / 'tools/build_deb.py').read_text(encoding='utf-8')
    assert "any(name.startswith('convertall_') for name in names)" in text
    assert 'expected_missing_translations' in text
    # The previous substring check would have failed on an absent widget language.
    assert "'Warning' in text" not in text


def test_native_deb_failures_are_annotated_for_logless_debugging(tmp_path, monkeypatch, capsys):
    """CI logs and artifacts can be unreachable, so failures must reach the API."""
    import build_deb
    monkeypatch.setenv('GITHUB_ACTIONS', 'true')
    monkeypatch.setattr(build_deb, 'STEP', {'name': 'execute extracted package'})
    build_deb.TRACE.append('staged 40 files for 0.9.3')
    build_deb.report_failure(tmp_path,
                             ReleaseError('translations mismatched: warnings=[], expected=[qt_sv_SE]'),
                             'Traceback (most recent call last):\n')
    captured = capsys.readouterr()
    report = (tmp_path / 'native-deb-failure.txt').read_text(encoding='utf-8')
    assert 'step=execute extracted package' in report
    assert 'expected=[qt_sv_SE]' in report
    assert 'staged 40 files for 0.9.3' in report
    assert '::error title=Native Debian package failed (execute extracted package)' in captured.out


def test_native_deb_checker_probes_the_system_runtime_before_packaging_and_traces_milestones():
    text = (ROOT / 'tools/build_deb.py').read_text(encoding='utf-8')
    assert '::notice title=ConvertAll native .deb::' in text
    assert '::error title=Native Debian package failed' in text
    assert 'native-deb-failure.txt' in text
    assert 'except Exception as error' in text  # unexpected failures stay reportable
    # The system runtime must be validated before anything is staged or built.
    body = text.split('def build(', 1)[1]
    assert body.index('probe_system(version)') < body.index('stage_deb(')
    assert body.index('stage_deb(') < body.index('check_extracted(')


def test_native_deb_git_calls_trust_the_ci_container_checkout():
    """Container jobs mount a foreign-owned workspace; plain git refuses it."""
    text = (ROOT / 'tools/build_deb.py').read_text(encoding='utf-8')
    assert "run(['git', '-c', f'safe.directory={ROOT}'" in text
    assert "git('rev-parse', 'HEAD')" in text
    assert "git('status', '--porcelain')" in text
    assert "git('show', '-s', '--format=%ct', commit)" in text
    # Every git call goes through that helper, so none can bypass the trust flag.
    assert text.count("run(['git',") == 1


def test_ci_exercises_native_debian_versions_without_installing_qt_wheels():
    workflow = (ROOT / '.github/workflows/qt6-release.yml').read_text(encoding='utf-8')
    native = workflow.split('  native-deb:', 1)[1].split('  bundle:', 1)[0]
    assert 'suite: [bookworm, trixie]' in native
    assert '--system-site-packages' in native
    assert 'requirements-test-debian.txt' in native
    assert '/usr/bin/python3 -E -s tools/build_deb.py' in native
    # The runtime probe is a separate step, so CI status alone localises failures.
    assert '/usr/bin/python3 -E -s tools/build_deb.py --probe-system' in native
    assert 'requirements-qt6.txt' not in native
    assert '--cov=source' in native and '--cov-fail-under=0' not in native
    requirements = (ROOT / 'requirements-test-debian.txt').read_text(encoding='utf-8')
    assert 'PyQt6==' not in requirements and '-r requirements-qt6.txt' not in requirements
