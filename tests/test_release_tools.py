"""Release drivers fail closed. Native bundle execution is a separate CI gate."""
from pathlib import Path
import json
import subprocess
import sys

import pytest

from helpers import ROOT
import check_bundle
import release_source
import validate_release


def test_release_environment_versions_are_explicit():
    packages = validate_release.expected_packages()
    assert packages['PyQt6'] == '6.11.0'
    assert packages['pytest'] == '9.1.1'
    assert 'PyQt5' not in packages
    hashes = validate_release.input_hashes()
    assert 'source/convertall.py' in hashes
    assert 'data/units.dat' in hashes
    assert all(len(value) == 64 for value in hashes.values())
    assert not any('__pycache__' in name for name in hashes)
    assert all('\\' not in name for name in hashes)  # canonical JSON paths on every OS


@pytest.mark.parametrize('source', ["__version__ = '0.9.0-beta'", 'x = 1',
                                    '__version__ = 1'])
def test_archive_version_must_be_a_stable_semver(source):
    with pytest.raises(ValueError, match='stable'):
        release_source.version_from_source(source)


def test_bundle_validator_rejects_missing_executable(tmp_path):
    with pytest.raises(RuntimeError, match='Missing bundle resource'):
        check_bundle.check_bundle(tmp_path)


@pytest.mark.parametrize('reason', ['_internal', 'PyQt5'])
def test_bundle_validator_rejects_wrong_layout_or_binding(tmp_path, monkeypatch, reason):
    monkeypatch.setattr(check_bundle.sys, 'platform', 'linux')
    for name in ('convertall', 'data/units.dat', 'doc/LICENSE', 'doc/LICENSE-GPL-3.0',
                 'icons/convertall_med.png', 'translations/convertall_fr.qm'):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    (tmp_path / reason).mkdir()
    with pytest.raises(RuntimeError, match='flat|binding'):
        check_bundle.check_bundle(tmp_path)


def test_workflow_pins_actions_and_has_test_then_native_bundle_gate():
    workflow = (ROOT / '.github/workflows/qt6-release.yml').read_text()
    for action in ('checkout', 'setup-python', 'upload-artifact'):
        assert f'actions/{action}@' in workflow
    import re
    for ref in re.findall(r'uses: actions/[^@]+@([^\s]+)', workflow):
        assert re.fullmatch('[0-9a-f]{40}', ref)
    assert 'needs: tests' in workflow
    assert 'python tools/validate_release.py' in workflow
    assert 'python tools/check_bundle.py dist/convertall' in workflow
    assert 'windows-2022' in workflow and 'ubuntu-24.04' in workflow
    assert "'3.11'" in workflow and "'3.14'" in workflow
    assert 'contents: read' in workflow
    assert 'gh release create' not in workflow  # never publish automatically


def test_required_release_configuration_is_not_gitignored(tmp_path):
    # Also runnable from an extracted source archive with no .git directory.
    (tmp_path / '.gitignore').write_bytes((ROOT / '.gitignore').read_bytes())
    subprocess.run(['git', 'init', '-b', 'arena/0adacf84-convertall-py'],
                   cwd=tmp_path, check=True, capture_output=True, timeout=10)
    paths = ['.coveragerc', 'pytest.ini', 'requirements-test.txt',
             '.github/workflows/qt6-release.yml']
    result = subprocess.run(['git', 'check-ignore', '--', *paths], cwd=tmp_path,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 1 and result.stdout == '', result.stdout + result.stderr


def test_qt5_reference_and_runner_cannot_use_new_qt6_sources():
    reference = 'b10b8e7837e30a2ec9a957a9a2519e4ac0334db3'
    archived = (ROOT / '.github/workflows/qt5-release.yml').read_text(encoding='utf-8')
    assert archived.count('ref: ' + reference) == 2
    assert '--commit ' + reference in archived
    assert 'workflow_dispatch:' in archived
    assert '\n  push:' not in archived and '\n  pull_request:' not in archived
    runner = (ROOT / 'test_all_qt5.sh').read_text(encoding='utf-8')
    assert 'requirements-qt6.txt' in runner
    assert reference in runner
    assert 'bash test_all_qt6.sh' in runner
    workflow = (ROOT / '.github/workflows/qt6-release.yml').read_text(encoding='utf-8')
    assert '--require-clean' in workflow
    for version in ('3.11', '3.12', '3.13', '3.14'):
        assert "'" + version + "'" in workflow
    assert 'QT_API: pyqt6' in workflow


@pytest.mark.parametrize('other', ['PyQt5', 'PySide2', 'PySide6'])
def test_gate_rejects_mixed_bindings_with_a_saved_report(tmp_path, monkeypatch, other):
    monkeypatch.setattr(validate_release, 'ROOT', tmp_path)
    monkeypatch.setattr(sys, 'argv', ['validate_release.py'])
    def version(name):
        if name in validate_release.expected_packages():
            return validate_release.expected_packages()[name]
        if name == other:
            return 'unexpected-binding'
        raise validate_release.metadata.PackageNotFoundError(name)
    monkeypatch.setattr(validate_release.metadata, 'version', version)
    assert validate_release.main() == 2
    report = json.loads((tmp_path / 'build/test-results/validation.json').read_text(encoding='utf-8'))
    assert other in report['prerequisite_error']
    assert not report['release_eligible']
    assert report['pytest_exit_code'] is None


def test_gate_refuses_dirty_release_checkout(tmp_path, monkeypatch):
    monkeypatch.setattr(validate_release, 'ROOT', tmp_path)
    monkeypatch.setattr(sys, 'argv', ['validate_release.py', '--require-clean'])
    monkeypatch.delenv('GITHUB_SHA', raising=False)
    monkeypatch.setattr(validate_release, 'git_state', lambda: {
        'commit': 'a' * 40, 'branch': 'arena/0adacf84-convertall-py', 'working_tree_dirty': True})
    assert validate_release.main() == 2
    report = json.loads((tmp_path / 'build/test-results/validation.json').read_text(encoding='utf-8'))
    assert 'clean committed' in report['prerequisite_error']
    assert report['working_tree_dirty'] is True
    assert not report['release_eligible']


def test_gate_refuses_ci_sha_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr(validate_release, 'ROOT', tmp_path)
    monkeypatch.setattr(sys, 'argv', ['validate_release.py', '--require-clean'])
    monkeypatch.setenv('GITHUB_SHA', 'b' * 40)
    monkeypatch.setattr(validate_release, 'git_state', lambda: {
        'commit': 'a' * 40, 'branch': 'arena/0adacf84-convertall-py', 'working_tree_dirty': False})
    assert validate_release.main() == 2
    report = json.loads((tmp_path / 'build/test-results/validation.json').read_text(encoding='utf-8'))
    assert 'GITHUB_SHA' in report['prerequisite_error']
    assert not report['release_eligible']


@pytest.fixture
def frozen_runtime_info():
    return {'application': 'ConvertAll', 'version': '0.9.3', 'binding': 'PyQt6',
            'pyqt_binding': '6.11.0', 'qt_runtime': '6.11.2',
            'sip_package': '13.13.0', 'sip_generator': '6.17.0'}


def test_bundle_checks_sip_distribution_separately_from_generator(frozen_runtime_info):
    check_bundle.validate_runtime_info(frozen_runtime_info)


@pytest.mark.parametrize('package', ['6.17.0', '13.12.0', None])
def test_bundle_rejects_wrong_sip_distribution(frozen_runtime_info, package):
    frozen_runtime_info['sip_package'] = package
    with pytest.raises(RuntimeError, match='Wrong frozen Qt6 runtime'):
        check_bundle.validate_runtime_info(frozen_runtime_info)


@pytest.mark.parametrize('generator', ['', None, []])
def test_bundle_requires_an_explicit_sip_generator(frozen_runtime_info, generator):
    frozen_runtime_info['sip_generator'] = generator
    with pytest.raises(RuntimeError, match='SIP generator'):
        check_bundle.validate_runtime_info(frozen_runtime_info)


def test_bundle_rejects_old_ambiguous_sip_report(frozen_runtime_info):
    frozen_runtime_info['sip'] = frozen_runtime_info.pop('sip_generator')
    frozen_runtime_info.pop('sip_package')
    with pytest.raises(RuntimeError, match='Wrong frozen Qt6 runtime'):
        check_bundle.validate_runtime_info(frozen_runtime_info)
