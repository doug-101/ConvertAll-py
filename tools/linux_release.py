"""Pure staging/integrity helpers for user-run Qt6 Linux releases.

No build, download, installation or GitHub write happens on import.
"""
import gzip
import hashlib
from importlib import metadata
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
import shutil
import tarfile
import zipfile


class ReleaseError(RuntimeError):
    pass


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe_file(root, relative):
    """Canonical report paths only; never read through an escaping symlink."""
    root = Path(root).resolve()
    name = PurePosixPath(relative)
    if (not relative or not name.parts or name.is_absolute() or '..' in name.parts
            or '\\' in relative or '\x00' in relative or name.as_posix() != relative):
        raise ReleaseError(f'Unsafe artifact path: {relative!r}')
    path = root.joinpath(*name.parts)
    if not path.resolve().is_relative_to(root):
        raise ReleaseError(f'Artifact escaped its directory: {relative!r}')
    return path


def file_hashes(directory):
    directory = Path(directory).resolve()
    return {path.relative_to(directory).as_posix(): sha256(
                safe_file(directory, path.relative_to(directory).as_posix()))
            for path in sorted(directory.rglob('*')) if path.is_file()}


def verify_bundle_report(directory, report, commit, version, *, extra_prefixes=()):
    """Re-hash the directory against a recorded report.

    `extra_prefixes` names the paths a packaging step legitimately adds after
    the report was written (the wheel notices and RELEASE-INFO.json); anything
    else that is not in the report still fails.
    """
    runtime = report.get('runtime', {})
    pins = {'application': 'ConvertAll', 'version': version, 'binding': 'PyQt6',
            'pyqt_binding': '6.11.0', 'qt_runtime': '6.11.2', 'sip_package': '13.13.0'}
    if (report.get('status') != 'PASS' or report.get('checker_source_commit') != commit
            or report.get('checker_working_tree_dirty') is not False
            or not isinstance(runtime, dict)
            or any(runtime.get(key) != value for key, value in pins.items())
            or not isinstance(runtime.get('sip_generator'), str)
            or not runtime['sip_generator']):
        raise ReleaseError('Bundle report is not a clean PASS for this SHA/runtime')
    expected = report.get('bundle_sha256')
    if not isinstance(expected, dict) or not expected:
        raise ReleaseError('Bundle report has no file hashes')
    for name, digest in expected.items():
        path = safe_file(directory, name)
        if not re.fullmatch(r'[0-9a-f]{64}', str(digest)) or not path.is_file():
            raise ReleaseError(f'Missing/invalid bundle file: {name}')
    hashes = file_hashes(directory)
    if extra_prefixes:
        hashes = {name: digest for name, digest in hashes.items()
                  if not name.startswith(tuple(extra_prefixes))}
    if hashes != expected:
        raise ReleaseError('Bundle bytes differ from the tested bundle report')


def verify_payload(directory, expected):
    """Packaging may add notices; it must never alter a tested bundle byte."""
    for name, digest in expected.items():
        path = safe_file(directory, name)
        if not path.is_file() or sha256(path) != digest:
            raise ReleaseError(f'Packaging changed/missed a tested bundle file: {name}')


def verify_source_archive(directory, version, commit):
    archive = Path(directory) / f'ConvertAll-{version}-qt6-source.tar.gz'
    provenance = archive.with_name(archive.name + '.provenance.json')
    checksum = archive.with_name(archive.name + '.sha256')
    info = json.loads(provenance.read_text(encoding='utf-8'))
    digest = sha256(archive)
    if (info.get('source_commit') != commit or info.get('version') != version
            or info.get('binding') != 'Qt6' or info.get('sha256') != digest
            or checksum.read_text(encoding='ascii').strip() != f'{digest}  {archive.name}'):
        raise ReleaseError('CI source archive SHA/version/checksum mismatch')
    return archive, checksum, provenance


def normalize_permissions(directory):
    for path in [Path(directory), *Path(directory).rglob('*')]:
        if not path.is_symlink():
            executable = path.is_dir() or path.name in (
                'convertall', 'convertall.exe', 'convertall_dos.exe', 'AppRun')
            path.chmod(0o755 if executable else 0o644)


def copy_bundle(source, destination):
    """Retain resources and internal symlinks; canonicalize release permissions."""
    source, destination = Path(source), Path(destination)
    for path in source.rglob('*'):
        if path.is_symlink() and (not path.exists()
                                 or not path.resolve().is_relative_to(source.resolve())):
            raise ReleaseError(f'External/dangling bundle symlink: {path}')
    shutil.copytree(source, destination, symlinks=True)
    normalize_permissions(destination)


def launcher(appimage=False):
    # Relocatable: also works from dpkg-deb --extract without root/installation.
    suffix = '/usr/lib/convertall/convertall' if appimage else '/../lib/convertall/convertall'
    return ('#!/bin/sh\nset -eu\n'
            'HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\n'
            f'exec "$HERE{suffix}" "$@"\n')


def desktop_entry():
    return ('[Desktop Entry]\nType=Application\nVersion=1.1\nName=ConvertAll\n'
            'GenericName=Unit Converter\nGenericName[fr]=Convertisseur d’unités\n'
            'Comment=Combine and convert units\nComment[fr]=Combiner et convertir les unités\n'
            'Exec=convertall\nIcon=convertall\nTerminal=false\nStartupNotify=true\n'
            'Categories=Education;Math;\n')


def write_file(path, text, executable=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8', newline='\n')
    path.chmod(0o755 if executable else 0o644)


def glibc_requirement(bundle, read_versions):
    """Inspect actual ELF symbol requirements, not the build host's libc label."""
    versions = set()
    for path in sorted(Path(bundle).rglob('*')):
        if not path.is_file():
            continue
        with path.open('rb') as stream:
            elf = stream.read(4) == b'\x7fELF'
        if elf:
            output = read_versions(path)
            versions.update(tuple(map(int, value.split('.')))
                            for value in re.findall(r'\bGLIBC_(\d+(?:\.\d+)+)\b', output))
    if not versions:
        raise ReleaseError('No GLIBC symbol requirements found in the Linux bundle')
    return '.'.join(map(str, max(versions)))


DEBIAN_DEPENDENCIES = ('python3 (>= 3.11)', 'python3-pyqt6 (>= 6.4.2)',
                       'python3-pyqt6.sip (>= 13.4.1)', 'qt6-translations-l10n (>= 6.4.2)')


def deb_control(version, maintainer, installed_kib):
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ReleaseError('Invalid Debian application version')
    if (not re.fullmatch(r'[^<>\r\n]+ <[^<>\s@]+@[^<>\s@]+>', maintainer)
            or not isinstance(installed_kib, int) or installed_kib < 1):
        raise ReleaseError('Invalid Debian maintainer/size')
    return (f'Package: convertall\nVersion: {version}-1\nArchitecture: all\n'
            f'Maintainer: {maintainer}\nSection: science\nPriority: optional\n'
            f'Installed-Size: {installed_kib}\nDepends: {", ".join(DEBIAN_DEPENDENCIES)}\n'
            'Homepage: https://github.com/jojo8356/ConvertAll-py\n'
            'Description: flexible unit converter (Python/PyQt6 edition)\n'
            ' Combine arbitrary units, with translations, history and fractions.\n'
            ' Python, PyQt6, SIP and Qt are supplied by Debian packages, not bundled.\n')


def deb_launcher():
    # Fixed system interpreter; -E/-s prevent a wheel venv/PYTHONPATH/user site
    # from falsely validating a package intended for Debian's shared runtime.
    return ('#!/bin/sh\nset -eu\n'
            'HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\n'
            'exec /usr/bin/python3 -E -s "$HERE/../share/convertall/_debian_entry.py" "$@"\n')


def deb_entry():
    return ('from pathlib import Path\nimport sys\n'
            'try:\n    import convertall\n'
            'except ImportError as error:\n'
            '    print("Debian dependencies unavailable: " + str(error) + "\\n"\n'
            '          "Install with apt: python3-pyqt6 python3-pyqt6.sip qt6-translations-l10n", file=sys.stderr)\n'
            '    sys.exit(1)\n'
            'base = Path(__file__).resolve().parent\n'
            'convertall.dataFilePath = str(base / "data")\n'
            'convertall.iconPath = str(base / "icons")\n'
            'convertall.helpFilePath = str(base.parent / "doc" / "convertall")\n'
            'sys.exit(convertall.main())\n')


def stage_deb(destination, root, version, maintainer):
    """Architecture-independent source/data package, NEVER a frozen bundle."""
    destination, root = Path(destination), Path(root)
    if destination.exists():
        raise ReleaseError('Use a fresh Debian staging directory')
    app = destination / 'usr/share/convertall'
    app.mkdir(parents=True)
    for source in sorted((root / 'source').glob('*.py')):
        if source.name != 'setup.py':
            shutil.copyfile(source, app / source.name)
    for directory, pattern in (('data', '*.dat'), ('icons', '*.png'),
                               ('translations', 'convertall_*.qm')):
        target = app / directory
        target.mkdir()
        for source in sorted((root / directory).glob(pattern)):
            shutil.copyfile(source, target / source.name)
    write_file(app / '_debian_entry.py', deb_entry())
    write_file(destination / 'usr/bin/convertall', deb_launcher(), executable=True)
    write_file(destination / 'usr/share/applications/convertall.desktop', desktop_entry())
    icon = destination / 'usr/share/icons/hicolor/scalable/apps/convertall.svg'
    icon.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / 'icons/convertall-icon.svg', icon)
    doc = destination / 'usr/share/doc/convertall'
    doc.mkdir(parents=True)
    for pattern in ('README*.html', 'LICENSE*'):
        for source in sorted((root / 'doc').glob(pattern)):
            if source.is_file():
                shutil.copyfile(source, doc / source.name)
    write_file(doc / 'copyright',
               'ConvertAll: GPL-2.0-or-later; use with PyQt6 under GPLv3.\n'
               'Copyright notices and full terms: LICENSE and LICENSE-GPL-3.0.\n'
               'Only application source and resources are distributed here.\n'
               'Python, Qt, PyQt6 and SIP are dependencies managed by Debian.\n')
    installed_kib = max(1, (sum(p.stat().st_size for p in destination.rglob('*')
                                if p.is_file()) + 1023) // 1024)
    write_file(destination / 'DEBIAN/control', deb_control(version, maintainer, installed_kib))
    normalize_permissions(destination)
    verify_thin_deb_payload(destination)
    return destination


TRANSLATION_WARNING = re.compile(r'translation file "([^"]+)" could not be loaded')


def translation_warning_names(output):
    """Catalogue names the application reported as unloadable, deduplicated."""
    return sorted(set(TRANSLATION_WARNING.findall(output)))


def expected_missing_translations(locale, qt_translations, app_translations):
    """Which catalogue names may legitimately warn on THIS distribution runtime.

    Distribution Qt may ship fewer widget languages than the pinned wheels, so
    an absent qtbase file is not a failure. An application catalogue is always
    shipped by our package; a warning for it is never expected.
    """
    name = str(locale).split('.', 1)[0]
    language = name.split('_', 1)[0]
    expected = []
    if not (Path(qt_translations) / f'qtbase_{language}.qm').is_file():
        expected.append(f'qt_{name}')
    if not any((Path(app_translations) / f'convertall_{key}.qm').is_file()
               for key in (name, language)):
        expected.append(f'convertall_{name}')
    return sorted(expected)


def verify_thin_deb_payload(directory):
    directory = Path(directory)
    app = directory / 'usr/share/convertall'
    if not (app / 'convertall.py').is_file() or not (app / '_debian_entry.py').is_file():
        raise ReleaseError('Debian application sources missing')
    for path in directory.rglob('*'):
        if (path.name in ('PyQt6', '_internal', 'base_library.zip', 'third-party', 'setup.py')
                or path.name.endswith(('.dist-info', '.egg-info'))
                or path.suffix.lower() in ('.so', '.pyd', '.dll', '.pyc', '.exe', '.ts', '.spec')
                or path.name.startswith(('libpython', 'libQt6', 'libqt6'))):
            raise ReleaseError(f'Bundled runtime/build file in thin Debian package: {path}')
        if path.is_file():
            with path.open('rb') as stream:
                if stream.read(4) == b'\x7fELF':
                    raise ReleaseError(f'ELF binary in architecture-all Debian package: {path}')
    if len(list((app / 'data').glob('*.dat'))) != 7:
        raise ReleaseError('Debian package must preserve all seven unit catalogues')
    shipped = {path.name for path in (app / 'translations').glob('*.qm')}
    expected_languages = {f'convertall_{language}.qm'
                          for language in ('ca', 'de', 'es', 'fr', 'ru', 'sv')}
    if shipped != expected_languages:
        raise ReleaseError('Debian package must ship exactly the six application translations')


def validate_debian_runtime(runtime, version):
    """Native Debian profile; frozen builds keep their strict 6.11 pins."""
    def at_least(value, minimum):
        match = re.match(r'^(\d+(?:\.\d+)+)', str(value))
        return bool(match and tuple(map(int, match[1].split('.'))) >= minimum)
    if (not isinstance(runtime, dict) or runtime.get('application') != 'ConvertAll'
            or runtime.get('version') != version or runtime.get('binding') != 'PyQt6'
            or runtime.get('frozen') is not False
            or not at_least(runtime.get('python_version'), (3, 11))
            or not at_least(runtime.get('pyqt_binding'), (6, 4, 2))
            or not at_least(runtime.get('qt_runtime'), (6, 4, 2))
            or not at_least(runtime.get('sip_package'), (13, 4, 1))
            or not isinstance(runtime.get('sip_generator'), str) or not runtime['sip_generator']):
        raise ReleaseError('Unsupported Debian system Python/Qt runtime')
    if not re.fullmatch(r'/usr/bin/python3(?:\.\d+)?', runtime.get('python_executable', '')):
        raise ReleaseError('Debian package must use /usr/bin/python3, not the build venv')
    if not runtime.get('pyqt_location', '').startswith('/usr/lib/python3/dist-packages/PyQt6/'):
        raise ReleaseError('Debian package loaded PyQt6 outside Debian dist-packages')


def stage_appdir(bundle, destination, root):
    destination, root = Path(destination), Path(root)
    copy_bundle(bundle, destination / 'usr/lib/convertall')
    write_file(destination / 'AppRun', launcher(appimage=True), executable=True)
    write_file(destination / 'convertall.desktop', desktop_entry())
    shutil.copyfile(root / 'icons/convertall-icon.svg', destination / 'convertall.svg')
    shutil.copyfile(root / 'icons/convertall_lg.png', destination / 'convertall.png')
    # A real image, not an absolute symlink into the packager's checkout.
    shutil.copyfile(root / 'icons/convertall_lg.png', destination / '.DirIcon')
    normalize_permissions(destination)
    return destination


def collect_notices(bundle):
    """Copy wheel notices without claiming a complete legal/source inventory."""
    destination = Path(bundle) / 'doc/third-party'
    destination.mkdir(parents=True, exist_ok=True)
    inventory = {}
    for name in ('PyQt6', 'PyQt6-Qt6', 'PyQt6-sip', 'PyInstaller', 'pyinstaller-hooks-contrib'):
        distribution = metadata.distribution(name)
        folder = destination / name
        folder.mkdir(exist_ok=True)  # a resumed run rewrites the same notices
        copied = []
        for item in distribution.files or []:
            relative = PurePosixPath(str(item).replace('\\', '/'))
            if '..' in relative.parts or relative.is_absolute():
                continue
            if not any(token in str(relative).lower()
                       for token in ('license', 'licence', 'copying', 'copyright', 'notice')):
                continue
            source = Path(distribution.locate_file(item))
            if source.is_file():
                target = folder.joinpath(*relative.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                copied.append(relative.as_posix())
        # Package metadata carries license/source links even when the wheel lacks texts.
        text = distribution.read_text('METADATA')
        if text:
            write_file(folder / 'METADATA', text)
        inventory[name] = {'version': distribution.version, 'notice_files': copied}
    write_file(destination / 'inventory.json', json.dumps(inventory, indent=2) + '\n')
    return inventory


def make_tar(directory, output, epoch):
    """One portable directory, with executable bits/symlinks and fixed owners."""
    directory, output = Path(directory), Path(output)
    def normalize(info):
        info.uid = info.gid = 0
        info.uname = info.gname = 'root'
        info.mtime = epoch
        if info.isdir():
            info.mode = 0o755
        elif info.isfile():
            info.mode = 0o755 if PurePosixPath(info.name).name == 'convertall' else 0o644
        return info
    with output.open('wb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as stream:
            with tarfile.open(fileobj=stream, mode='w', format=tarfile.PAX_FORMAT) as archive:
                archive.add(directory, arcname=directory.name, filter=normalize)


def extract_own_tar(archive, destination):
    """Validate even on Python 3.11.2, which predates tarfile's data filter."""
    with tarfile.open(archive, 'r:gz') as stream:
        for item in stream.getmembers():
            name = PurePosixPath(item.name)
            if name.is_absolute() or '..' in name.parts or not (item.isfile() or item.isdir() or item.issym()):
                raise ReleaseError('Unsafe portable tar member')
            if item.issym():
                target = posixpath.normpath(posixpath.join(str(name.parent), item.linkname))
                if item.linkname.startswith('/') or target == '..' or target.startswith('../'):
                    raise ReleaseError('Unsafe portable tar symlink')
        options = {'filter': 'data'} if hasattr(tarfile, 'data_filter') else {}
        stream.extractall(destination, **options)


def make_windows_zip(bundle, output, prefix, epoch):
    import time
    # ZIP cannot encode dates before 1980 or after 2107.
    stamp = time.gmtime(max(315532800, min(epoch, 4354819198)))[:6]
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(Path(bundle).rglob('*')):
            if not path.is_file():
                continue
            name = path.relative_to(bundle).as_posix()
            safe_file(bundle, name)
            info = zipfile.ZipInfo(f'{prefix}/{name}', stamp)
            info.create_system = 3
            info.external_attr = (0o100755 if path.suffix.lower() == '.exe' else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
