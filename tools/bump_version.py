#!/usr/bin/env python3
# Bump the project version everywhere it is pinned, and check that the pinned
# copies agree with the running code.
#
#   python3 tools/bump_version.py --check            état de cohérence
#   python3 tools/bump_version.py 0.9.3 --dry-run    montre les changements
#   python3 tools/bump_version.py 0.9.3              applique
#   python3 tools/bump_version.py --repair 0.9.2     rattrape des jetons restés
#                                                    à l'ancienne version
#
# It never commits, tags, pushes or touches a release.
#
# Why the strict rules
# --------------------
# The 0.9.1 -> 0.9.2 bump left three version literals behind and turned every CI
# test job red in under two minutes:
#   * tests/test_cli.py compared the `--version` output with a literal string,
#     'ConvertAll 0.9.1 (Qt6)', which the old tool did not see because the
#     version was inside a longer string;
#   * tests/test_release_tools.py passed a fake runtime report whose 'version'
#     is compared with the real __version__ by check_bundle.validate_runtime_info;
#   * tests/test_linux_release.py expected 'Version: 0.9.1-1' in the Debian
#     control file, which the old pattern missed because of the revision suffix.
# So replacements are done on version *tokens* (not quoted strings), all of
# tests/ is covered, and --check refuses to pass while a test that renders the
# real version still carries a different token.
import argparse
import re
import sys
from pathlib import Path

DESCRIPTION = ('met à jour la version partout où elle est épinglée, ou vérifie que les copies '
               'sont cohérentes')

ROOT = Path(__file__).resolve().parent.parent
# The version lines that are labelled, per file glob. A bare x.y.z pattern is
# not usable: README.md links to doc/RELEASE_NOTES_0.9.1.md and compares itself
# to the 0.8.0 benchmark, and the Russian manual carries 'LibreOffice 5.4.6.2' in
# a generator meta tag that comes before its own banner. An earlier 0.x.y-only
# pattern avoided that by accident, and broke on any 1.x version.
ANCHORED = (
    (re.compile(r'(Python/Qt6 fork )(\d+\.\d+\.\d+)'),
     ('doc/README*.html', 'docs/README*.html')),
    (re.compile(r'^(# ConvertAll-py[^\n]*?)(\d+\.\d+\.\d+)', re.M), ('README.md',)),
    (re.compile(r'^(\*\*État : )(\d+\.\d+\.\d+)', re.M), ('README.md',)),
)
VERSION = re.compile(r'\d+\.\d+\.\d+')
# A version token, not a version-shaped substring of something else: '0.9.10'
# does not match '0.9.1', but the Debian revision ('0.9.1-1') and asset names
# ('ConvertAll-0.9.1-qt6-…') do, which is the point.
TOKEN = r'(?<![\w.]){}(?![\w])'
# Files that must follow the current version. tests/ is taken as a whole: any
# version literal there is either the current version or a fake one, and a stale
# one is what breaks CI.
MANAGED_GLOBS = ('tests/*.py',)
# tests/test_bump_version.py defines the stale literals a bump has to catch, on
# purpose. Rewriting them would make its own checks tautological.
EXCLUDED = ('tests/test_bump_version.py',)
# A test that compares the rendered program version, and a fake runtime report
# whose 'version' is compared with the real __version__ (check_bundle does that
# through validate_runtime_info; validate_debian_runtime takes the expectation as
# an argument instead, so those fixtures may use any value).
RENDERED_COMMAND = re.compile(r'ConvertAll (\d+\.\d+\.\d+) \(Qt6\)')
FAKE_RUNTIME_VERSION = re.compile(r"'version'\s*:\s*'(\d+\.\d+\.\d+)'")
RUNTIME_VALIDATOR = 'validate_runtime_info'


def read(path):
    # newline='' preserves CRLF: the Inno Setup recipes are CRLF files, and
    # letting text mode translate them rewrites every line of the file.
    with (ROOT / path).open(encoding='utf-8', newline='') as stream:
        return stream.read()


def write(path, text):
    with (ROOT / path).open('w', encoding='utf-8', newline='') as stream:
        stream.write(text)


def source_version():
    match = re.search(r"^__version__\s*=\s*'([^']+)'", read('source/convertall.py'), re.M)
    if not match:
        raise SystemExit('source/convertall.py has no __version__ line')
    return match.group(1)


def anchored_lines():
    """[(path, pattern)] for the labelled version lines, in file order."""
    for pattern, globs in ANCHORED:
        for glob in globs:
            for path in sorted(ROOT.glob(glob)):
                yield path.relative_to(ROOT), pattern


def iss_files():
    for path in sorted((ROOT / 'win').glob('*.iss')):
        yield path.relative_to(ROOT)


def managed_python():
    result = [Path('source/convertall.py')]
    for pattern in MANAGED_GLOBS:
        for path in sorted(ROOT.glob(pattern)):
            relative = path.relative_to(ROOT)
            if str(relative) not in EXCLUDED:
                result.append(relative)
    return result


def rewrite_tokens(text, old, new):
    return re.sub(TOKEN.format(re.escape(old)), new, text)


def replacement_plan(old, new):
    """[(path, new_text, note)] for every file that must change.

    README.md is anchored twice (banner and state line), so the plan is
    accumulated per file: two independent writes would drop the first one.
    """
    updated, notes = {}, {}

    def stage(path, content, note):
        updated[path], _ = content, notes.setdefault(path, []).append(note)

    for path, pattern in anchored_lines():
        text = updated.get(path, read(path))
        match = pattern.search(text)
        if match is None:
            raise SystemExit(f'{path}: no version line found ({pattern.pattern})')
        if match.group(2) != new:
            stage(path, text[:match.start(2)] + new + text[match.end(2):],
                  f'en-tête {match.group(2)} -> {new}')
    for path in iss_files():
        text = updated.get(path, read(path))
        replaced = rewrite_tokens(text, old, new)
        if replaced != text:
            stage(path, replaced, f'{old} -> {new}')
    for path in managed_python():
        text = updated.get(path, read(path))
        replaced = rewrite_tokens(text, old, new)
        if replaced != text:
            count = len(re.findall(TOKEN.format(re.escape(old)), text))
            stage(path, replaced, f'{count} occurrence(s) {old} -> {new}')
    return [(path, updated[path], ' ; '.join(notes[path])) for path in updated]


def rendered_version_mismatches(version):
    """Tests that compare the real version of the program against a stale literal.

    This is exactly what the 0.9.2 bump broke, in two places: the expected
    `--version` output, and a fake runtime report whose 'version' is compared
    with __version__. Both are detected without running the suite.
    """
    problems = []
    for path in sorted(ROOT.glob('tests/*.py')):
        if str(path.relative_to(ROOT)) in EXCLUDED:
            continue
        text = path.read_text(encoding='utf-8')
        validates_runtime = RUNTIME_VALIDATOR in text
        for number, line in enumerate(text.splitlines(), 1):
            for match in RENDERED_COMMAND.finditer(line):
                if match.group(1) != version:
                    problems.append(f'{path.name}:{number} attend « ConvertAll '
                                    f'{match.group(1)} (Qt6) » alors que le programme annonce '
                                    f'{version}')
            if validates_runtime:
                for match in FAKE_RUNTIME_VERSION.finditer(line):
                    if match.group(1) != version:
                        problems.append(f'{path.name}:{number} compare un rapport de version '
                                        f'{match.group(1)} à __version__ ({version}) via '
                                        f'{RUNTIME_VALIDATOR}')
    return problems


def check(expected=None):
    """The coherence rules of the packaging test, plus the stale-literal rule."""
    problems = []
    current = source_version()
    if expected and current != expected:
        problems.append(f'source/convertall.py pins {current}, expected {expected}')
    from release_source import version_from_source            # noqa: E402
    derived = version_from_source(read('source/convertall.py'))
    if derived != current:
        problems.append(f'release_source derives {derived} but __version__ is {current}')
    for path in iss_files():
        text = read(path)
        if f'AppVersion={current}' not in text:
            problems.append(f'{path}: AppVersion is not {current}')
        if f'convertall-{current}-install' not in text:
            problems.append(f'{path}: installer file name is not {current}')
    for path, pattern in anchored_lines():
        match = pattern.search(read(path))
        if match is None:
            problems.append(f'{path}: no version line found ({pattern.pattern})')
        elif match.group(2) != current:
            problems.append(f'{path}: announces {match.group(2)} instead of {current}')
    problems.extend(rendered_version_mismatches(current))
    if not (ROOT / f'doc/RELEASE_NOTES_{current}.md').is_file():
        problems.append(f'doc/RELEASE_NOTES_{current}.md is missing')
    return current, problems


def release_notes(old, new):
    """A starting point for the human changelog, not a generated document."""
    import subprocess

    def git(*arguments):
        return subprocess.run(['git', *arguments], cwd=ROOT, capture_output=True,
                              text=True, check=False).stdout

    if git('rev-parse', '--verify', '--quiet', f'refs/tags/v{old}').strip():
        lines = git('log', '--oneline', '--no-merges', f'v{old}..HEAD')
        origin = f'Contenu depuis v{old}'
    else:
        # A local clone may not have the tag (it was created by the release).
        lines = git('log', '--oneline', '--no-merges', '-25')
        origin = (f'Tag v{old} absent de ce clone : les 25 derniers commits ; '
                  f'faites « git fetch --tags » pour la liste exacte')
    body = '\n'.join(f'- {line.split(" ", 1)[1]}' for line in lines.splitlines() if ' ' in line)
    return (f'# ConvertAll {new} — notes de version\n\n'
            f'À compléter avant publication. {origin} :\n\n'
            f'{body or "- (aucun commit listé)"}\n\n'
            '## Points à vérifier à la main\n\n'
            '- bureau réel, DPI et GPU : non certifiés par la CI ;\n'
            '- installation, mise à niveau et désinstallation du `.deb` ;\n'
            '- AppImage : double-clic (AppImageLauncher ne lit pas le zstd, voir '
            'doc/RELEASE_LINUX_FR.md) ;\n'
            '- licences et attributions.\n')


def apply_changes(changes, dry_run):
    for path, text, note in changes:
        print(f'  {path}   ({note})')
    if dry_run:
        return
    for path, text, _ in changes:
        write(path, text)


def main():
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument('version', nargs='?', help='nouvelle version, ex. 0.9.3')
    parser.add_argument('--check', action='store_true', help='vérifie la cohérence')
    parser.add_argument('--dry-run', action='store_true', help='montre sans écrire')
    parser.add_argument('--repair', metavar='ANCIENNE', help='remplace les jetons restés à '
                        'ANCIENNE par la version courante (rattrapage)')
    arguments = parser.parse_args()
    sys.path.insert(0, str(ROOT / 'tools'))

    if arguments.repair:
        current = source_version()
        changes = replacement_plan(arguments.repair, current)
        if not changes:
            print(f'Aucun jeton {arguments.repair} à rattraper.')
            return 0
        print(f'Rattrapage de {arguments.repair} vers {current} :')
        apply_changes(changes, arguments.dry_run)
        if arguments.dry_run:
            print('\nRien écrit (--dry-run).')
            return 0
        _, problems = check()
        print(f'\n{current} inchangée.' if not problems else '\nProblèmes restants :')
        for problem in problems:
            print(f'  - {problem}')
        return 1 if problems else 0

    if arguments.check or not arguments.version:
        current, problems = check(arguments.version)
        print(f'Version actuelle : {current}')
        if problems:
            print('Incohérences :')
            for problem in problems:
                print(f'  - {problem}')
            return 1
        print('Cohérence : OK (source, .iss, manuels HTML, README, tests, notes de version)')
        return 0

    new = arguments.version
    if not VERSION.fullmatch(new):
        print(f'Version invalide : {new} (attendu x.y.z)', file=sys.stderr)
        return 2
    old = source_version()
    if old == new:
        print(f'La version est déjà {new} ; rien à faire.')
        return 0
    changes = replacement_plan(old, new)
    notes = f'doc/RELEASE_NOTES_{new}.md'
    print(f'{old} -> {new} :')
    apply_changes(changes, arguments.dry_run)
    if not (ROOT / notes).is_file():
        print(f'  {notes} (nouveau, à compléter)')
    if arguments.dry_run:
        print('\nRien écrit (--dry-run).')
        return 0
    if not (ROOT / notes).is_file():
        write(notes, release_notes(old, new))
    _, problems = check(new)
    print(f'\n{old} -> {new}')
    if problems:
        print('À corriger :')
        for problem in problems:
            print(f'  - {problem}')
        return 1
    print('Cohérence vérifiée après modification.')
    print('Prochaine étape, à vous : relire git diff, puis committer.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
