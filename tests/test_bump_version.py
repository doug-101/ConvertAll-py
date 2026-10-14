"""A version bump must not leave a literal behind: that turned CI red.

Run 38471134227 failed in the ten jobs that start pytest because the 0.9.1 ->
0.9.2 bump rewrote only quoted version strings, leaving three literals that the
tests compare with the running code. These tests replay that failure on a copy
of the project, so the next bump cannot pass silently.

The expected versions are derived from the checkout at run time, and this file
is excluded from rewriting (see EXCLUDED in tools/bump_version.py) because it
holds stale literals on purpose.
"""
import contextlib
import re
import sys

import pytest

from helpers import ROOT, copy_project
import bump_version

# The version of this checkout, and a target that no release will ever use.
CURRENT = bump_version.source_version()
NEXT = '9.9.9'
STALE_CLI_LINE = f"    assert result.stdout.strip() == 'ConvertAll {CURRENT} (Qt6)'\n"
STALE_DEB_LINE = f"Version: {CURRENT}-1\\nArchitecture: all\\n"
STALE_RUNTIME_LINE = (f"    return {{'application': 'ConvertAll', 'version': '{CURRENT}',"
                      " 'binding': 'PyQt6',\n")


@contextlib.contextmanager
def arguments(*argv):
    previous, sys.argv = sys.argv, list(argv)
    try:
        yield
    finally:
        sys.argv = previous


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A throwaway copy of the project, with the tool pointed at it."""
    copied = copy_project(tmp_path / 'project')
    monkeypatch.setattr(bump_version, 'ROOT', copied)
    monkeypatch.chdir(copied)
    return copied


def bump(project, version, *options):
    with arguments('bump_version.py', *options, version):
        return bump_version.main()


def read(project, name):
    return (project / name).read_text(encoding='utf-8')


def write(project, name, text):
    (project / name).write_text(text, encoding='utf-8', newline='')


def stale(project, name, fragment, replacement):
    """Reproduce what the old tool left behind: one literal stuck a step behind."""
    text = read(project, name)
    assert fragment in text, f'{name}: the bump did not rewrite the literal'
    write(project, name, text.replace(fragment, replacement, 1))


def test_a_bump_rewrites_every_literal_the_tests_compare_with_the_program(project):
    assert bump(project, NEXT) == 0
    assert f"__version__ = '{NEXT}'" in read(project, 'source/convertall.py')
    # The three literals that broke the 0.9.2 CI run.
    assert f"== 'ConvertAll {NEXT} (Qt6)'" in read(project, 'tests/test_cli.py')
    assert f"Version: {NEXT}-1\\nArchitecture: all\\n" in read(project, 'tests/test_linux_release.py')
    assert f"'version': '{NEXT}'" in read(project, 'tests/test_release_tools.py')
    assert bump_version.check(NEXT)[1] == []


def test_the_manual_header_is_not_the_program_version_in_the_text(project):
    """A bare x.y.z pattern would rewrite the generator meta tag of README_ru.html."""
    assert 'LibreOffice 5.4.6' in read(project, 'doc/README_ru.html')
    assert bump(project, NEXT) == 0
    assert 'LibreOffice 5.4.6' in read(project, 'doc/README_ru.html')
    assert NEXT in read(project, 'doc/README_ru.html')


def test_the_readme_banner_and_state_line_follow_the_version(project):
    """The README announces the version twice; its history must not move."""
    history = [line for line in read(project, 'README.md').splitlines()
               if 'RELEASE_NOTES_' in line]
    assert history, 'the README links to the previous release notes'
    assert bump(project, NEXT) == 0
    readme = read(project, 'README.md')
    assert readme.splitlines()[0].endswith(NEXT), readme.splitlines()[0]
    assert f'**État : {NEXT} ' in readme
    assert all(line in readme for line in history)
    assert '0.8.0' in readme


def test_check_refuses_a_readme_left_at_the_previous_release(project):
    assert bump(project, NEXT) == 0
    readme = read(project, 'README.md')
    write(project, 'README.md', readme.replace(f'Qt6 {NEXT}', f'Qt6 {CURRENT}', 1))
    _, problems = bump_version.check(NEXT)
    assert any('README.md' in problem and CURRENT in problem for problem in problems)


def test_the_changelog_of_the_previous_release_is_history_not_a_pinned_copy(project):
    assert bump(project, NEXT) == 0
    assert (project / f'doc/RELEASE_NOTES_{CURRENT}.md').is_file()
    assert (project / f'doc/RELEASE_NOTES_{NEXT}.md').is_file()


def test_bumping_to_the_current_version_changes_nothing(project):
    assert bump(project, CURRENT) == 0
    assert bump_version.check(CURRENT)[1] == []


def test_a_version_that_is_not_x_y_z_is_refused(project):
    assert bump(project, '0.9') == 2
    assert bump(project, '0.9.2.1') == 2
    assert f"__version__ = '{CURRENT}'" in read(project, 'source/convertall.py')


def test_check_refuses_a_rendered_version_left_at_the_previous_release(project):
    """This is the exact assertion that failed in the 0.9.2 CI run."""
    assert bump(project, NEXT) == 0
    stale(project, 'tests/test_cli.py', f"== 'ConvertAll {NEXT} (Qt6)'", STALE_CLI_LINE)
    version, problems = bump_version.check(NEXT)
    assert version == NEXT
    assert any(f'ConvertAll {CURRENT} (Qt6)' in problem and 'test_cli.py' in problem
               for problem in problems)


def test_check_refuses_a_fake_runtime_report_compared_with_the_real_version(project):
    assert bump(project, NEXT) == 0
    stale(project, 'tests/test_release_tools.py', f"'version': '{NEXT}'", STALE_RUNTIME_LINE)
    _, problems = bump_version.check(NEXT)
    assert any('validate_runtime_info' in problem and 'test_release_tools.py' in problem
               for problem in problems)


def test_check_ignores_fixtures_that_do_not_compare_with_the_real_version(project):
    """validate_debian_runtime takes the expected version as an argument."""
    assert bump(project, NEXT) == 0
    text = read(project, 'tests/test_debian_package.py')
    assert f"validate_debian_runtime(native_runtime, '{NEXT}')" in text
    write(project, 'tests/test_debian_package.py',
          text.replace(f"'version': '{NEXT}'", f"'version': '{CURRENT}'", 1))
    assert bump_version.check(NEXT)[1] == []


def test_repair_catches_the_literals_an_earlier_bump_left_behind(project):
    assert bump(project, NEXT) == 0
    stale(project, 'tests/test_cli.py', f"== 'ConvertAll {NEXT} (Qt6)'", STALE_CLI_LINE)
    stale(project, 'tests/test_linux_release.py', f"Version: {NEXT}-1\\nArchitecture: all\\n",
          STALE_DEB_LINE)
    stale(project, 'tests/test_release_tools.py', f"'version': '{NEXT}'", STALE_RUNTIME_LINE)
    assert bump_version.check(NEXT)[1], 'the stale literals must be detected first'

    with arguments('bump_version.py', '--repair', CURRENT):
        assert bump_version.main() == 0
    assert bump_version.check(NEXT)[1] == []
    assert f"== 'ConvertAll {NEXT} (Qt6)'" in read(project, 'tests/test_cli.py')
    assert f"Version: {NEXT}-1\\nArchitecture: all\\n" in read(project,
                                                               'tests/test_linux_release.py')


def test_this_checkout_has_no_stale_version_literal():
    """The check that would have failed before the 15896e4 CI run.

    It runs on the real tree, so a bump that misses a literal fails here in
    every test job instead of ten minutes into a marked release run.
    """
    version, problems = bump_version.check()
    assert problems == []
    assert re.fullmatch(r'\d+\.\d+\.\d+', version), version


def test_the_tool_writes_files_but_never_commits(project):
    """Committing, tagging and pushing a version bump stay manual decisions."""
    assert (ROOT / '.git').exists(), 'the suite expects a checkout'
    assert bump(project, NEXT) == 0
    assert not (project / '.git').exists()
