"""Version, resources and reproducible archives of the exact tested commit."""
import ast
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tarfile

import pytest

from helpers import ROOT, copy_project, run_cli
import convertall
import release_source

pytestmark = pytest.mark.packaging


def test_versions_are_consistent_without_rewriting_history():
    version = convertall.__version__
    assert version == '0.9.3'
    assert release_source.version_from_source((ROOT / 'source/convertall.py').read_text(encoding='utf-8')) == version
    for path in (ROOT / 'win').glob('*.iss'):
        text = path.read_text(encoding='utf-8')
        assert f'AppVersion={version}' in text
        assert f'convertall-{version}-install' in text
        assert 'convertall.exe.manifest' not in text
        assert 'convertall_dos.exe' in text
    for folder in ('doc', 'docs'):
        for path in (ROOT / folder).glob('README*.html'):
            # The first version is the manual header; old changelog versions
            # are intentionally retained. Manuals are UTF-8, not Windows ANSI.
            assert re.search(r'0\.\d+\.\d+', path.read_text(encoding='utf-8')).group() == version, path
    setup = (ROOT / 'source/setup.py').read_text(encoding='utf-8')
    assert 'from convertall import __version__' in setup
    assert "'-m', 'PyInstaller'" in setup
    assert 'from cx_Freeze import' not in setup
    assert '0.8.0' in (ROOT / 'doc/README.html').read_text(encoding='utf-8')


def test_all_python_source_files_compile():
    for directory in ('source', 'tools', 'tests'):
        for path in (ROOT / directory).glob('*.py'):
            compile(path.read_bytes(), str(path), 'exec')
    for name in ('install.py', 'uninstall.py', 'source/convertall.spec'):
        path = ROOT / name
        compile(path.read_bytes(), str(path), 'exec')


def test_runtime_is_pinned_to_qt6_only():
    text = (ROOT / 'requirements-qt6.txt').read_text(encoding='utf-8')
    for expected in ('PyQt6==6.11.0', 'PyQt6-sip==13.13.0', 'PyQt6-Qt6==6.11.2'):
        assert expected in text
    assert 'PyQt5' not in text and 'PySide' not in text
    for path in (ROOT / 'source').glob('*.py'):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        assert not any(name and name.startswith(('PyQt5', 'PySide')) for name in imports)


def test_pyinstaller_recipe_has_no_machine_specific_path_or_removed_crypto_api():
    text = (ROOT / 'source/convertall.spec').read_text(encoding='utf-8')
    for required in ("Path(SPECPATH)", "contents_directory='.'", "'convertall_dos'",
                     "'data'", "'icons'", "'doc'", "'translations'"):
        assert required in text
    assert 'C:\\git' not in text and 'cipher=' not in text
    assert 'upx=False' in text
    # A frozen diagnostic must read real wheel metadata, not SIP_VERSION_STR.
    assert "copy_metadata('PyQt6-sip')" in text
    assert "'PyQt6_sip-13.13.0.dist-info'" in text
    for path in (ROOT / 'win').glob('*.iss'):
        recipe = path.read_text(encoding='utf-8')
        assert 'PyQt6_sip-13.13.0.dist-info' in recipe


@pytest.fixture
def committed_copy(tmp_path):
    project = copy_project(tmp_path / 'git-copy')
    def git(*args):
        return subprocess.check_output(['git', '-C', str(project), *args], stderr=subprocess.STDOUT)
    git('init', '-b', 'arena/0adacf84-convertall-py')
    git('add', '.')
    git('-c', 'user.name=Release test', '-c', 'user.email=release-test@example.invalid',
        '-c', 'commit.gpgsign=false', 'commit', '-m', 'isolated release test')
    return project, git


def test_archive_reproducible_checksum_commit_and_extracted_cli(committed_copy, tmp_path):
    project, git = committed_copy
    first = release_source.create_archive(project, project / 'dist/release')
    content = first[0].read_bytes()
    metadata = json.loads(first[2].read_text(encoding='utf-8'))
    assert metadata['source_commit'] == git('rev-parse', 'HEAD').decode().strip()
    assert metadata['binding'] == 'Qt6'
    assert metadata['sha256'] == hashlib.sha256(content).hexdigest()
    assert first[1].read_text(encoding='utf-8').strip() == f"{metadata['sha256']}  {first[0].name}"
    second = release_source.create_archive(project, project / 'dist/release')
    assert second[0].read_bytes() == content
    commit = subprocess.check_output(['git', 'get-tar-commit-id'], input=gzip.decompress(content))
    assert commit.decode().strip() == metadata['source_commit']
    extracted = tmp_path / 'extracted'
    with tarfile.open(first[0], 'r:gz') as archive:
        paths = [member.name for member in archive.getmembers()]
        prefix = 'ConvertAll-0.9.3-qt6-source/'
        for relative in ('source/convertall.py', 'data/units.dat', 'translations/convertall_fr.qm',
                         'install.py', 'doc/LICENSE', 'icons/convertall_med.png',
                         'requirements-test.txt', 'pytest.ini', '.coveragerc',
                         '.github/workflows/qt6-release.yml', 'tests/test_gui.py',
                         'tools/release_source.py', 'tools/update_translations.py',
                         'requirements-qt6.txt', 'test_all_qt6.sh',
                         'doc/LICENSE-GPL-3.0', 'doc/RELEASE_QT6_FR.md',
                         'release_qt6.sh', 'tools/release_qt6.py', 'tools/linux_release.py',
                         'tools/appimage-lock.json', 'doc/RELEASE_LINUX_FR.md',
                         'tools/build_deb.py', 'requirements-test-debian.txt',
                         'doc/RELEASE_NOTES_0.9.1.md'):
            assert prefix + relative in paths
        assert not any('/.git/' in path or '/.venv/' in path or '__pycache__' in path for path in paths)
        # This archive is created by git from our own temporary commit. All
        # members must be inside its prefix; do not extract arbitrary inputs.
        assert all((path == prefix.rstrip('/') or path.startswith(prefix))
                   and '..' not in Path(path).parts for path in paths)
        filters = {'filter': 'data'} if hasattr(tarfile, 'data_filter') else {}
        archive.extractall(extracted, **filters)
    script = extracted / 'ConvertAll-0.9.3-qt6-source/source/convertall.py'
    result = run_cli('-q', '1', 'in', 'cm', script=script, cwd=tmp_path)
    assert result.returncode == 0 and result.stdout.strip() == '1 in = 2.54 cm'
    assert run_cli('--test-all', script=script, cwd=tmp_path).returncode == 0
    assert run_cli('--gui-smoke-test', script=script, cwd=tmp_path).returncode == 0


def test_archive_refuses_dirty_tree_or_another_commit(committed_copy):
    project, git = committed_copy
    head = git('rev-parse', 'HEAD').decode().strip()
    (project / 'untracked.txt').write_text('not committed', encoding='utf-8')
    with pytest.raises(ValueError, match='dirty'):
        release_source.create_archive(project, project / 'dist/release')
    (project / 'untracked.txt').unlink()
    git('-c', 'user.name=Release test', '-c', 'user.email=release-test@example.invalid',
        '-c', 'commit.gpgsign=false', 'commit', '--allow-empty', '-m', 'new commit')
    with pytest.raises(ValueError, match='HEAD'):
        release_source.create_archive(project, project / 'dist/release', head)


@pytest.mark.parametrize('output', ['.', '..'])
def test_archive_refuses_repository_or_parent_as_output(committed_copy, output):
    project, git = committed_copy
    with pytest.raises(ValueError, match='dedicated'):
        release_source.create_archive(project, project / output)
