"""Packaging cannot silently modify already-tested bundle resources."""
import pytest

from helpers import ROOT
import linux_release as packages
from linux_release import ReleaseError

pytestmark = pytest.mark.packaging


def test_notices_may_be_added_but_tested_payload_must_stay_identical(tmp_path):
    bundle = tmp_path / 'payload'
    bundle.mkdir()
    (bundle / 'convertall').write_bytes(b'executable fixture')
    expected = packages.file_hashes(bundle)
    (bundle / 'NOTICE').write_text('extra notice', encoding='utf-8')
    packages.verify_payload(bundle, expected)
    (bundle / 'convertall').write_bytes(b'modified executable')
    with pytest.raises(ReleaseError, match='Packaging changed'):
        packages.verify_payload(bundle, expected)


def test_wheel_notices_include_metadata_and_text_not_unrelated_binaries(tmp_path, monkeypatch):
    source = tmp_path / 'wheel'
    source.mkdir()
    for name in ('LICENSE', 'library.so'):
        (source / name).write_text('fixture', encoding='utf-8')
    class Distribution:
        version = 'unit-test'
        files = ['LICENSE', 'library.so', '../escape/LICENSE']
        def locate_file(self, name):
            return source / name
        def read_text(self, name):
            assert name == 'METADATA'
            return 'License: fixture\n'
    monkeypatch.setattr(packages.metadata, 'distribution', lambda name: Distribution())
    bundle = tmp_path / 'bundle'
    bundle.mkdir()
    inventory = packages.collect_notices(bundle)
    assert inventory['PyQt6']['notice_files'] == ['LICENSE']
    assert (bundle / 'doc/third-party/PyQt6/LICENSE').is_file()
    assert (bundle / 'doc/third-party/PyQt6/METADATA').is_file()
    assert not (bundle / 'doc/third-party/PyQt6/library.so').exists()


def test_readme_exposes_the_user_run_release_script():
    readme = (ROOT / 'README.md').read_text(encoding='utf-8')
    assert 'bash release_qt6.sh --wait-ci --draft' in readme
    assert 'doc/RELEASE_LINUX_FR.md' in readme
