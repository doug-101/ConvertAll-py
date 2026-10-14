"""Unix installer: isolated prefix, DESTDIR, quoting and uninstall."""
import hashlib
import os
from pathlib import Path
import shlex
import subprocess
import sys

import pytest

from helpers import ROOT, copy_project, run_cli
import install

pytestmark = pytest.mark.integration


def run_script(script, *args, cwd=None):
    return subprocess.run([sys.executable, str(script), *map(str, args)],
                          cwd=cwd or ROOT, capture_output=True, text=True,
                          encoding='utf-8', timeout=45)


@pytest.mark.parametrize('version,minimum,expected', [
    ('3.10', (3, 10, 0), True), ('3.9.9', (3, 10), False),
    ('5.15.19', (5, 15, 2), True), ('Qt 5.15.2', (5, 15), True),
    ('not a version', (5, 15), False), ('5.4', (5, 15), False),
    ('3.11', (3, 11), True), ('3.10.9', (3, 11), False),
    ('6.11.2', (6, 11, 2), True), ('6.11.0', (6, 11, 2), False),
    ('PyQt 6.11.0', (6, 11, 0), True), ('6.10.3', (6, 11, 0), False),
])
def test_dependency_version_comparison(version, minimum, expected):
    assert install.cmpVersions(version, minimum) is expected


@pytest.mark.parametrize('script', ['install.py', 'uninstall.py'])
def test_installer_help_and_unknown_option(script):
    result = run_script(ROOT / script, '-h')
    assert result.returncode == 0 and 'Usage' in result.stdout
    assert run_script(ROOT / script, '--bad-option').returncode == 2


@pytest.mark.parametrize('path_name', ["a path/with 'quotes'", 'plain', 'mètre et 日本語'])
def test_wrapper_quotes_python_and_script_paths(tmp_path, monkeypatch, path_name):
    monkeypatch.chdir(tmp_path)
    executable = f'/{path_name}/python'
    script_dir = f'/{path_name}/convertall'
    monkeypatch.setattr(sys, 'executable', executable)
    install.createWrapper(script_dir, 'convertall')
    wrapper = tmp_path / 'convertall'
    text = wrapper.read_text(encoding='utf-8')
    words = shlex.split(text.split('exec ', 1)[1])
    assert words == [executable, script_dir + '/convertall.py', '$@']
    assert text.startswith('#!/bin/sh')
    assert b'\r\n' not in wrapper.read_bytes()  # POSIX script even on a Windows host


@pytest.mark.skipif(sys.platform == 'win32', reason='Unix shell installer; Windows is covered by the native bundle CI job')
@pytest.mark.parametrize('translated', [True, False])
def test_isolated_install_runs_cli_and_uninstall_leaves_no_app(translated, tmp_path):
    project = copy_project(tmp_path / 'source extraction with spaces')
    # Both shell quoting and Python resource path literals must survive this.
    prefix = tmp_path / "prefix with spaces and O'Brien"
    before = hashlib.sha256((ROOT / 'source/convertall.py').read_bytes()).hexdigest()
    args = ['-p', str(prefix)] + ([] if translated else ['-s'])
    result = run_script(project / 'install.py', *args, cwd=project)
    assert result.returncode == 0, result.stdout + result.stderr
    installed = prefix / 'share/convertall'
    assert (installed / 'convertall.py').is_file()
    assert (installed / 'data/units.dat').is_file()
    assert (prefix / 'share/doc/convertall/README.html').is_file()
    assert (prefix / 'share/icons/convertall/convertall_med.png').is_file()
    assert (installed / 'data/units_fr.dat').exists() is translated
    assert (installed / 'translations').exists() is translated
    assert (prefix / 'share/doc/convertall/LICENSE-GPL-3.0').is_file()
    if translated:
        assert (installed / 'translations/convertall_fr.qm').is_file()
        assert not list((installed / 'translations').glob('qt_*.qm'))
    wrapper = prefix / 'bin/convertall'
    cli = subprocess.run([str(wrapper), '-q', '1', 'in', 'cm'],
                         capture_output=True, text=True, timeout=20)
    assert cli.returncode == 0 and cli.stdout.strip() == '1 in = 2.54 cm', cli.stderr
    test = subprocess.run([str(wrapper), '--test-all'], capture_output=True,
                          text=True, timeout=20)
    assert test.returncode == 0
    assert test.stdout.count('All units pass tests') == (7 if translated else 1)
    assert hashlib.sha256((ROOT / 'source/convertall.py').read_bytes()).hexdigest() == before
    removed = run_script(project / 'uninstall.py', '-p', prefix, cwd=project)
    assert removed.returncode == 0, removed.stderr
    for path in (installed, wrapper, prefix / 'share/doc/convertall',
                 prefix / 'share/icons/convertall',
                 prefix / 'share/applications/convertall.desktop',
                 prefix / 'share/icons/hicolor/scalable/apps/convertall-icon.svg'):
        assert not path.exists(), path
    assert run_script(project / 'uninstall.py', '-p', prefix, cwd=project).returncode == 0


@pytest.mark.skipif(sys.platform == 'win32', reason='Unix packager DESTDIR layout')
def test_destdir_install_preserves_final_prefix_in_wrapper(tmp_path):
    project = copy_project(tmp_path / 'extraction')
    staged = tmp_path / 'stage'
    result = run_script(project / 'install.py', '-p', '/opt/convertall-test',
                        '-b', staged, cwd=project)
    assert result.returncode == 0, result.stdout + result.stderr
    wrapper = staged / 'opt/convertall-test/bin/convertall'
    assert wrapper.is_file()
    assert '/opt/convertall-test/share/convertall/convertall.py' in wrapper.read_text()
    assert str(staged) not in wrapper.read_text()
    assert (staged / 'opt/convertall-test/share/convertall/data/units.dat').exists()
